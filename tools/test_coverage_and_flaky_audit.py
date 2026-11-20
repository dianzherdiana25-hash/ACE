"""Unit & adversarial tests untuk tools/coverage_and_flaky_audit.py."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
import tempfile
import unittest
from unittest.mock import patch

from tools import coverage_and_flaky_audit as cfa


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestCoverageAndFlakyAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir(parents=True, exist_ok=True)

    def _seed_sample_repo(self) -> None:
        _write_text(self.root / "tools" / "__init__.py", "")
        _write_text(
            self.root / "tools" / "sample_tool.py",
            (
                "def used_fn():\n"
                "    return 1\n\n"
                "def unused_fn():\n"
                "    return 2\n\n"
                "def _private_fn():\n"
                "    return 3\n"
            ),
        )
        _write_text(
            self.root / "tools" / "test_sample_tool.py",
            (
                "import unittest\n"
                "from tools import sample_tool\n\n"
                "class TestSample(unittest.TestCase):\n"
                "    def test_used(self):\n"
                "        self.assertEqual(sample_tool.used_fn(), 1)\n"
            ),
        )

        _write_text(self.root / "code" / "pkg_demo" / "__init__.py", "")
        _write_text(
            self.root / "code" / "pkg_demo" / "alpha.py",
            (
                "class AlphaEngine:\n"
                "    def run(self):\n"
                "        return 'ok'\n\n"
                "async def async_step():\n"
                "    return True\n"
            ),
        )
        _write_text(
            self.root / "code" / "pkg_demo" / "beta_orphan.py",
            "def orphan_api():\n    return 42\n",
        )
        _write_text(
            self.root / "code" / "pkg_demo" / "test_alpha.py",
            (
                "import unittest\n"
                "from .alpha import AlphaEngine\n\n"
                "class TestAlpha(unittest.TestCase):\n"
                "    def test_engine(self):\n"
                "        self.assertEqual(AlphaEngine().run(), 'ok')\n"
            ),
        )

        # Forbidden modules containing side effects at import time: must NEVER be executed/imported
        _write_text(
            self.root / "code" / "ace_operational" / "evo0007_run.py",
            "raise RuntimeError('FORBIDDEN_MODULE_MUST_NOT_EXECUTE')\n",
        )
        _write_text(
            self.root / "code" / "ace_evaluator" / "sealed.py",
            "def judge():\n    return 1.0\n",
        )
        _write_text(
            self.root / "tools" / "memory_writeback.py",
            "def write_mem():\n    return True\n",
        )
        _write_text(
            self.root / "code" / "ace_operational" / "g3_instrument.py",
            "def score():\n    return 0\n",
        )

    def test_01_forbidden_paths_and_targets_detection(self):
        forbidden_paths = (
            "code/ace_operational/evo0007_run.py",
            "code/ace_evaluator/sealed.py",
            "code/ace_operational/abc_v3_scorer.py",
            "code/ace_operational/round2_instrument.py",
            "code/ace_operational/g1_instrument.py",
            "tools/memory_writeback.py",
            "code/ace_operational/cognitive_memory.py",
        )
        for p in forbidden_paths:
            with self.subTest(path=p):
                self.assertTrue(cfa.is_forbidden_path(p))

        self.assertFalse(cfa.is_forbidden_path("code/ace_mission/schema.py"))
        self.assertFalse(cfa.is_forbidden_path("tools/repo_index.py"))

        for bad_target in (
            "ace_operational.evo0007_run",
            "ace_evaluator.test_sealed_evaluator",
            "tools.memory_writeback",
            "ace_operational.g4_instrument",
            "tests/e2e/test_live.py",
        ):
            with self.subTest(target=bad_target):
                self.assertTrue(cfa.is_forbidden_target(bad_target))

    def test_02_ast_symbol_coverage_mapping_and_forbidden_isolation(self):
        self._seed_sample_repo()
        report = cfa.audit_symbol_coverage(self.root)
        summary = report["summary"]

        self.assertEqual(summary["total_source_modules"], 3)
        self.assertEqual(summary["modules_with_tests"], 2)
        self.assertEqual(summary["modules_without_tests"], 1)
        self.assertEqual(summary["forbidden_skipped_count"], 4)
        self.assertEqual(summary["total_public_symbols"], 5)
        self.assertEqual(summary["covered_public_symbols"], 2)
        self.assertEqual(summary["uncovered_public_symbols"], 3)
        self.assertEqual(summary["symbol_coverage_pct"], 40.0)
        self.assertEqual(report["uncovered_modules"], ["code/pkg_demo/beta_orphan.py"])

        by_path = {m["path"]: m for m in report["modules"]}
        self.assertEqual(by_path["tools/sample_tool.py"]["covered_symbols"], ["used_fn"])
        self.assertEqual(by_path["tools/sample_tool.py"]["uncovered_symbols"], ["unused_fn"])
        self.assertEqual(by_path["code/pkg_demo/alpha.py"]["covered_symbols"], ["AlphaEngine"])
        self.assertEqual(by_path["code/pkg_demo/alpha.py"]["uncovered_symbols"], ["async_step"])

    def test_03_ast_tolerates_syntax_errors_and_skips_symlinks(self):
        _write_text(self.root / "tools" / "broken.py", "def bad_syntax(:\n    pass\n")
        _write_text(self.root / "tools" / "ok.py", "def hello():\n    return 1\n")
        outside = Path(self.tmp.name) / "outside_secret.py"
        _write_text(outside, "def secret():\n    return 99\n")
        os.symlink(outside, self.root / "tools" / "link_secret.py")

        report = cfa.audit_symbol_coverage(self.root)
        paths = [m["path"] for m in report["modules"]]
        self.assertIn("tools/ok.py", paths)
        self.assertIn("tools/broken.py", paths)
        self.assertNotIn("tools/link_secret.py", paths)
        broken_rec = next(m for m in report["modules"] if m["path"] == "tools/broken.py")
        self.assertIsNotNone(broken_rec["parse_error"])

    def test_04_flaky_detector_passes_consistent_suite_clean_tree(self):
        self._seed_sample_repo()
        res = cfa.run_flaky_audit(self.root, ["tools.test_sample_tool", "pkg_demo.test_alpha"], runs=3)
        self.assertTrue(res["summary"]["passed"])
        self.assertEqual(res["summary"]["passing_targets"], 2)
        self.assertEqual(res["summary"]["flaky_targets"], 0)
        self.assertEqual(res["summary"]["dirty_targets"], 0)
        for item in res["targets"]:
            self.assertEqual(item["statuses"], ["PASS", "PASS", "PASS"])
            self.assertTrue(item["all_passed"])
            self.assertTrue(item["tree_clean"])
            self.assertFalse(item["flaky"])

    def test_05_flaky_detector_flags_intermittent_failure_and_dirty_tree(self):
        marker = self.root / ".counter.txt"
        marker.write_text("0", encoding="utf-8")
        _write_text(self.root / "tools" / "__init__.py", "")
        _write_text(
            self.root / "tools" / "test_intermittent.py",
            (
                "from pathlib import Path\n"
                "import unittest\n\n"
                f"MARKER = Path({repr(str(marker))})\n\n"
                "class TestIntermittent(unittest.TestCase):\n"
                "    def test_flaky(self):\n"
                "        n = int(MARKER.read_text()) + 1\n"
                "        MARKER.write_text(str(n))\n"
                "        self.assertGreaterEqual(n, 2)\n"
            ),
        )
        _write_text(
            self.root / "tools" / "test_dirty.py",
            (
                "from pathlib import Path\n"
                "import unittest\n\n"
                f"DIRTY_OUT = Path({repr(str(self.root / 'leaked_artifact.txt'))})\n\n"
                "class TestDirty(unittest.TestCase):\n"
                "    def test_leak(self):\n"
                "        DIRTY_OUT.write_text('oops')\n"
            ),
        )

        res = cfa.run_flaky_audit(self.root, ["tools.test_intermittent", "tools.test_dirty"], runs=3)
        self.assertFalse(res["summary"]["passed"])
        self.assertEqual(res["summary"]["flaky_targets"], 2)
        self.assertEqual(res["summary"]["dirty_targets"], 2)
        by_target = {t["target"]: t for t in res["targets"]}
        self.assertEqual(by_target["tools.test_intermittent"]["statuses"], ["FAIL", "PASS", "PASS"])
        self.assertTrue(by_target["tools.test_intermittent"]["flaky"])
        self.assertFalse(by_target["tools.test_dirty"]["tree_clean"])
        self.assertIn("leaked_artifact.txt", by_target["tools.test_dirty"]["dirty_entries"])

    def test_06_flaky_detector_handles_consistent_fail_and_timeout(self):
        outcomes = {"tools.test_fast": "PASS", "tools.test_always_fail": "FAIL",
                    "tools.test_slow": "TIMEOUT"}

        def fixture_process(argv, *, timeout, **kwargs):
            self.assertEqual(timeout, 0.1)
            outcome = outcomes[argv[-1]]
            if outcome == "TIMEOUT":
                raise TimeoutExpired(argv, timeout)
            return CompletedProcess(argv, int(outcome == "FAIL"), stdout="", stderr="Ran 1 test")

        with patch.object(cfa.subprocess, "run", side_effect=fixture_process) as fake_run:
            result = cfa.run_flaky_audit(self.root, list(outcomes), runs=20, timeout_sec=0.1)

        self.assertFalse(result["summary"]["passed"])
        self.assertEqual(fake_run.call_count, 60)
        for target in result["targets"]:
            expected = outcomes[target["target"]]
            with self.subTest(target=target["target"]):
                self.assertEqual(target["statuses"], [expected] * 20)
                self.assertEqual(target["timeout_runs"], 20 if expected == "TIMEOUT" else 0)
                self.assertEqual(target["consistent_fail"], expected != "PASS")

    def test_07_validation_rejects_bad_runs_timeout_forbidden_and_flags(self):
        self._seed_sample_repo()
        for kwargs in (
            {"targets": []},
            {"targets": ["tools.memory_writeback"]},
            {"targets": ["-h"]},
            {"targets": ["tools.test_sample_tool"], "runs": 0},
            {"targets": ["tools.test_sample_tool"], "runs": True},
            {"targets": ["tools.test_sample_tool"], "timeout_sec": float("nan")},
            {"targets": ["tools.test_sample_tool"], "timeout_sec": -1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    cfa.run_flaky_audit(self.root, **kwargs)

    def test_08_cli_markdown_json_output_and_exit_codes(self):
        self._seed_sample_repo()
        md_out = self.root / "out" / "audit.md"
        json_out = self.root / "out" / "audit.json"

        rc_cov = cfa.main(["--root", str(self.root), "--skip-flaky", "--output", str(md_out)])
        self.assertEqual(rc_cov, 0)
        md_text = md_out.read_text(encoding="utf-8")
        self.assertIn("Audit Cakupan Simbol & Deteksi Tes Flaky", md_text)
        self.assertIn("code/pkg_demo/beta_orphan.py", md_text)
        self.assertIn("code/ace_operational/evo0007_run.py", md_text)

        rc_json = cfa.main(
            [
                "--root",
                str(self.root),
                "--targets",
                "tools.test_sample_tool",
                "--runs",
                "2",
                "--format",
                "json",
                "--output",
                str(json_out),
            ]
        )
        self.assertEqual(rc_json, 0)
        parsed = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertEqual(parsed["schema"], cfa.AUDIT_SCHEMA)
        self.assertTrue(parsed["flaky"]["summary"]["passed"])

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_forbidden = cfa.main(
                ["--root", str(self.root), "--targets", "ace_evaluator.test_sealed_evaluator"]
            )
        self.assertEqual(rc_forbidden, 1)
        self.assertIn("wilayah terlarang", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
