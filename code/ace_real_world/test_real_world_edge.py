"""Edge-case tests for ace_real_world synthesizers and mission integration (M4)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ace_mission.bus import MissionBus
from ace_real_world.data_wrangler_synth import DataWranglerSynthesizer
from ace_real_world.git_analyzer_synth import GitAnalyzerSynthesizer
from ace_real_world.log_parser_synth import LogParserSynthesizer
from ace_real_world.mission_integration import RealWorldMissionIntegrator
from ace_real_world.net_client_synth import NetClientSynthesizer
from ace_real_world.process_sentinel import ProcessSentinel
from ace_real_world.system_tool_synth import SystemToolSynthesizer


class TestRealWorldEdge(unittest.TestCase):
    def test_01_log_parser_empty_inputs_return_none(self) -> None:
        synth = LogParserSynthesizer()
        self.assertIsNone(synth.synthesize_regex_parser([], []))
        self.assertIsNone(synth.synthesize_regex_parser(["a"], []))

    def test_02_log_parser_mismatched_field_value_returns_none(self) -> None:
        synth = LogParserSynthesizer()
        rule = synth.synthesize_regex_parser(
            ["2026-11-17T00:00:00Z OK 200", "DIFFERENT FORMAT LINE"],
            [{"code": "200"}, {"code": "999"}],
        )
        self.assertIsNone(rule)

    def test_03_log_parser_custom_func_name_executes(self) -> None:
        synth = LogParserSynthesizer()
        samples = ["id=10 status=OK", "id=20 status=FAIL"]
        expected = [{"id": "10", "status": "OK"}, {"id": "20", "status": "FAIL"}]
        rule = synth.synthesize_regex_parser(samples, expected, func_name="parse_custom")
        self.assertIsNotNone(rule)
        scope = {}
        exec(rule.extractor_code, scope)
        self.assertEqual(scope["parse_custom"]("id=30 status=WARN")["id"], "30")

    def test_04_system_tool_empty_base_command_raises(self) -> None:
        synth = SystemToolSynthesizer()
        with self.assertRaises(ValueError):
            synth.synthesize_safe_executor("   ", {"arg": "str"})

    def test_05_system_tool_blocks_all_forbidden_metacharacters(self) -> None:
        synth = SystemToolSynthesizer()
        rule = synth.synthesize_safe_executor("echo", {"msg": "str"})
        scope = {}
        exec(rule.sanitizer_code, scope)
        fn = scope["safe_execute_command"]
        for bad in ("a;b", "a|b", "a&b", "a>b", "a<b", "$(id)", "`id`", "a\nb", "a\rb"):
            with self.assertRaises(ValueError):
                fn({"msg": bad})

    def test_06_system_tool_safe_exec_echo_succeeds(self) -> None:
        synth = SystemToolSynthesizer()
        rule = synth.synthesize_safe_executor("echo", {"n": "str"})
        scope = {}
        exec(rule.sanitizer_code, scope)
        proc = scope["safe_execute_command"]({"m": "hello"})
        self.assertEqual(proc.returncode, 0)
        self.assertIn("hello", proc.stdout)

    def test_07_system_tool_path_sanitizer_allows_inside_root(self) -> None:
        synth = SystemToolSynthesizer()
        with tempfile.TemporaryDirectory() as tmp:
            code = synth.synthesize_path_sanitizer(tmp)
            scope = {}
            exec(code, scope)
            res = scope["sanitize_workspace_path"]("sub/file.txt")
            self.assertTrue(str(res).startswith(str(Path(tmp).resolve())))

    def test_08_system_tool_path_sanitizer_blocks_traversal_and_prefix_escape(self) -> None:
        synth = SystemToolSynthesizer()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            root.mkdir()
            code = synth.synthesize_path_sanitizer(str(root))
            scope = {}
            exec(code, scope)
            fn = scope["sanitize_workspace_path"]
            with self.assertRaises(PermissionError):
                fn("../outside.txt")
            with self.assertRaises(PermissionError):
                fn("/etc/passwd")

    def test_09_data_wrangler_empty_examples_returns_none(self) -> None:
        self.assertIsNone(DataWranglerSynthesizer().synthesize_string_transform([]))

    def test_10_data_wrangler_identity_rule(self) -> None:
        rule = DataWranglerSynthesizer().synthesize_string_transform([("abc", "abc"), ("xyz", "xyz")])
        self.assertIsNotNone(rule)
        self.assertEqual(rule.operations, ("IDENTITY",))

    def test_11_data_wrangler_upper_lower_strip_rules(self) -> None:
        dw = DataWranglerSynthesizer()
        r_up = dw.synthesize_string_transform([("ab", "AB"), ("cd", "CD")])
        r_lo = dw.synthesize_string_transform([("AB", "ab"), ("CD", "cd")])
        r_st = dw.synthesize_string_transform([(" a ", "a"), (" b ", "b")])
        self.assertEqual(r_up.operations, ("UPPER",))
        self.assertEqual(r_lo.operations, ("LOWER",))
        self.assertEqual(r_st.operations, ("STRIP",))

    def test_12_data_wrangler_slice_fallback_rule(self) -> None:
        dw = DataWranglerSynthesizer()
        rule = dw.synthesize_string_transform([("PRE123POST", "123"), ("PRE456POST", "456")])
        self.assertIsNotNone(rule)
        scope = {}
        exec(rule.transform_code, scope)
        self.assertEqual(scope["transform_data_field"]("PRE789POST"), "789")

    def test_13_data_wrangler_unsolvable_examples_return_none(self) -> None:
        dw = DataWranglerSynthesizer()
        self.assertIsNone(dw.synthesize_string_transform([("alpha", "999"), ("beta", "000")]))

    def test_14_net_client_synthesizes_expected_keys_and_timeout(self) -> None:
        synth = NetClientSynthesizer()
        rule = synth.synthesize_json_client("http://127.0.0.1:9999/health", expected_keys=["status", "uptime"])
        self.assertIn("status", rule.client_code)
        self.assertIn("uptime", rule.client_code)
        self.assertIn("timeout=10.0", rule.client_code)

    def test_15_net_client_synthesized_code_with_expected_keys_is_valid_python(self) -> None:
        # Suspected bug in code/ace_real_world/net_client_synth.py:
        # When expected_keys is provided, the `# Verify schema keys` block is emitted at
        # 4-space indentation inside a 16-space `try:` block, causing SyntaxError on exec().
        synth = NetClientSynthesizer()
        rule = synth.synthesize_json_client("http://127.0.0.1:1/unreachable", expected_keys=["ok"])
        compile(rule.client_code, "<net_client>", "exec")

    def test_16_git_analyzer_on_non_git_tempdir_handles_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("x = 1\n# comment\n\n", encoding="utf-8")
            analyzer = GitAnalyzerSynthesizer(tmp)
            metrics = analyzer.compute_codebase_metrics()
            self.assertEqual(metrics.total_commits, 0)
            self.assertEqual(metrics.total_python_files, 0)
            self.assertEqual(metrics.total_loc, 0)

    def test_17_process_sentinel_availability_and_audit_shape(self) -> None:
        sentinel = ProcessSentinel()
        avail = sentinel.is_available()
        self.assertIsInstance(avail, bool)
        if avail:
            load = sentinel.audit_system_load()
            self.assertGreaterEqual(load["load_1m"], 0.0)

    def test_18_mission_integrator_unknown_mission_returns_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bus = MissionBus(str(Path(tmp) / "bus.sqlite3"))
            integrator = RealWorldMissionIntegrator(bus, tmp)
            res = integrator.execute_real_world_mission("nonexistent-mission-id")
            self.assertEqual(res["status"], "FAILED")

    def test_19_mission_integrator_generates_deterministic_three_missions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bus = MissionBus(str(Path(tmp) / "bus.sqlite3"))
            integrator = RealWorldMissionIntegrator(bus, tmp)
            missions = integrator.generate_real_world_missions()
            self.assertEqual(len(missions), 3)
            ids = [m["mission_id"] for m in missions]
            self.assertEqual(len(set(ids)), 3)

    def test_20_system_tool_rule_ids_increment_uniquely(self) -> None:
        synth = SystemToolSynthesizer()
        r1 = synth.synthesize_safe_executor("ls", {"a": "str"})
        r2 = synth.synthesize_safe_executor("pwd", {})
        self.assertNotEqual(r1.rule_id, r2.rule_id)


if __name__ == "__main__":
    unittest.main()
