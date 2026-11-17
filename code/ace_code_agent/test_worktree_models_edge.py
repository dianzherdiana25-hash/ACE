"""Edge-case tests for ace_code_agent WorktreeHarness and data models (M4)."""
from __future__ import annotations

import unittest
from pathlib import Path

from ace_code_agent.models import (
    AutonomousPRMetadata,
    CodePatch,
    ImprovementHypothesis,
    ResearchProblem,
    WorktreeExecutionResult,
)
from ace_code_agent.worktree_harness import FORBIDDEN_CALLS, PROTECTED_PATHS, WorktreeHarness


def _make_patch(target_file: str = "code/ace_demo/sample.py", snippet: str = "x = 1 + 2\n") -> CodePatch:
    return CodePatch(
        patch_id="p-1",
        hypothesis_id="h-1",
        target_file=target_file,
        diff_content="@@ -1 +1 @@\n-x = 0\n+x = 3\n",
        original_code_snippet="x = 0\n",
        replacement_code_snippet=snippet,
        patch_type="AST_TRANSFORMATION",
        author_provenance="TEST",
    )


class TestWorktreeModelsEdge(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = WorktreeHarness(Path("."))

    def test_01_valid_patch_passes_security_validation(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch())
        self.assertTrue(ok)
        self.assertIn("passed", msg.lower())

    def test_02_rejects_non_code_prefix(self) -> None:
        ok, _ = self.harness.validate_patch_security(_make_patch(target_file="tools/x.py"))
        self.assertFalse(ok)

    def test_03_rejects_non_py_extension(self) -> None:
        ok, _ = self.harness.validate_patch_security(_make_patch(target_file="code/ace_demo/readme.md"))
        self.assertFalse(ok)

    def test_04_rejects_backslash_path(self) -> None:
        ok, _ = self.harness.validate_patch_security(_make_patch(target_file="code\\ace_demo\\x.py"))
        self.assertFalse(ok)

    def test_05_rejects_absolute_path(self) -> None:
        ok, _ = self.harness.validate_patch_security(_make_patch(target_file="/code/ace_demo/x.py"))
        self.assertFalse(ok)

    def test_06_rejects_parent_traversal(self) -> None:
        ok, _ = self.harness.validate_patch_security(_make_patch(target_file="code/../tools/x.py"))
        self.assertFalse(ok)

    def test_07_rejects_protected_ace_autonomy_path(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch(target_file="code/ace_autonomy/policy.py"))
        self.assertFalse(ok)
        self.assertIn("protected", msg.lower())

    def test_08_rejects_protected_ace_host_controller_path(self) -> None:
        ok, _ = self.harness.validate_patch_security(_make_patch(target_file="code/ace_host_controller/main.py"))
        self.assertFalse(ok)

    def test_09_rejects_forbidden_eval_call(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch(snippet="y = eval('1+1')\n"))
        self.assertFalse(ok)
        self.assertIn("eval", msg)

    def test_10_rejects_forbidden_attribute_call_os_system(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch(snippet="x.system('ls')\n"))
        self.assertFalse(ok)
        self.assertIn("system", msg)

    def test_11_rejects_forbidden_import_subprocess(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch(snippet="import subprocess\n"))
        self.assertFalse(ok)
        self.assertIn("subprocess", msg)

    def test_12_rejects_forbidden_import_os(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch(snippet="import os\n"))
        self.assertFalse(ok)
        self.assertIn("os", msg)

    def test_13_rejects_syntax_error_snippet(self) -> None:
        ok, msg = self.harness.validate_patch_security(_make_patch(snippet="def broken(:\n"))
        self.assertFalse(ok)
        self.assertIn("Syntax error", msg)

    def test_14_execute_in_worktree_valid_returns_inconclusive_never_accepted(self) -> None:
        res = self.harness.execute_in_worktree(_make_patch(snippet="def f(a):\n    return a + 1\n"))
        self.assertEqual(res.decision, "INCONCLUSIVE")
        self.assertTrue(res.ast_valid)
        self.assertFalse(res.applied_cleanly)
        self.assertEqual(res.performance_metrics["candidate_python_executed"], 0.0)
        self.assertEqual(res.performance_metrics["independent_confirmation"], 0.0)
        self.assertEqual(len(res.receipt_signature), 64)

    def test_15_execute_in_worktree_rejected_sets_failed_count(self) -> None:
        res = self.harness.execute_in_worktree(_make_patch(snippet="import socket\n"))
        self.assertEqual(res.decision, "REJECTED")
        self.assertFalse(res.ast_valid)
        self.assertEqual(res.tests_failed, 1)

    def test_16_execute_in_worktree_handles_unsupported_ast_gracefully(self) -> None:
        res = self.harness.execute_in_worktree(_make_patch(snippet="async def g():\n    yield 1\n"))
        self.assertEqual(res.decision, "INCONCLUSIVE")
        self.assertIn("STAGED_ONLY_NOT_EXECUTED", res.rejection_reason)

    def test_17_code_patch_sha256_deterministic_and_roundtrip(self) -> None:
        p1 = _make_patch()
        p2 = _make_patch()
        self.assertEqual(p1.patch_sha256, p2.patch_sha256)
        restored = CodePatch.from_dict(p1.to_dict())
        self.assertEqual(restored.patch_sha256, p1.patch_sha256)

    def test_18_research_problem_roundtrip_and_timestamp(self) -> None:
        rp = ResearchProblem(
            problem_id="rp-1",
            category="ALGORITHMIC_GAP",
            title="Test",
            description="Desc",
            target_files=["code/a.py"],
        )
        self.assertTrue(rp.detected_timestamp.endswith("Z"))
        self.assertEqual(ResearchProblem.from_dict(rp.to_dict()).problem_id, "rp-1")

    def test_19_improvement_hypothesis_roundtrip(self) -> None:
        ih = ImprovementHypothesis(
            hypothesis_id="h-1",
            problem_id="rp-1",
            statement="S",
            proposed_strategy="AST",
            expected_metric_gain=0.1,
            target_module="code/a.py",
            rationale="R",
        )
        self.assertEqual(ImprovementHypothesis.from_dict(ih.to_dict()).hypothesis_id, "h-1")

    def test_20_worktree_execution_result_roundtrip(self) -> None:
        wer = WorktreeExecutionResult(
            execution_id="e-1",
            patch_id="p-1",
            hypothesis_id="h-1",
            worktree_path="",
            applied_cleanly=False,
            ast_valid=True,
            tests_passed=0,
            tests_failed=0,
            test_duration_seconds=0.01,
        )
        self.assertEqual(WorktreeExecutionResult.from_dict(wer.to_dict()).decision, "REJECTED")

    def test_21_autonomous_pr_metadata_roundtrip(self) -> None:
        meta = AutonomousPRMetadata(
            pr_id="pr-1",
            branch_name="ace-auto/1",
            target_branch="main",
            title="T",
            body_markdown="B",
            commit_sha="deadbeef",
            hypothesis_id="h-1",
            patch_id="p-1",
            merkle_proof_digest="00",
            author_identity="ACE",
        )
        self.assertEqual(AutonomousPRMetadata.from_dict(meta.to_dict()).commit_sha, "deadbeef")

    def test_22_protected_constants_non_empty(self) -> None:
        self.assertIn("eval", FORBIDDEN_CALLS)
        self.assertIn("code/ace_autonomy", PROTECTED_PATHS)


if __name__ == "__main__":
    unittest.main()
