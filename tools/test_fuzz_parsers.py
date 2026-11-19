"""Uji unit untuk harness fuzz ringan tools/fuzz_parsers.py."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tools.fuzz_parsers import (
    FUZZ_MATRIX_SCHEMA,
    STANDARD_ITERATIONS,
    STANDARD_SEEDS,
    collect_targets,
    run_fuzz,
    run_fuzz_matrix,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "fuzz_parsers.py"
FUZZ_DOC = REPO_ROOT / "tools" / "FUZZ_STANDARD.md"


class FuzzParsersTests(unittest.TestCase):
    """Memastikan harness fuzz deterministik dan bebas crash tak tertangani."""

    def test_run_fuzz_deterministic_and_zero_unhandled_crashes(self) -> None:
        r1 = run_fuzz(seed=20261117, iterations=120)
        r2 = run_fuzz(seed=20261117, iterations=120)
        self.assertEqual(r1, r2)
        self.assertTrue(r1["passed"], f"Ada crash fuzz: {r1}")
        self.assertEqual(r1["total_crashes"], 0)
        self.assertGreaterEqual(r1["target_count"], 33)

    def test_three_seeds_300_iterations_matrix_passes_with_zero_crashes(self) -> None:
        matrix = run_fuzz_matrix(seeds=STANDARD_SEEDS, iterations=STANDARD_ITERATIONS)
        self.assertEqual(matrix["schema"], FUZZ_MATRIX_SCHEMA)
        self.assertEqual(matrix["seeds"], [20261117, 20261118, 20261119])
        self.assertEqual(matrix["iterations_per_target"], 300)
        self.assertEqual(matrix["total_runs"], 3)
        self.assertEqual(matrix["total_crashes"], 0)
        self.assertGreaterEqual(matrix["target_count"], 33)
        self.assertTrue(matrix["passed"], f"Ada crash fuzz matrix: {matrix}")

    def test_collect_targets_includes_tools_and_safe_code_parsers(self) -> None:
        targets = collect_targets()
        expected = [
            "ace_mobile_dashboard.parse_logs_to_stories",
            "ace_ai_diagnostic.audit_consultations",
            "dashboard_state_build.rp_to_int",
            "code.ace_visual_bridge.cli.process",
            "code.ace_host_exchange.contracts.verify",
            "code.ace_autonomy.policy.BudgetCeiling",
            "code.ace_code_agent.read_failure_history",
            "code.ace_code_agent.verify_receipt",
            "code.ace_indo_nlp.syllabify_and_morphology",
            "pattern_distill.distill_evidence",
            "four_arm_report.analyze_four_arms",
            "kbm_pack_check.check_package",
            "kbm_pipeline.run_pipeline",
            "curriculum_gen.generate_curricula",
            "portability_pack.verify_bundle",
            "instance_kit.validate_isolation",
            "ruleset_readiness.check_repo_readiness",
            "opportunity_register.generate_proposals",
            "repo_status_dashboard.collect_and_render",
            "self_send_audit_view.inspect_audit_files",
            "repo_index.build_and_render",
            "daily_digest.build_daily_digest",
        ]
        for name in expected:
            self.assertIn(name, targets)
        self.assertTrue(FUZZ_DOC.is_file())

    def test_cli_exits_0_with_valid_json_report_and_rejects_bad_args(self) -> None:
        p_ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--seeds", "20261117,20261118", "--iterations", "50"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_ok.returncode, 0, p_ok.stderr)
        payload = json.loads(p_ok.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["seeds"], [20261117, 20261118])

        p_bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--iterations", "0"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad.returncode, 2)
        self.assertIn("Error:", p_bad.stderr)

        p_bad_seeds = subprocess.run(
            [sys.executable, str(SCRIPT), "--seeds", "abc"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad_seeds.returncode, 2)


class D1FuzzRegressionTests(unittest.TestCase):
    """Tes regresi deterministik untuk 10 crash parser yang ditemukan fuzzing D1."""

    def test_pattern_distill_huge_int_and_nondict_provenance(self) -> None:
        from tempfile import TemporaryDirectory

        from tools import pattern_distill

        self.assertIsNone(pattern_distill._as_optional_float(10**400))
        with TemporaryDirectory() as td:
            root = Path(td)
            ev = root / "ev.json"
            out = root / "staging.jsonl"
            ev.write_text(
                json.dumps(
                    [
                        {
                            "episode_id": "ep1",
                            "ratified": True,
                            "output": "def f(): return 1",
                            "score": 10**400,
                            "reasons": ["ok"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            out.write_text(json.dumps({"source_episode": "old", "provenance": "not-a-dict"}) + "\n", encoding="utf-8")
            rep = pattern_distill.distill_evidence([ev], output_path=out, append=True)
            self.assertEqual(rep["distilled_count"], 1)

    def test_four_arm_report_non_list_episodes_raises_contract_error(self) -> None:
        from tempfile import TemporaryDirectory

        from tools import four_arm_report

        with TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            p.write_text(json.dumps({"episodes": "not-a-list"}), encoding="utf-8")
            with self.assertRaises(four_arm_report.FourArmReportError):
                four_arm_report.analyze_four_arms([p])

    def test_curriculum_gen_non_list_task_shape_keywords(self) -> None:
        from tempfile import TemporaryDirectory

        from tools import curriculum_gen

        with TemporaryDirectory() as td:
            root = Path(td)
            cand = root / "cand.jsonl"
            cens = root / "cens.json"
            stag = root / "stag.jsonl"
            prop = root / "prop.jsonl"
            base = root / "base.jsonl"
            cand.write_text('{"id":"e1","kind":"episode","task_kind":"code","instruction":"x"}\n', encoding="utf-8")
            cens.write_text(json.dumps({"records": []}), encoding="utf-8")
            stag.write_text(json.dumps({"source_episode": "e1", "task_shape": {"keywords": 123}}) + "\n", encoding="utf-8")
            rep = curriculum_gen.generate_curricula(
                candidates_path=cand,
                census_path=cens,
                proposed_out=prop,
                baseline_out=base,
                staging_path=stag,
            )
            self.assertEqual(rep["emitted_count"], 1)

    def test_repo_index_broken_python_file_keeps_from_imports(self) -> None:
        from tempfile import TemporaryDirectory

        from tools import repo_index

        with TemporaryDirectory() as td:
            sub = Path(td)
            (sub / "broken.py").write_bytes(b"\xff\xfe\x00def broken(")
            idx = repo_index.build_repo_index(sub)
            self.assertEqual(idx["module_count"], 1)
            self.assertEqual(idx["python_modules"][0]["path"], "broken.py")
            md = repo_index.render_markdown_index(idx)
            self.assertIn("broken.py", md)

    def test_portability_pack_corrupt_archive_bool_bytes_and_non_str_path(self) -> None:
        import io
        import tarfile
        from tempfile import TemporaryDirectory

        from tools import portability_pack

        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                ti = tarfile.TarInfo("manifest.json")
                data = b"{}"
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
            arc = root / "trunc.tar.gz"
            arc.write_bytes(buf.getvalue()[: max(1, len(buf.getvalue()) // 2)])
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.verify_bundle(arc)

            bdir = root / "bdir"
            bdir.mkdir()
            (bdir / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema": portability_pack.SCHEMA_VERSION,
                        "files": [{"path": None, "bytes": True, "sha256": "abc"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(portability_pack.PortabilityPackError):
                portability_pack.verify_bundle(bdir)

    def test_instance_kit_nul_byte_records_structured_violation(self) -> None:
        from tools import instance_kit

        res = instance_kit.validate_isolation(
            [
                {
                    "schema": instance_kit.SCHEMA_VERSION,
                    "instance_id": "inst-nul",
                    "allowed_root": "/tmp/a\x00b",
                    "directories": {
                        "workspace_dir": "/tmp/w\x00x",
                        "store_dir": "/tmp/s",
                        "cache_dir": "/tmp/c",
                        "log_dir": "/tmp/l",
                    },
                    "ports": {"api": 8080},
                    "lock_namespace": "lk",
                }
            ]
        )
        kinds = {v["kind"] for v in res["violations"]}
        self.assertIn("invalid_path_nul_byte", kinds)

    def test_ruleset_readiness_malformed_approval_count_handled(self) -> None:
        from tools import ruleset_readiness

        rep = ruleset_readiness.evaluate_readiness(
            repo="owner/repo",
            protection={"required_pull_request_reviews": {"required_approving_review_count": "invalid"}},
            branch_rules=[],
        )
        self.assertFalse(rep["ready"])
        checks = {c["id"]: c for c in rep["checks"]}
        self.assertEqual(checks["approving_review_minimum"]["detail"], "required_approving_review_count=0")

    def test_repo_status_dashboard_malformed_panel_numbers_handled(self) -> None:
        from tempfile import TemporaryDirectory

        from tools import repo_status_dashboard

        with TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "docs").mkdir()
            (repo / "handover").mkdir()
            panel = repo / "panel.json"
            panel.write_text(
                json.dumps(
                    {
                        "file_count": "bad",
                        "valid_rows": None,
                        "invalid_rows": [],
                        "files": [{"path": "a.txt", "size": "oops", "sha256": 123}],
                        "totals_by_serial": {"s1": {"total_units": "nan", "row_count": None}},
                        "summary": {"completed": "x", "scheduled": {}, "overdue": "bad", "total_debt_files": None, "total_debt_bytes": []},
                        "serials": [{"id": "s1", "completed_count": "a", "total_chapters": None, "overdue_count": []}],
                        "programs": {"p1": {"file_count": "z", "total_bytes": None, "files": 123}},
                    }
                ),
                encoding="utf-8",
            )
            st = repo_status_dashboard.collect_repo_status(
                repo,
                stage_file=panel,
                heartbeat_file=panel,
                royalty_file=panel,
                schedule_file=panel,
                storage_debt_file=panel,
            )
            html = repo_status_dashboard.render_dashboard_html(st)
            self.assertIn("<!DOCTYPE html>", html)

    def test_kbm_pack_check_nul_cover_name_raises_contract_error(self) -> None:
        from tempfile import TemporaryDirectory

        from tools import kbm_pack_check

        with TemporaryDirectory() as td:
            with self.assertRaises(kbm_pack_check.KbmPackCheckError):
                kbm_pack_check.check_package(Path(td), cover_name="bad\x00cover.png")

    def test_opportunity_register_unhashable_attribution_handled(self) -> None:
        from tools import opportunity_register

        summary = opportunity_register.summarize_register(
            [{"origin_attribution": ["unhashable"]}],
            [],
        )
        self.assertEqual(summary["proposal_count"], 1)


if __name__ == "__main__":
    unittest.main()
