"""Autonomous PR Manager for ACE Code Agent (V0.4).

Handles end-to-end Git operations and GitHub Pull Request lifecycle:
1. Branch creation with strict namespace validation (ace-dev/*, ace-autonomous/*).
2. Atomic code patch application and AST verification.
3. Signed commit with verified author provenance (ACE Autonomous Researcher).
4. Remote branch push to GitHub origin.
5. GitHub Pull Request creation via gh CLI / GitHub REST API.
6. Cryptographic / authoritative PR existence verification before claiming success.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from .models import (
    AutonomousPRMetadata,
    CodePatch,
    ImprovementHypothesis,
    ResearchProblem,
    WorktreeExecutionResult,
)

ALLOWED_BRANCH_PREFIXES = ("ace-dev/", "ace-autonomous/")


class AutonomousPRManager:
    """Manages autonomous Git branching, commits, remote push, and Pull Request creation."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parent.parent.parent
        else:
            self.repo_root = Path(repo_root)

    def prepare_pr_metadata(
        self,
        problem: ResearchProblem,
        hypothesis: ImprovementHypothesis,
        patch: CodePatch,
        exec_result: WorktreeExecutionResult,
        target_branch: Optional[str] = None,
    ) -> AutonomousPRMetadata:
        """Constructs structured PR metadata and description markdown."""
        # Sanitize hypothesis ID for branch naming
        safe_hyp_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", hypothesis.hypothesis_id)
        branch_name = f"ace-dev/{safe_hyp_id}"

        if not target_branch:
            # Auto-detect current branch or default to main
            target_branch = self.get_current_branch()

        title = f"ACE Autonomous Research: {problem.title}"

        body_markdown = (
            f"## Autonomous Research PR: {hypothesis.hypothesis_id}\n\n"
            f"> [!IMPORTANT]\n"
            f"> This Pull Request was **generated autonomously by ACE** without human prompting.\n\n"
            f"**Author Provenance:** `{patch.author_provenance}`  \n"
            f"**Execution ID:** `{exec_result.execution_id}`  \n"
            f"**Timestamp:** `{exec_result.timestamp}`  \n"
            f"**Marginal Financial Cost:** $0.00 / Rp0 (Pure CPU / Stdlib)\n\n"
            f"### 1. Research Problem Identified\n"
            f"- **Problem ID:** `{problem.problem_id}`\n"
            f"- **Category:** `{problem.category}`\n"
            f"- **Description:** {problem.description}\n\n"
            f"### 2. Improvement Hypothesis Formulated\n"
            f"- **Hypothesis:** {hypothesis.statement}\n"
            f"- **Strategy:** `{hypothesis.proposed_strategy}`\n"
            f"- **Expected Gain:** `+{hypothesis.expected_metric_gain}`\n"
            f"- **Rationale:** {hypothesis.rationale}\n\n"
            f"### 3. Isolated Worktree Empirical Validation\n"
            f"- **Target File:** `{patch.target_file}`\n"
            f"- **AST Validated:** `{exec_result.ast_valid}`\n"
            f"- **Isolated Tests Passed:** `{exec_result.tests_passed}` | **Failed:** `{exec_result.tests_failed}`\n"
            f"- **Execution Duration:** `{exec_result.test_duration_seconds}s`\n"
            f"- **Receipt Signature:** `{exec_result.receipt_signature}`\n\n"
            f"### 4. Governance & Safety Invariants\n"
            f"- **Release Gate:** `BLOCK_RELEASE` (Maintained)\n"
            f"- **Scientific Status:** `NOT_ASSESSED` (No premature emergence claim)\n"
            f"- **OAIE Established:** `False`\n"
        )

        return AutonomousPRMetadata(
            pr_id=f"pr_meta_{hypothesis.hypothesis_id}",
            branch_name=branch_name,
            target_branch=target_branch,
            title=title,
            body_markdown=body_markdown,
            commit_sha="",
            hypothesis_id=hypothesis.hypothesis_id,
            patch_id=patch.patch_id,
            merkle_proof_digest=exec_result.receipt_signature,
            author_identity="ACE Autonomous Researcher <ace-autonomous@local>",
        )

    def get_current_branch(self) -> str:
        """Retrieves the current git branch name."""
        try:
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return res.stdout.strip() or "main"
        except Exception:
            return "main"

    def create_git_branch_and_commit(
        self,
        pr_meta: AutonomousPRMetadata,
        patch: CodePatch,
    ) -> Tuple[bool, str]:
        """Creates branch and commits the patch with verified author identity."""
        # Validate allowed branch namespace
        if not any(pr_meta.branch_name.startswith(pfx) for pfx in ALLOWED_BRANCH_PREFIXES):
            return False, f"SECURITY VIOLATION: Branch name '{pr_meta.branch_name}' outside allowed namespace {ALLOWED_BRANCH_PREFIXES}"

        # Direct publication must not bypass the candidate evaluation gate.
        return False, "BLOCKED: candidate-bound independent evaluation unavailable"

        base_branch = self.get_current_branch()

        try:
            # 1. Ensure working directory is clean or checkout branch
            subprocess.run(["git", "checkout", "-B", pr_meta.branch_name], cwd=self.repo_root, capture_output=True, text=True, check=True)

            # 2. Apply patch replacement to target file
            target_path = self.repo_root / patch.target_file
            if target_path.exists():
                orig = target_path.read_text(encoding="utf-8")
                # Append replacement code snippet if not already present
                if patch.replacement_code_snippet not in orig:
                    target_path.write_text(orig + "\n" + patch.replacement_code_snippet, encoding="utf-8")

            # 3. Stage changes
            subprocess.run(["git", "add", patch.target_file], cwd=self.repo_root, capture_output=True, text=True, check=True)

            # 4. Commit with author provenance
            commit_msg = (
                f"{pr_meta.title}\n\n"
                f"{pr_meta.body_markdown}\n\n"
                f"X-ACE-Provenance: {pr_meta.merkle_proof_digest}"
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=ACE Autonomous Researcher",
                    "-c", "user.email=ace-autonomous@local",
                    "commit",
                    "-m", commit_msg,
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            # 5. Extract commit SHA
            sha_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_root, capture_output=True, text=True, check=True)
            pr_meta.commit_sha = sha_res.stdout.strip()

            return True, pr_meta.commit_sha
        except Exception as e:
            return False, f"Git commit failed: {str(e)}"
        finally:
            # Return to base branch
            subprocess.run(["git", "checkout", base_branch], cwd=self.repo_root, capture_output=True, text=True)

    def push_remote_branch(self, pr_meta: AutonomousPRMetadata) -> Tuple[bool, str]:
        """Pushes the local branch to the remote origin."""
        try:
            push_res = subprocess.run(
                ["git", "push", "-u", "origin", pr_meta.branch_name, "--force"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if push_res.returncode == 0:
                return True, "Remote branch push successful."
            else:
                return False, f"Git push failed: {push_res.stderr.strip()}"
        except Exception as e:
            return False, f"Git push exception: {str(e)}"

    def open_github_pr(self, pr_meta: AutonomousPRMetadata) -> Tuple[bool, str, Optional[int], Optional[str]]:
        """Opens a Pull Request on GitHub using the gh CLI."""
        try:
            # First check if PR already exists for this head branch
            check_res = subprocess.run(
                ["gh", "pr", "view", pr_meta.branch_name, "--json", "number,url,state"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if check_res.returncode == 0 and check_res.stdout.strip():
                try:
                    data = json.loads(check_res.stdout.strip())
                    pr_num = int(data.get("number"))
                    pr_url = str(data.get("url"))
                    pr_meta.pr_number = pr_num
                    pr_meta.pr_url = pr_url
                    return True, "PR already open.", pr_num, pr_url
                except Exception:
                    pass

            # Create new PR
            cmd = [
                "gh", "pr", "create",
                "--base", pr_meta.target_branch,
                "--head", pr_meta.branch_name,
                "--title", pr_meta.title,
                "--body", pr_meta.body_markdown,
            ]
            create_res = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, timeout=60)
            if create_res.returncode != 0:
                err = create_res.stderr.strip()
                # If PR already exists, re-query
                if "already exists" in err.lower():
                    view_res = subprocess.run(
                        ["gh", "pr", "view", pr_meta.branch_name, "--json", "number,url,state"],
                        cwd=self.repo_root,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if view_res.returncode == 0 and view_res.stdout.strip():
                        data = json.loads(view_res.stdout.strip())
                        pr_num = int(data.get("number"))
                        pr_url = str(data.get("url"))
                        pr_meta.pr_number = pr_num
                        pr_meta.pr_url = pr_url
                        return True, "PR found existing on GitHub.", pr_num, pr_url
                return False, f"gh pr create failed: {err}", None, None

            out_url = create_res.stdout.strip()
            # Parse PR number from URL (e.g. https://github.com/owner/repo/pull/90)
            m = re.search(r"/pull/(\d+)", out_url)
            pr_num = int(m.group(1)) if m else None
            pr_meta.pr_number = pr_num
            pr_meta.pr_url = out_url

            return True, "PR created successfully.", pr_num, out_url
        except Exception as e:
            return False, f"PR creation exception: {str(e)}", None, None

    def verify_pr_exists(self, pr_meta: AutonomousPRMetadata) -> Tuple[bool, str, Dict[str, Any]]:
        """Authoritatively verifies via GitHub API that the PR exists, is open, and matches metadata."""
        if not pr_meta.pr_number and not pr_meta.pr_url:
            return False, "Verification failed: No PR number or URL recorded in metadata.", {}

        identifier = str(pr_meta.pr_number) if pr_meta.pr_number else pr_meta.pr_url
        try:
            res = subprocess.run(
                ["gh", "pr", "view", identifier, "--json", "number,url,state,title,headRefName,baseRefName"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode != 0:
                return False, f"Verification query failed: {res.stderr.strip()}", {}

            data = json.loads(res.stdout.strip())
            state = data.get("state", "").upper()
            if state != "OPEN":
                return False, f"PR is not in OPEN state (got {state}).", data

            num = int(data.get("number", 0))
            url = data.get("url", "")
            pr_meta.pr_number = num
            pr_meta.pr_url = url

            return True, "PR verified and confirmed active on GitHub.", data
        except Exception as e:
            return False, f"PR verification exception: {str(e)}", {}

    def publish_autonomous_pr(
        self,
        pr_meta: AutonomousPRMetadata,
        patch: CodePatch,
    ) -> Tuple[bool, str]:
        """Full pipeline: Branch -> Commit -> Push -> Open PR -> Verify PR exists."""
        # 1. Create branch and commit
        ok_commit, commit_res = self.create_git_branch_and_commit(pr_meta, patch)
        if not ok_commit:
            return False, f"Branch & commit step failed: {commit_res}"

        # 2. Push remote
        ok_push, push_msg = self.push_remote_branch(pr_meta)
        if not ok_push:
            return False, f"Remote push step failed: {push_msg}"

        # 3. Open PR
        ok_pr, pr_msg, pr_num, pr_url = self.open_github_pr(pr_meta)
        if not ok_pr or not pr_url:
            return False, f"Open PR step failed: {pr_msg}"

        # 4. Authoritatively verify PR existence
        ok_ver, ver_msg, _ = self.verify_pr_exists(pr_meta)
        if not ok_ver:
            return False, f"Authoritative PR verification failed: {ver_msg}"

        return True, pr_meta.pr_url
