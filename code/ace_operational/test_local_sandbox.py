"""Sandbox admission, fail-closed behavior and opt-in real containment tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ace_operational.local_sandbox import LocalPythonSandbox, _tree_digest


class TestSandboxAdmission(unittest.TestCase):
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
            " def test_add(self): self.assertEqual(add(2, 3), 5)\n"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_symlink_and_hardlink_are_rejected(self) -> None:
        (self.candidate / "escape.py").symlink_to(self.evaluator / "test_m.py")
        with self.assertRaisesRegex(ValueError, "symlink"):
            _tree_digest(self.candidate)
        (self.candidate / "escape.py").unlink()
        os.link(self.evaluator / "test_m.py", self.candidate / "escape.py")
        with self.assertRaisesRegex(ValueError, "hardlinked"):
            _tree_digest(self.candidate)

    def test_missing_isolation_never_executes_candidate(self) -> None:
        runner = LocalPythonSandbox()
        with patch.object(runner, "_execute", return_value={
            "returncode": 1, "stdout": "", "stderr": "bwrap denied", "stopped_reason": "",
        }) as execute:
            receipt = runner.run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "BLOCKED_ENVIRONMENT")
        self.assertFalse(receipt["passed"])
        self.assertEqual(execute.call_count, 1)

    def test_failed_or_forged_success_output_is_not_accepted(self) -> None:
        runner = LocalPythonSandbox()
        probe = {"returncode": 0, "stdout": json.dumps({"sockets_denied": True}), "stopped_reason": ""}
        failed = {"returncode": 1, "stdout": '{"status":"PASS"}', "stderr": "failed", "stopped_reason": ""}
        with patch.object(runner, "_execute", side_effect=[probe, failed]):
            receipt = runner.run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertFalse(receipt["passed"])

    def test_candidate_cannot_share_evaluator_directory(self) -> None:
        receipt = LocalPythonSandbox().run_tests(self.candidate, self.candidate)
        self.assertEqual(receipt["status"], "BLOCKED_ENVIRONMENT")
        self.assertIn("distinct", receipt["error"])

    def test_invalid_budget_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LocalPythonSandbox().run_tests(self.candidate, self.evaluator, timeout_seconds=0)


@unittest.skipUnless(os.environ.get("ACE_RUN_SANDBOX_TESTS") == "1", "requires real namespace-capable host")
class TestLiveSandbox(TestSandboxAdmission):
    def test_real_isolation_and_behavior(self) -> None:
        receipt = LocalPythonSandbox().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "PASS", receipt)
        self.assertTrue(all(receipt["isolation_checks"].values()))
        self.assertTrue(receipt["input_digests_unchanged"])
        self.assertFalse(receipt["independent_scientific_confirmation"])

    def test_real_test_failure(self) -> None:
        (self.candidate / "m.py").write_text("def add(a, b): return a - b\n")
        receipt = LocalPythonSandbox().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL", receipt)
        self.assertIn("AssertionError", receipt["stderr"])

    def test_output_flood_and_hang_are_stopped(self) -> None:
        for source, reason in [
            ("while True: print('x' * 1000, flush=True)\n", "OUTPUT_BUDGET"),
            ("while True: pass\n", "WALL_TIME_BUDGET"),
        ]:
            (self.candidate / "m.py").write_text(source)
            receipt = LocalPythonSandbox().run_tests(
                self.candidate, self.evaluator, timeout_seconds=0.4, output_limit_bytes=4096,
            )
            self.assertEqual(receipt["status"], "STOPPED_BUDGET", receipt)
            self.assertEqual(receipt["stopped_reason"], reason, receipt)

    def test_no_tests_does_not_pass(self) -> None:
        (self.evaluator / "test_m.py").unlink()
        receipt = LocalPythonSandbox().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL", receipt)
        self.assertIn("NO_TESTS", receipt["stderr"])

    def test_candidate_early_successful_exit_does_not_pass(self) -> None:
        (self.candidate / "m.py").write_text("import os\nos._exit(0)\n")
        receipt = LocalPythonSandbox().run_tests(self.candidate, self.evaluator)
        self.assertEqual(receipt["status"], "FAIL", receipt)
        self.assertEqual(receipt["returncode"], 0)
        self.assertEqual(receipt["error"], "RUNNER_COMPLETION_NOT_OBSERVED")


if __name__ == "__main__":
    unittest.main()
