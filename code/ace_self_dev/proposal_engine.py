"""Proposal Engine: Prepares structured pull request proposals and research summaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .models import (
    CodeCandidate,
    EvaluationReceipt,
    ResearchHypothesis,
    SystemDiagnosis,
)


class ProposalEngine:
    """Prepares structured proposals for candidate pull requests and research audits."""

    def build_proposal_payload(
        self,
        cycle_id: int,
        diagnosis: SystemDiagnosis,
        hypothesis: ResearchHypothesis,
        candidate: CodeCandidate,
        receipt: EvaluationReceipt,
        is_promoted: bool,
    ) -> Dict[str, Any]:
        """Construct full proposal payload for draft PR submission and archival."""
        title = f"ACE Self-Dev Cycle {cycle_id}: {hypothesis.target_task_id} [{receipt.decision.value}]"
        
        status_banner = "PROMOTED TO ACTIVE HEAD" if is_promoted else "REJECTED (BASELINE RETAINED)"

        body = (
            f"## Autonomous Self-Development Cycle {cycle_id} Summary\n\n"
            f"**Cycle ID:** `CYCLE_{cycle_id:04d}`  \n"
            f"**Author Type:** `{candidate.author_type.value}`  \n"
            f"**Decision Status:** `{receipt.decision.value}` ({status_banner})  \n"
            f"**Target Task:** `{hypothesis.target_task_id}` (`{diagnosis.diagnosed_weakness_family}`)  \n"
            f"**Source SHA-256:** `{candidate.source_sha}`  \n"
            f"**Receipt ID:** `{receipt.receipt_id}`  \n"
            f"**Marginal Financial Cost:** Strictly $0.00 / Rp0  \n\n"
            f"### 1. Empirical System Diagnosis\n"
            f"- Baseline Head: `{diagnosis.baseline_head_id}` (Overall Score: `{diagnosis.baseline_score}`)\n"
            f"- Weakness Diagnosed: `{diagnosis.diagnosed_weakness_task}` (Failure Rate: `{diagnosis.observed_failure_rate}`)\n"
            f"- Diagnostic Cue: `{diagnosis.error_cue}`\n\n"
            f"### 2. Falsifiable Research Hypothesis\n"
            f"> {hypothesis.statement}\n\n"
            f"- Required Gain Threshold: `>={hypothesis.min_required_gain}`\n"
            f"- Max Regression Tolerance: `<={hypothesis.max_regression_tolerance}`\n"
            f"- Preregistration Hash: `{hypothesis.preregistration_hash}`\n\n"
            f"### 3. Generated Code Candidate\n"
            f"```python\n{candidate.source_code}```\n\n"
            f"**Diff Patch:**\n"
            f"```diff\n{candidate.diff_patch or 'No structural difference from seed'}\n```\n\n"
            f"### 4. Independent Sealed Holdout Evaluation\n"
            f"- Train Score: `{receipt.train_score}`\n"
            f"- Validation Score: `{receipt.validation_score}`\n"
            f"- Sealed Holdout Score: `{receipt.holdout_score}`\n"
            f"- Gain over Parent: `{receipt.gain_over_parent}`\n"
            f"- Prior Regression: `{receipt.prior_regression}`\n"
            f"- Decision Reason: `{receipt.decision_reason}`\n\n"
            f"### 5. Lineage Governance & Epistemic Boundaries\n"
            f"```json\n"
            f"{{\n"
            f'  "release_gate": "BLOCK_RELEASE",\n'
            f'  "scientific_status": "NOT_ASSESSED",\n'
            f'  "oaie_established": false,\n'
            f'  "promoted": {str(is_promoted).lower()}\n'
            f"}}\n"
            f"```\n"
        )

        return {
            "cycle_id": cycle_id,
            "title": title,
            "body": body,
            "candidate_id": candidate.candidate_id,
            "parent_id": candidate.parent_id,
            "source_sha": candidate.source_sha,
            "author_type": candidate.author_type.value,
            "decision": receipt.decision.value,
            "is_promoted": is_promoted,
            "receipt_id": receipt.receipt_id,
            "holdout_score": receipt.holdout_score,
            "gain_over_parent": receipt.gain_over_parent,
            "diff_patch": candidate.diff_patch,
        }
