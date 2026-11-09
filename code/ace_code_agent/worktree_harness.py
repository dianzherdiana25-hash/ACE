"""Worktree Test Harness & Isolated Evaluator (V0.4).

Applies candidate patches strictly in an isolated execution sandbox,
verifies AST safety, executes regression tests inside the isolated workspace,
and guarantees fail-closed cleanup and rollback.
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
        # 1. Check target path against protected governance paths
        target = patch.target_file
        path = Path(target)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            return False, "SECURITY VIOLATION: Invalid target path"
        for prot in PROTECTED_PATHS:
            if path == Path(prot) or Path(prot) in path.parents:
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

    def _setup_isolated_workspace(self, prefix: str = "ace_worktree_") -> Tuple[Path, str]:
        """Creates an isolated execution sandbox via git worktree or deep sandbox copy."""
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        mode = "worktree"
        try:
            # Attempt git worktree creation at HEAD
            worktree_path = temp_dir / "repo"
            res = subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree_path), "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0 and worktree_path.exists():
                return worktree_path, "git_worktree"
        except Exception:
            pass

        # Fallback: Copy minimal execution tree to isolated directory
        mode = "copy_sandbox"
        for folder in ("code", "tools"):
            src_f = self.repo_root / folder
            dst_f = temp_dir / folder
            if src_f.exists():
                shutil.copytree(src_f, dst_f, dirs_exist_ok=True)
        return temp_dir, mode

    def _cleanup_isolated_workspace(self, workspace_path: Path, mode: str) -> None:
        """Cleans up the isolated workspace and detached git worktree."""
        try:
            if mode == "git_worktree":
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(workspace_path)],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            parent = workspace_path.parent if mode == "git_worktree" else workspace_path
            shutil.rmtree(parent, ignore_errors=True)
        except Exception:
            pass

    def execute_in_worktree(
        self,
        patch: CodePatch,
        test_commands: Optional[List[List[str]]] = None,
    ) -> WorktreeExecutionResult:
        """Creates an isolated workspace, applies patch to isolated source, runs tests, and cleans up."""
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

        # A worktree is not an OS security boundary. Fail closed until a
        # supervised sandbox with filesystem and credential isolation exists.
        return WorktreeExecutionResult(
            execution_id=execution_id, patch_id=patch.patch_id,
            hypothesis_id=patch.hypothesis_id, worktree_path="",
            applied_cleanly=False, ast_valid=False, tests_passed=0, tests_failed=1,
            test_duration_seconds=round(time.time() - start_time, 3),
            decision="REJECTED", rejection_reason="BLOCKED_ENVIRONMENT: OS containment unavailable",
            rollback_completed=True,
        )

        # Step 2: Create isolated execution workspace
        workspace_path, mode = self._setup_isolated_workspace()
        applied_cleanly = False
        ast_valid = False

        try:
            # Locate target file inside isolated workspace
            target_dest = workspace_path / patch.target_file
            target_dest.parent.mkdir(parents=True, exist_ok=True)

            orig_content = target_dest.read_text(encoding="utf-8") if target_dest.exists() else ""
            new_content = orig_content + "\n" + patch.replacement_code_snippet
            target_dest.write_text(new_content, encoding="utf-8")
            applied_cleanly = True

            # Validate AST of the patched file inside the isolated workspace
            ast.parse(new_content)
            ast_valid = True

            # Step 3: Run isolated verification tests inside the workspace
            tests_passed = 0
            tests_failed = 0

            # Default test command executes unit tests against the isolated workspace code
            isolated_env = dict(os.environ)
            isolated_env["PYTHONPATH"] = str(workspace_path / "code")
            isolated_env["PYTHONDONTWRITEBYTECODE"] = "1"

            if test_commands:
                cmds_to_run = test_commands
            else:
                # Default sanity test verifying that the target module imports cleanly
                mod_name = patch.target_file.replace("/", ".").replace(".py", "")
                if mod_name.startswith("code."):
                    mod_name = mod_name[5:]
                cmds_to_run = [
                    [sys.executable, "-c", f"import {mod_name}; print('{mod_name} import ok')"]
                ]

            for cmd in cmds_to_run:
                res = subprocess.run(
                    cmd,
                    cwd=str(workspace_path),
                    env=isolated_env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0:
                    tests_passed += 1
                else:
                    tests_failed += 1

            duration = round(time.time() - start_time, 3)
            decision = "ACCEPTED" if tests_failed == 0 and applied_cleanly and ast_valid else "REJECTED"
            reason = "Isolated tests passed cleanly." if decision == "ACCEPTED" else f"Isolated test command failed (failed: {tests_failed})."

            sig_payload = f"{execution_id}:{patch.patch_sha256}:{decision}:{duration}".encode("utf-8")
            receipt_sig = hashlib.sha256(sig_payload).hexdigest()

            return WorktreeExecutionResult(
                execution_id=execution_id,
                patch_id=patch.patch_id,
                hypothesis_id=patch.hypothesis_id,
                worktree_path=str(workspace_path),
                applied_cleanly=applied_cleanly,
                ast_valid=ast_valid,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                test_duration_seconds=duration,
                performance_metrics={
                    "duration_s": duration,
                    "tests_total": tests_passed + tests_failed,
                    "isolation_mode": mode,
                },
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
                worktree_path=str(workspace_path),
                applied_cleanly=applied_cleanly,
                ast_valid=ast_valid,
                tests_passed=0,
                tests_failed=1,
                test_duration_seconds=round(time.time() - start_time, 3),
                decision="REJECTED",
                rejection_reason=f"Isolated execution error: {str(e)}",
                rollback_completed=True,
            )
        finally:
            # Clean up the isolated workspace
            self._cleanup_isolated_workspace(workspace_path, mode)
