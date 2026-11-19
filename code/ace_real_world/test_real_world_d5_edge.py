"""Ekspansi tes tepi bermakna (>=25 kasus) untuk paket `ace_real_world` (Gelombang D5).

Meliputi input batas, kosong, rusak, dan ekstrem di seluruh 7 modul:
- `data_wrangler_synth` (termasuk `TransformRule`)
- `git_analyzer_synth` (termasuk `ChurnRecord`, `CodebaseMetrics`)
- `log_parser_synth` (termasuk `LogRule`)
- `net_client_synth` (termasuk `ClientRule`)
- `process_sentinel` (termasuk `ProcessReport`)
- `system_tool_synth` (termasuk `CommandRule`)
- `mission_integration` (`RealWorldMissionIntegrator`)
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from ace_mission.bus import MissionBus
from ace_real_world.data_wrangler_synth import DataWranglerSynthesizer, TransformRule
from ace_real_world.git_analyzer_synth import ChurnRecord, CodebaseMetrics, GitAnalyzerSynthesizer
from ace_real_world.log_parser_synth import LogParserSynthesizer, LogRule
from ace_real_world.mission_integration import RealWorldMissionIntegrator
from ace_real_world.net_client_synth import ClientRule, NetClientSynthesizer
from ace_real_world.process_sentinel import ProcessReport, ProcessSentinel
from ace_real_world.system_tool_synth import CommandRule, SystemToolSynthesizer


def _exec_fn(source: str, func_name: str):
    ns: dict = {}
    exec(compile(source, "<d5_synth>", "exec"), ns)
    return ns[func_name]


def _make_fake_proc_entry(
    proc_root: Path,
    pid: int,
    *,
    comm: str,
    state: str = "S",
    utime: int = 10,
    stime: int = 5,
    rss_pages: int = 256,
    cmdline: bytes = b"",
) -> None:
    pdir = proc_root / str(pid)
    pdir.mkdir(parents=True, exist_ok=True)
    # Minimal 24+ fields after "(comm) " per Linux /proc/[pid]/stat layout
    rest = [state] + ["0"] * 10 + [str(utime), str(stime)] + ["0"] * 8 + [str(rss_pages), "0"]
    (pdir / "stat").write_text(f"{pid} ({comm}) " + " ".join(rest) + "\n", encoding="utf-8")
    (pdir / "cmdline").write_bytes(cmdline)


class TestRealWorldD5Edge(unittest.TestCase):
    # --- 1. data_wrangler_synth ---

    def test_01_data_wrangler_empty_string_identity_and_frozen_rule(self) -> None:
        rule = DataWranglerSynthesizer().synthesize_string_transform([("", ""), ("x", "x")])
        self.assertIsInstance(rule, TransformRule)
        self.assertEqual(rule.rule_id, "rule_identity")
        fn = _exec_fn(rule.transform_code, "transform_data_field")
        self.assertEqual(fn(""), "")
        with self.assertRaises(FrozenInstanceError):
            rule.rule_id = "mutated"  # type: ignore[misc]

    def test_02_data_wrangler_delimiter_missing_on_runtime_input_returns_empty(self) -> None:
        rule = DataWranglerSynthesizer().synthesize_string_transform(
            [("a:10:ok", "10"), ("b:20:err", "20")]
        )
        self.assertIsNotNone(rule)
        fn = _exec_fn(rule.transform_code, "transform_data_field")
        self.assertEqual(fn("no_delimiter_here"), "")
        self.assertEqual(fn(""), "")
        self.assertEqual(fn("c: 99 :warn"), "99")

    def test_03_data_wrangler_mixed_delimiter_inconsistency_falls_back_cleanly(self) -> None:
        rule = DataWranglerSynthesizer().synthesize_string_transform(
            [("k:val1", "val1"), ("no_colon_val2", "val2")]
        )
        self.assertIsNone(rule)

    def test_04_data_wrangler_conflicting_identical_inputs_return_none(self) -> None:
        rule = DataWranglerSynthesizer().synthesize_string_transform(
            [("same:1", "1"), ("same:1", "2")]
        )
        self.assertIsNone(rule)

    def test_05_data_wrangler_whitespace_only_strip_and_unicode(self) -> None:
        rule = DataWranglerSynthesizer().synthesize_string_transform(
            [("  café  ", "café"), ("\tnaïve\n", "naïve")]
        )
        self.assertIsNotNone(rule)
        self.assertEqual(rule.operations, ("STRIP",))
        fn = _exec_fn(rule.transform_code, "transform_data_field")
        self.assertEqual(fn("   "), "")

    # --- 2. git_analyzer_synth ---

    def test_06_git_analyzer_unborn_repo_zero_commits_returns_empty_and_zero_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            analyzer = GitAnalyzerSynthesizer(tmp)
            self.assertEqual(analyzer.get_recent_churn(limit=10), [])
            metrics = analyzer.compute_codebase_metrics()
            self.assertIsInstance(metrics, CodebaseMetrics)
            self.assertEqual(metrics.total_commits, 0)
            self.assertEqual(metrics.average_churn_per_commit, 0.0)

    def test_07_git_analyzer_empty_commit_and_pipe_in_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "empty | init"], cwd=tmp, check=True)
            (root / "code").mkdir()
            (root / "code" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            subprocess.run(["git", "add", "code/a.py"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "add code | pipe"], cwd=tmp, check=True)

            analyzer = GitAnalyzerSynthesizer(tmp)
            recs = analyzer.get_recent_churn(limit=5)
            self.assertEqual(len(recs), 2)
            self.assertIsInstance(recs[0], ChurnRecord)
            self.assertEqual(recs[0].files_changed, 1)
            self.assertEqual(recs[0].insertions, 2)
            self.assertEqual(recs[0].deletions, 0)
            self.assertEqual(recs[1].files_changed, 0)
            with self.assertRaises(FrozenInstanceError):
                recs[0].insertions = 99  # type: ignore[misc]

    def test_08_git_analyzer_hotspot_caps_at_top_5_and_handles_non_utf8_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=tmp, check=True)
            (root / "tools").mkdir()
            for idx in range(1, 8):
                (root / "tools" / f"m{idx}.py").write_text("a = 1\n" * idx, encoding="utf-8")
            (root / "tools" / "binary_comment.py").write_bytes(b"# \xff\xfe\nx = 1\n")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=tmp, check=True)

            metrics = GitAnalyzerSynthesizer(tmp).compute_codebase_metrics()
            self.assertEqual(metrics.total_python_files, 8)
            self.assertEqual(len(metrics.hotspot_files), 5)
            self.assertEqual(metrics.hotspot_files[0], ("tools/m7.py", 7))

    def test_09_git_analyzer_limit_zero_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "one"], cwd=tmp, check=True)
            self.assertEqual(GitAnalyzerSynthesizer(tmp).get_recent_churn(limit=0), [])

    # --- 3. log_parser_synth ---

    def test_10_log_parser_regex_metacharacters_in_delimiters_escaped(self) -> None:
        synth = LogParserSynthesizer()
        samples = [
            "host(10.0.0.1)+[err]: code=503 msg=timeout",
            "host(10.0.0.1)+[err]: code=404 msg=missing",
        ]
        expected = [
            {"code": "503", "msg": "timeout"},
            {"code": "404", "msg": "missing"},
        ]
        rule = synth.synthesize_regex_parser(samples, expected, func_name="parse_meta")
        self.assertIsInstance(rule, LogRule)
        self.assertEqual(rule.field_names, ("code", "msg"))
        fn = _exec_fn(rule.extractor_code, "parse_meta")
        self.assertEqual(fn("host(10.0.0.1)+[err]: code=200 msg=ok"), {"code": "200", "msg": "ok"})
        self.assertEqual(fn(""), {})
        self.assertEqual(fn("unmatched garbage line"), {})
        with self.assertRaises(FrozenInstanceError):
            rule.rule_id = "changed"  # type: ignore[misc]

    def test_11_log_parser_multiword_space_field_and_varying_prefix(self) -> None:
        synth = LogParserSynthesizer()
        samples = [
            "alpha [user alice] OK",
            "beta [user bob smith] OK",
        ]
        expected = [
            {"ev": "alpha", "msg": "user alice"},
            {"ev": "beta", "msg": "user bob smith"},
        ]
        rule = synth.synthesize_regex_parser(samples, expected)
        self.assertIsNotNone(rule)
        fn = _exec_fn(rule.extractor_code, "parse_log_entry")
        parsed = fn("gamma [user charlie brown] OK")
        self.assertEqual(parsed["ev"], "gamma")
        self.assertEqual(parsed["msg"], "user charlie brown")

    def test_27_log_parser_trailing_multiword_empty_suffix_bug(self) -> None:
        # Bug yang sudah diperbaiki (2026-11-20): bidang terakhir multi-kata
        # tanpa sufiks kini ditangkap rakus (?P<key>.+) sampai akhir baris;
        # pola lama (?P<key>.+?).*?$ menelan semua kecuali 1 karakter.
        synth = LogParserSynthesizer()
        samples = [
            "alpha event: user alice logged in",
            "beta event: user bob smith logged out",
        ]
        expected = [
            {"ev": "alpha", "msg": "user alice logged in"},
            {"ev": "beta", "msg": "user bob smith logged out"},
        ]
        rule = synth.synthesize_regex_parser(samples, expected)
        self.assertIsNotNone(rule)
        fn = _exec_fn(rule.extractor_code, "parse_log_entry")
        parsed = fn("gamma event: user charlie connected")
        self.assertEqual(parsed["msg"], "user charlie connected")

    def test_12_log_parser_missing_value_in_first_sample_returns_none(self) -> None:
        synth = LogParserSynthesizer()
        rule = synth.synthesize_regex_parser(
            ["only-prefix-here"],
            [{"code": "999"}],
        )
        self.assertIsNone(rule)

    def test_13_log_parser_increments_rule_ids_uniquely(self) -> None:
        synth = LogParserSynthesizer()
        r1 = synth.synthesize_regex_parser(["id=1"], [{"id": "1"}])
        r2 = synth.synthesize_regex_parser(["k=2"], [{"k": "2"}])
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertNotEqual(r1.rule_id, r2.rule_id)
        self.assertEqual(len(synth.known_rules), 2)

    # --- 4. net_client_synth ---

    def test_14_net_client_post_sends_json_body_and_custom_headers(self) -> None:
        synth = NetClientSynthesizer()
        rule = synth.synthesize_json_client(
            "http://127.0.0.1:9/post",
            method="post",
            expected_keys=["id"],
            max_retries=1,
            func_name="post_item",
        )
        self.assertIsInstance(rule, ClientRule)
        with self.assertRaises(FrozenInstanceError):
            rule.rule_id = "mutated"  # type: ignore[misc]
        fn = _exec_fn(rule.client_code, "post_item")

        captured: dict = {}

        class _Resp:
            status = 201
            def read(self) -> bytes:
                return b'{"id": 42}'
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        def fake_open(req, timeout=None):
            captured["method"] = req.get_method()
            captured["data"] = req.data
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return _Resp()

        caller_headers = {"X-Trace": "abc"}
        with mock.patch("urllib.request.urlopen", side_effect=fake_open):
            out = fn(params={"x": 1}, headers=caller_headers)
        self.assertEqual(out, {"id": 42})
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(json.loads(captured["data"].decode("utf-8")), {"x": 1})
        self.assertEqual(caller_headers, {"X-Trace": "abc"})

    def test_15_net_client_retries_transient_failure_then_succeeds(self) -> None:
        rule = NetClientSynthesizer().synthesize_json_client(
            "http://127.0.0.1:9/retry", max_retries=3, timeout_seconds=2.5
        )
        fn = _exec_fn(rule.client_code, "query_api_endpoint")

        class _OkResp:
            status = 200
            def read(self) -> bytes:
                return b'{"ok": true}'
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        calls = {"n": 0}

        def flaky_open(req, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise OSError("transient connection reset")
            return _OkResp()

        with mock.patch("urllib.request.urlopen", side_effect=flaky_open), \
             mock.patch("time.sleep") as mock_sleep:
            res = fn()
        self.assertEqual(res, {"ok": True})
        self.assertEqual(calls["n"], 3)
        self.assertEqual([c.args[0] for c in mock_sleep.call_args_list], [0.5, 1.0])

    def test_16_net_client_non_200_and_malformed_json_raise_runtime_error(self) -> None:
        rule = NetClientSynthesizer().synthesize_json_client("http://127.0.0.1:9/err", max_retries=2)
        fn = _exec_fn(rule.client_code, "query_api_endpoint")

        class _BadStatusResp:
            status = 503
            def read(self) -> bytes:
                return b"{}"
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        with mock.patch("urllib.request.urlopen", return_value=_BadStatusResp()), mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                fn()
        self.assertIn("HTTP error status 503", str(ctx.exception))

        class _BadJsonResp:
            status = 200
            def read(self) -> bytes:
                return b"{not-json"
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        with mock.patch("urllib.request.urlopen", return_value=_BadJsonResp()), mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError):
                fn()

    # --- 5. process_sentinel ---

    def test_17_process_sentinel_missing_proc_dir_fails_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = ProcessSentinel(str(Path(tmp) / "missing_proc"))
            self.assertFalse(sentinel.is_available())
            self.assertEqual(sentinel.scan_active_python_processes(), [])
            load = sentinel.audit_system_load()
            self.assertEqual(load["load_1m"], 0.0)
            self.assertEqual(load["active_python_processes"], 0)
            self.assertEqual(load["top_processes"], [])

    def test_18_process_sentinel_parses_nested_parens_nul_cmdline_and_sorts_rss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root = Path(tmp)
            (proc_root / "version").write_text("Linux version 6.0\n", encoding="utf-8")
            (proc_root / "loadavg").write_text("1.25 0.80 0.50 1/100 999\n", encoding="utf-8")
            _make_fake_proc_entry(
                proc_root, 101, comm="python3 (w1)", rss_pages=100, cmdline=b"python3\x00-m\x00ace\x00"
            )
            _make_fake_proc_entry(
                proc_root, 102, comm="python3", rss_pages=512, cmdline=b""
            )
            _make_fake_proc_entry(
                proc_root, 103, comm="python3-a", rss_pages=256, cmdline=b"python3\x00a.py"
            )
            _make_fake_proc_entry(
                proc_root, 104, comm="python3-b", rss_pages=400, cmdline=b"python3\x00b.py"
            )
            _make_fake_proc_entry(
                proc_root, 105, comm="bash", rss_pages=999, cmdline=b"/bin/bash"
            )

            sentinel = ProcessSentinel(str(proc_root))
            self.assertTrue(sentinel.is_available())
            p101 = sentinel.get_process_info(101)
            self.assertIsInstance(p101, ProcessReport)
            self.assertEqual(p101.name, "python3 (w1)")
            self.assertEqual(p101.command_line, "python3 -m ace")
            p102 = sentinel.get_process_info(102)
            self.assertEqual(p102.command_line, "python3")
            with self.assertRaises(FrozenInstanceError):
                p101.pid = 0  # type: ignore[misc]

            load = sentinel.audit_system_load()
            self.assertEqual(load["load_1m"], 1.25)
            self.assertEqual(load["active_python_processes"], 4)
            self.assertEqual(len(load["top_processes"]), 3)
            self.assertEqual([p["pid"] for p in load["top_processes"]], [102, 104, 103])

    def test_19_process_sentinel_corrupt_stat_and_corrupt_loadavg_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc_root = Path(tmp)
            (proc_root / "version").write_text("Linux\n", encoding="utf-8")
            (proc_root / "loadavg").write_text("CORRUPT_LOAD\n", encoding="utf-8")
            (proc_root / "201").mkdir()
            (proc_root / "201" / "stat").write_text("broken-no-parens\n", encoding="utf-8")
            (proc_root / "202").mkdir()
            (proc_root / "202" / "stat").write_text("202 (python3) S only_two_fields\n", encoding="utf-8")

            sentinel = ProcessSentinel(str(proc_root))
            self.assertIsNone(sentinel.get_process_info(201))
            self.assertIsNone(sentinel.get_process_info(202))
            self.assertIsNone(sentinel.get_process_info(99999))
            load = sentinel.audit_system_load()
            self.assertEqual(load["load_1m"], 0.0)
            self.assertEqual(load["active_python_processes"], 0)

    # --- 6. system_tool_synth ---

    def test_20_system_tool_short_and_long_flags_and_empty_args(self) -> None:
        synth = SystemToolSynthesizer()
        rule = synth.synthesize_safe_executor("python3 -c", {"c": "str", "opt": "str"})
        self.assertIsInstance(rule, CommandRule)
        self.assertEqual(rule.command_template, "python3 -c")
        self.assertEqual(rule.allowed_args, ("c", "opt"))
        with self.assertRaises(FrozenInstanceError):
            rule.rule_id = "x"  # type: ignore[misc]

        rule_echo = synth.synthesize_safe_executor("echo", {})
        fn = _exec_fn(rule_echo.sanitizer_code, "safe_execute_command")
        # Single-char flag uses `-x`, multi-char uses `--flag`, empty dict runs bare command
        proc_empty = fn({})
        self.assertEqual(proc_empty.returncode, 0)
        proc_flags = fn({"v": "one", "long": "two"})
        self.assertEqual(proc_flags.returncode, 0)
        self.assertIn("-v one --long two", proc_flags.stdout)

    def test_21_system_tool_path_sanitizer_blocks_sibling_prefix_and_symlink_escape(self) -> None:
        synth = SystemToolSynthesizer()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            sibling = Path(tmp) / "ws_evil"
            root.mkdir()
            sibling.mkdir()
            (sibling / "secret.txt").write_text("nope", encoding="utf-8")
            (root / "escape_link").symlink_to(sibling / "secret.txt")

            fn = _exec_fn(synth.synthesize_path_sanitizer(str(root)), "sanitize_workspace_path")
            self.assertEqual(fn(""), root.resolve())
            self.assertEqual(fn("."), root.resolve())
            with self.assertRaises(PermissionError):
                fn("../ws_evil/secret.txt")
            with self.assertRaises(PermissionError):
                fn("escape_link")

    # --- 7. mission_integration ---

    def test_22_mission_integrator_executes_process_and_git_and_fallback_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "init"], cwd=tmp, check=True)

            bus = MissionBus(str(root / "bus.sqlite3"))
            integrator = RealWorldMissionIntegrator(bus, str(root))
            missions = integrator.generate_real_world_missions()
            self.assertEqual(len(missions), 3)

            # Jalankan semua 3 misi (log, process, git) berurutan + verifikasi artifact tertulis
            r1 = integrator.execute_real_world_mission()
            r2 = integrator.execute_real_world_mission()
            r3 = integrator.execute_real_world_mission()
            for r in (r1, r2, r3):
                self.assertEqual(r["status"], "COMPLETED")
                self.assertTrue(r["receipt"]["passed"])
                self.assertTrue((root / "evidence" / "real_world" / f"artifact_{r['mission_id']}.json").is_file())

            # Misi family khusus di luar log/process/git tetap selesai aman
            bus.create_mission(
                goal="Custom family check",
                hypothesis="Fallback branch",
                task_family_ids=["custom_unknown_family"],
                inputs=[{"path": ".", "hash": "0" * 64}],
                budget={"time_sec": 10.0, "max_candidates": 1},
                acceptance={"metric": "m", "threshold": 1.0, "comparator": "exact_match"},
                forbidden=[],
            )
            r4 = integrator.execute_real_world_mission()
            self.assertEqual(r4["status"], "COMPLETED")
            self.assertEqual(r4["receipt"], {"passed": True, "metric_achieved": 1.0})

    def test_23_data_wrangler_slice_variable_length_returns_fixed_width(self) -> None:
        """Kasus tepi: contoh slice dengan panjang output identik vs contoh tunggal."""
        rule = DataWranglerSynthesizer().synthesize_string_transform(
            [("ID-123-END", "123"), ("ID-456-END", "456")]
        )
        self.assertIsNotNone(rule)
        fn = _exec_fn(rule.transform_code, "transform_data_field")
        self.assertEqual(fn("ID-789-END"), "789")
        self.assertEqual(fn("SHORT"), "")

    def test_24_net_client_get_ignores_params_and_uses_default_headers(self) -> None:
        rule = NetClientSynthesizer().synthesize_json_client("http://127.0.0.1:9/get", method="GET")
        fn = _exec_fn(rule.client_code, "query_api_endpoint")
        seen: dict = {}

        class _Resp:
            status = 200
            def read(self) -> bytes:
                return b'{"alive": true}'
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        def fake_open(req, timeout=None):
            seen["method"] = req.get_method()
            seen["data"] = req.data
            seen["ua"] = req.get_header("User-agent")
            return _Resp()

        with mock.patch("urllib.request.urlopen", side_effect=fake_open):
            out = fn(params={"ignored": 1})
        self.assertEqual(out, {"alive": True})
        self.assertEqual(seen["method"], "GET")
        self.assertIsNone(seen["data"])
        self.assertEqual(seen["ua"], "ACE-Autonomous-Agent/2.0")

    def test_25_git_analyzer_missing_repo_raises_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist"
            analyzer = GitAnalyzerSynthesizer(str(missing))
            with self.assertRaises(FileNotFoundError):
                analyzer.get_recent_churn()

    def test_26_system_tool_rejects_unclosed_quote_in_base_command(self) -> None:
        with self.assertRaises(ValueError):
            SystemToolSynthesizer().synthesize_safe_executor('echo "unclosed', {})


if __name__ == "__main__":
    unittest.main()
