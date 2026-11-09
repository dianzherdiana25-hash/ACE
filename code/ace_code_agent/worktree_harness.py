"""ACE candidate intake gate (fail closed).

A git worktree and an ordinary subprocess are not an OS sandbox. Until an
independent, sealed evaluator is integrated, source patches may be parsed and
recorded but never executed or marked as capability improvements.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path, PurePosixPath
import time
from typing import List, Optional, Set, Tuple

from .models import CodePatch, WorktreeExecutionResult

PROTECTED_PATHS: Set[str] = {
    ".github/workflows",
    "checkpoints/self_dev/immutable_baseline.json",
    "checkpoints/self_dev/recovery_baseline.json",
    "code/ace_host_controller",
    "code/ace_autonomy",
}

FORBIDDEN_CALLS: Set[str] = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "open",
    "system",
    "popen",
    "fork",
    "kill",
}


class WorktreeHarness:
    """Fail-closed candidate intake. No untrusted source execution occurs here."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parent.parent.parent
        else:
            self.repo_root = Path(repo_root)

    def validate_patch_security(self, patch: CodePatch) -> Tuple[bool, str]:
        """Verify that patch does not touch protected governance paths or inject unsafe AST."""
        # 1. Check target path against protected governance paths
        target = patch.target_file
        if (not isinstance(target, str) or not target.startswith("code/") or
                not target.endswith(".py") or chr(92) in target or
                target.startswith("/") or ".." in PurePosixPath(target).parts):
            return False, "SECURITY VIOLATION: invalid candidate source path"
        for prot in PROTECTED_PATHS:
            if target == prot or target.startswith(prot + "/"):
                return False, f"SECURITY VIOLATION: Patch targets protected system path '{target}'"

        # 2. Check replacement code AST
        try:
            tree = ast.parse(patch.replacement_code_snippet)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                        return False, f"SECURITY VIOLATION: Forbidden function call '{func.id}'"
                    elif isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CALLS:
                        return False, f"SECURITY VIOLATION: Forbidden method call '{func.attr}'"
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Check for dangerous system imports
                    for alias in node.names:
                        if alias.name in ("os", "sys", "subprocess", "socket", "shutil"):
                            return False, f"SECURITY VIOLATION: Forbidden import '{alias.name}'"
        except Exception as e:
            return False, f"AST Syntax error in replacement snippet: {e}"

        return True, "Security validation passed."

    def execute_in_worktree(
        self,
        patch: CodePatch,
        test_commands: Optional[List[List[str]]] = None,
    ) -> WorktreeExecutionResult:
        """Static intake only; never execute model-produced code on an unsealed host.

        Importing a module is code execution, not an evidence-based behavioral test.
        Worktrees provide version-control isolation, NOT OS process containment.
        An actual evaluator must separately measure candidate and baseline on
        preregistered tasks, check regression and controls, and own the receipts
        before any future path can return ACCEPTED.
        """
        start_time = time.monotonic()
        allowed, reason = self.validate_patch_security(patch)
        decision = "INCONCLUSIVE" if allowed else "REJECTED"
        explanation = (
            "STAGED_ONLY_NOT_EXECUTED: no verified OS containment, connected "
            "behavioral test, candidate-vs-baseline measurement or independent "
            "evaluator receipt; import-only tests cannot authorize promotion."
            if allowed else reason
        )
        # SHA-256 is a local integrity checksum, NOT an evaluator signature.
        receipt = hashlib.sha256(
            f"{patch.patch_sha256}:{decision}:{explanation}".encode("utf-8")
        ).hexdigest()
        return WorktreeExecutionResult(
            execution_id=f"intake_{patch.patch_sha256[:16]}",
            patch_id=patch.patch_id,
            hypothesis_id=patch.hypothesis_id,
            worktree_path="",
            applied_cleanly=False,
            ast_valid=allowed,
            tests_passed=0,
            tests_failed=0 if allowed else 1,
            test_duration_seconds=round(time.monotonic() - start_time, 4),
            performance_metrics={
                "candidate_executed": 0.0,
                "behavioral_tests_executed": 0.0,
                "gain_measured": 0.0,
            },
            decision=decision,
            rejection_reason=explanation,
            receipt_signature=receipt,
            rollback_completed=True,
        )
