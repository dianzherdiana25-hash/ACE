"""Lineage Governor: Enforces gating decisions and maintains active lineage baseline."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ace_host_controller import HostController
from .models import CandidateDecision, EvaluationReceipt


class LineageGovernor:
    """Manages active baseline promotion and retention under Host Controller governance."""

    def apply_decision(
        self,
        receipt: EvaluationReceipt,
        host_controller: Optional[HostController] = None,
        fallback_head_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """Apply gating decision to lineage. Returns (active_head_id, is_promoted)."""
        active_head = (
            host_controller.lineage.active_head_id
            if host_controller is not None
            else (fallback_head_id or receipt.parent_id)
        )

        if receipt.decision == CandidateDecision.ACCEPTED:
            # Verified promotion
            is_promoted = True
            new_head = receipt.candidate_id
            return new_head, is_promoted
        else:
            # Rejection, Blocked, or Stagnated: fail-closed retention of parent baseline
            is_promoted = False
            if host_controller is not None and host_controller.lineage.active_head_id == receipt.candidate_id:
                raise RuntimeError(
                    f"Lineage corruption: rejected candidate {receipt.candidate_id} "
                    f"became active head!"
                )
            return active_head, is_promoted
