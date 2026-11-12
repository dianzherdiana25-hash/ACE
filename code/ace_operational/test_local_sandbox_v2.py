"""OMEGA-05 v2 tests: the v1 live acceptance list, run against the
unshare + pivot_root + seccomp(2) backend on hosts without bwrap.

The live class is gated by the same env flag as v1's, so CI on hosts
without namespace privileges still skips honestly; on this host it
must RUN and PASS — that is the stage-7 acceptance criterion.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from ace_operational.local_sandbox_v2 import LocalPythonSandboxV2


class TestSandboxV2Admission(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.evaluator = self.root / "evaluator"
        self.candidate.mkdir()
        self.evaluator.mkdir()
        (self.candidate / "m.py").write_text("def add(a, b): return a + b\n")
        (self.evaluator / "test_m.py").write_text(
            "import unittest\nfrom m import add\n"
            "class TestM(unittest.TestCase):\n"
            " def test_add(self): self.assertEqual(add(2, 3), 5)\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_candidate_cannot_share_evaluator_directory(self) -> None:
        receipt = LocalPythonSandboxV2().run_tests(self.candidate, self.candidate)
        self.assertEqual(receipt["status"], "BLOCKED_ENVIRONMENT")
        self.assertIn("distinct", receipt["error"])

    def test_invalid_budget_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LocalPythonSandboxV2().run_tests(
                self.candidate, self.evaluator, timeout_seconds=0)


@unittest.skipUnless(os.environ.get("ACE_RUN_SANDBOX_TESTS") == "1",
                     "requires real namespace-capable host")
class TestLiveSandboxV2(TestSandboxV2Admission):
    def test_real_isolation_and_behavior(self) -> None:
        receipt = LocalPythonSandboxV2().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "PASS", receipt)
        self.assertEqual(receipt["isolation"], "userns+pivot_root+seccomp(2)")
        self.assertTrue(all(receipt["isolation_checks"].values()))
        self.assertTrue(receipt["input_digests_unchanged"])
        self.assertFalse(receipt["independent_scientific_confirmation"])

    def test_real_test_failure(self) -> None:
        (self.candidate / "m.py").write_text("def add(a, b): return a - b\n")
        receipt = LocalPythonSandboxV2().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL", receipt)
        self.assertIn("AssertionError", receipt["stderr"])

    def test_output_flood_and_hang_are_stopped(self) -> None:
        for source, reason in [
            ("while True: print('x' * 1000, flush=True)\n", "OUTPUT_BUDGET"),
            ("while True: pass\n", "WALL_TIME_BUDGET"),
        ]:
            (self.candidate / "m.py").write_text(source)
            receipt = LocalPythonSandboxV2().run_tests(
                self.candidate, self.evaluator,
                timeout_seconds=0.4, output_limit_bytes=4096)
            self.assertEqual(receipt["status"], "STOPPED_BUDGET", receipt)
            self.assertEqual(receipt["stopped_reason"], reason, receipt)

    def test_no_tests_does_not_pass(self) -> None:
        (self.evaluator / "test_m.py").unlink()
        receipt = LocalPythonSandboxV2().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL", receipt)
        self.assertIn("NO_TESTS", receipt["stderr"])

    def test_candidate_early_successful_exit_does_not_pass(self) -> None:
        (self.candidate / "m.py").write_text("import os\nos._exit(0)\n")
        receipt = LocalPythonSandboxV2().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL", receipt)
        self.assertEqual(receipt["returncode"], 0)
        self.assertEqual(receipt["error"], "RUNNER_COMPLETION_NOT_OBSERVED")


if __name__ == "__main__":
    unittest.main()
