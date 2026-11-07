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
        host_controller: HostController,
    ) -> Tuple[str, bool]:
        """Apply gating decision to lineage. Returns (active_head_id, is_promoted)."""
        active_head = host_controller.lineage.active_head_id

        if receipt.decision == CandidateDecision.ACCEPTED:
            # Verified promotion
            is_promoted = True
            new_head = receipt.candidate_id
            if host_controller.lineage.active_head_id != new_head:
                # Gated node already promoted by controller
                pass
            return new_head, is_promoted
        else:
            # Rejection or Blocked: fail-closed retention of parent baseline
            is_promoted = False
            # Ensure candidate did NOT overwrite active head
            if host_controller.lineage.active_head_id == receipt.candidate_id:
                raise RuntimeError(
                    f"Lineage corruption: rejected candidate {receipt.candidate_id} "
                    f"became active head!"
                )
            return host_controller.lineage.active_head_id, is_promoted
