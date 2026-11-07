"""Autonomous PR Manager for ACE Code Agent.

Handles git branching, commits with verifiable author provenance,
and GitHub Pull Request creation with structured empirical receipts.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from .models import AutonomousPRMetadata, CodePatch, ImprovementHypothesis, ResearchProblem, WorktreeExecutionResult


class AutonomousPRManager:
    """Manages autonomous Git branching, atomic commits, and Pull Request creation."""

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
        target_branch: str = "main",
    ) -> AutonomousPRMetadata:
        """Constructs structured PR metadata and description markdown."""
        branch_name = f"ace-dev/{hypothesis.hypothesis_id}"
        title = f"ACE Autonomous Research: {problem.title}"

        body_markdown = (
            f"## Autonomous Research PR: {hypothesis.hypothesis_id}\n\n"
            f"**Author Provenance:** `{patch.author_provenance}`\n"
            f"**Execution ID:** `{exec_result.execution_id}`\n"
            f"**Timestamp:** `{exec_result.timestamp}`\n"
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
            f"### 3. Worktree Empirical Validation\n"
            f"- **Target File:** `{patch.target_file}`\n"
            f"- **AST Valid:** `{exec_result.ast_valid}`\n"
            f"- **Tests Passed:** `{exec_result.tests_passed}` | **Failed:** `{exec_result.tests_failed}`\n"
            f"- **Duration:** `{exec_result.test_duration_seconds}s`\n"
            f"- **Receipt Signature:** `{exec_result.receipt_signature}`\n\n"
            f"### 4. Governance & Safety Declarations\n"
            f"- **Release Gate:** `BLOCK_RELEASE` (Maintained)\n"
            f"- **Scientific Status:** `NOT_ASSESSED`\n"
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

    def create_git_branch_and_commit(
        self,
        pr_meta: AutonomousPRMetadata,
        patch: CodePatch,
    ) -> Tuple[bool, str]:
        """Creates branch and commits the patch with verified author identity."""
        try:
            # 1. Check current branch
            current_branch_res = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            base_branch = current_branch_res.stdout.strip()

            # 2. Create and checkout new branch
            subprocess.run(
                ["git", "checkout", "-b", pr_meta.branch_name],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            # 3. Apply changes to target file
            target_path = self.repo_root / patch.target_file
            if target_path.exists():
                orig = target_path.read_text(encoding="utf-8")
                target_path.write_text(orig + "\n" + patch.replacement_code_snippet, encoding="utf-8")

            # 4. Stage and commit
            subprocess.run(
                ["git", "add", patch.target_file],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            commit_msg = (
                f"{pr_meta.title}\n\n"
                f"{pr_meta.body_markdown}\n\n"
                f"X-ACE-Provenance: {pr_meta.merkle_proof_digest}"
            )

            commit_res = subprocess.run(
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

            # Get commit SHA
            sha_res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            pr_meta.commit_sha = sha_res.stdout.strip()

            # Return to base branch
            subprocess.run(
                ["git", "checkout", base_branch],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )

            return True, pr_meta.commit_sha
        except Exception as e:
            return False, f"Git commit failed: {str(e)}"
