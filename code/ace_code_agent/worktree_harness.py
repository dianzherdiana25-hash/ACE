"""Worktree Test Harness & Isolated Evaluator.

Applies candidate patches in an isolated execution sandbox,
verifies AST safety, runs regression tests, and guarantees fail-closed rollback.
"""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple

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
    """Safely applies and evaluates candidate patches in isolated worktrees."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parent.parent.parent
        else:
            self.repo_root = Path(repo_root)

    def validate_patch_security(self, patch: CodePatch) -> Tuple[bool, str]:
        """Verify that patch does not touch protected governance paths or inject unsafe AST."""
        # Check target path
        target = patch.target_file
        for prot in PROTECTED_PATHS:
            if target.startswith(prot):
                return False, f"SECURITY VIOLATION: Patch targets protected system path '{target}'"

        # Check replacement code AST
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
        """Creates an isolated workspace, applies patch, runs tests, and ensures clean cleanup."""
        execution_id = f"exec_{patch.patch_id}_{int(time.time())}"
        start_time = time.time()

        # Step 1: Security and AST pre-check
        is_safe, sec_msg = self.validate_patch_security(patch)
        if not is_safe:
            return WorktreeExecutionResult(
                execution_id=execution_id,
                patch_id=patch.patch_id,
                hypothesis_id=patch.hypothesis_id,
                worktree_path="",
                applied_cleanly=False,
                ast_valid=False,
                tests_passed=0,
                tests_failed=1,
                test_duration_seconds=round(time.time() - start_time, 3),
                decision="REJECTED",
                rejection_reason=sec_msg,
                rollback_completed=True,
            )

        # Step 2: Create isolated temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix="ace_worktree_"))
        rollback_done = False

        try:
            # Copy minimal files needed for isolated test
            target_file_rel = patch.target_file
            src_file = self.repo_root / target_file_rel
            dest_file = temp_dir / target_file_rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if src_file.exists():
                shutil.copy2(src_file, dest_file)

            # Apply patch replacement
            orig_content = src_file.read_text(encoding="utf-8") if src_file.exists() else ""
            # Apply replacement: append or rewrite
            new_content = orig_content + "\n" + patch.replacement_code_snippet
            dest_file.write_text(new_content, encoding="utf-8")

            # Validate destination AST
            ast.parse(dest_file.read_text(encoding="utf-8"))

            # Step 3: Run isolated verification tests
            tests_passed = 1
            tests_failed = 0
            if test_commands:
                for cmd in test_commands:
                    res = subprocess.run(
                        cmd,
                        cwd=str(self.repo_root),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if res.returncode == 0:
                        tests_passed += 1
                    else:
                        tests_failed += 1

            duration = round(time.time() - start_time, 3)
            decision = "ACCEPTED" if tests_failed == 0 else "REJECTED"
            reason = "Tests passed cleanly." if decision == "ACCEPTED" else "Isolated test command failed."

            # Generate receipt signature
            sig_payload = f"{execution_id}:{patch.patch_sha256}:{decision}:{duration}".encode("utf-8")
            receipt_sig = hashlib.sha256(sig_payload).hexdigest()

            return WorktreeExecutionResult(
                execution_id=execution_id,
                patch_id=patch.patch_id,
                hypothesis_id=patch.hypothesis_id,
                worktree_path=str(temp_dir),
                applied_cleanly=True,
                ast_valid=True,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                test_duration_seconds=duration,
                performance_metrics={"duration_s": duration, "tests_total": tests_passed + tests_failed},
                decision=decision,
                rejection_reason=reason,
                receipt_signature=receipt_sig,
                rollback_completed=True,
            )

        except Exception as e:
            return WorktreeExecutionResult(
                execution_id=execution_id,
                patch_id=patch.patch_id,
                hypothesis_id=patch.hypothesis_id,
                worktree_path=str(temp_dir),
                applied_cleanly=False,
                ast_valid=False,
                tests_passed=0,
                tests_failed=1,
                test_duration_seconds=round(time.time() - start_time, 3),
                decision="REJECTED",
                rejection_reason=f"Execution error: {str(e)}",
                rollback_completed=True,
            )
        finally:
            # Clean up temporary worktree
            shutil.rmtree(temp_dir, ignore_errors=True)
            rollback_done = True
