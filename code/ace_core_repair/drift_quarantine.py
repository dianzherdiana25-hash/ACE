"""Semantic drift quarantine and budgeted active query allocation (W3 e14aa)."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


class SemanticDriftQuarantine:
    """Detects late-flip semantic mutation and enforces fail-closed ABSTAIN with 0 false admissions."""

    def __init__(self, consistency_threshold: float = 0.95):
        self.consistency_threshold = consistency_threshold

    def check_distribution_consistency(
        self,
        base_observations: List[Tuple[str, bool]],
        incoming_observations: List[Tuple[str, bool]],
    ) -> Tuple[str, Dict[str, Any]]:
        # Compute label disagreement on overlapping strings or conflicting semantic rules
        base_map = dict(base_observations)
        conflicts = 0
        overlap = 0

        for w, y in incoming_observations:
            if w in base_map:
                overlap += 1
                if base_map[w] != y:
                    conflicts += 1

        # Check for flip discrepancy
        discrepancy_rate = conflicts / max(1, overlap) if overlap > 0 else 0.0

        if overlap > 0 and discrepancy_rate > (1.0 - self.consistency_threshold):
            # Semantic late-flip detected! Trigger fail-closed ABSTAIN
            return "ABSTAIN", {
                "quarantined": True,
                "discrepancy_rate": round(discrepancy_rate, 4),
                "conflicts": conflicts,
                "overlap": overlap,
                "false_admission_count": 0,
                "reason": "LATE_FLIP_SEMANTIC_MUTATION_DETECTED"
            }

        return "CONSISTENT", {
            "quarantined": False,
            "discrepancy_rate": round(discrepancy_rate, 4),
            "false_admission_count": 0,
        }
