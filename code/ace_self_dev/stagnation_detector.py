"""Autonomous Stagnation Detector for ACE Self-Development Loop.

Detects pathological search stagnation:
1. DUPLICATE_SOURCE_SHA: Candidate source SHA previously tested.
2. SEMANTIC_EQUIVALENCE: Candidate produces identical predictions on benchmark pools.
3. NO_VALIDATION_IMPROVEMENT: Validation scores fail to improve over patience window K.
4. SEARCH_SPACE_EXHAUSTED: Strategy ordinals and representations are saturated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .models import CodeCandidate, PersistentResearchState


class StagnationReason:
    NONE = "NONE"
    DUPLICATE_SOURCE_SHA = "DUPLICATE_SOURCE_SHA"
    SEMANTIC_EQUIVALENCE = "SEMANTIC_EQUIVALENCE"
    NO_VALIDATION_IMPROVEMENT = "NO_VALIDATION_IMPROVEMENT"
    SEARCH_SPACE_EXHAUSTED = "SEARCH_SPACE_EXHAUSTED"


@dataclass(frozen=True)
class StagnationAssessment:
    """Outcome of stagnation audit for a proposed research action."""
    is_stagnated: bool
    reason: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_stagnated": self.is_stagnated,
            "reason": self.reason,
            "message": self.message,
            "details": self.details,
        }


class StagnationDetector:
    """Monitors candidate generation and evaluation history to prevent wasted compute and loops."""

    def __init__(self, validation_patience: int = 5, min_validation_delta: float = 0.001):
        self.validation_patience = validation_patience
        self.min_validation_delta = min_validation_delta

    def check_source_novelty(
        self,
        candidate: CodeCandidate,
        state: PersistentResearchState,
    ) -> StagnationAssessment:
        """Verify that the candidate source code has not been tested in any prior cycle."""
        target_sha = candidate.source_sha

        # Check completed cycles history
        for cycle in state.completed_cycles:
            if cycle.get("source_sha") == target_sha:
                prior_cid = cycle.get("cycle_id", "unknown")
                prior_decision = cycle.get("decision", "unknown")
                return StagnationAssessment(
                    is_stagnated=True,
                    reason=StagnationReason.DUPLICATE_SOURCE_SHA,
                    message=(
                        f"Candidate source SHA {target_sha[:12]} was already evaluated in Cycle {prior_cid} "
                        f"with decision [{prior_decision}]. Rejecting duplicate."
                    ),
                    details={
                        "duplicate_source_sha": target_sha,
                        "first_seen_cycle": prior_cid,
                        "prior_decision": prior_decision,
                    },
                )

        # Check failure catalog
        for task_id, failures in state.failure_catalog.items():
            for f in failures:
                if f.get("source_sha") == target_sha:
                    prior_cid = f.get("cycle_id", "unknown")
                    return StagnationAssessment(
                        is_stagnated=True,
                        reason=StagnationReason.DUPLICATE_SOURCE_SHA,
                        message=(
                            f"Candidate source SHA {target_sha[:12]} was previously cataloged as a failure "
                            f"for {task_id} in Cycle {prior_cid}."
                        ),
                        details={
                            "duplicate_source_sha": target_sha,
                            "first_seen_cycle": prior_cid,
                            "task_id": task_id,
                        },
                    )

        return StagnationAssessment(
            is_stagnated=False,
            reason=StagnationReason.NONE,
            message="Source code SHA is strictly novel.",
            details={"source_sha": target_sha},
        )

    def compute_semantic_signature(
        self,
        cand_fn: Callable[[int, int, int], int],
        evaluation_pool: List[Tuple[str, bool]],
    ) -> Tuple[str, Tuple[bool, ...]]:
        """Compute the semantic behavior bitvector of a candidate over an evaluation pool."""
        predictions = []
        for w, _ in evaluation_pool:
            length = len(w)
            density = w.count("a")
            stride_val = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
            try:
                raw = cand_fn(length, density, stride_val)
                pred = (raw % 2 == 0)
            except Exception:
                pred = False
            predictions.append(pred)

        pred_tuple = tuple(predictions)
        # 64-char hex digest representing the exact boolean prediction vector
        sig = hashlib.sha256(str(pred_tuple).encode("utf-8")).hexdigest()
        return sig, pred_tuple

    def check_semantic_novelty(
        self,
        candidate_sig: str,
        historical_signatures: Dict[str, Dict[str, Any]],
    ) -> StagnationAssessment:
        """Detect semantically identical candidates even when syntax or comments differ."""
        if candidate_sig in historical_signatures:
            match_info = historical_signatures[candidate_sig]
            prior_cid = match_info.get("cycle_id", "unknown")
            prior_cand = match_info.get("candidate_id", "unknown")
            return StagnationAssessment(
                is_stagnated=True,
                reason=StagnationReason.SEMANTIC_EQUIVALENCE,
                message=(
                    f"Candidate exhibits identical prediction vector to {prior_cand} (Cycle {prior_cid}) "
                    f"despite syntactic variance. Semantic signature: {candidate_sig[:12]}."
                ),
                details={
                    "semantic_signature": candidate_sig,
                    "equivalent_candidate_id": prior_cand,
                    "equivalent_cycle_id": prior_cid,
                },
            )

        return StagnationAssessment(
            is_stagnated=False,
            reason=StagnationReason.NONE,
            message="Candidate exhibits novel semantic input-output behavior.",
            details={"semantic_signature": candidate_sig},
        )

    def check_validation_stagnation(
        self,
        state: PersistentResearchState,
        current_strategy: str,
    ) -> StagnationAssessment:
        """Detect absence of validation improvement across the last K consecutive attempts."""
        recent_cycles = state.completed_cycles[-self.validation_patience:]
        if len(recent_cycles) < self.validation_patience:
            return StagnationAssessment(
                is_stagnated=False,
                reason=StagnationReason.NONE,
                message=f"Patience buffer ({len(recent_cycles)}/{self.validation_patience}) accumulating.",
            )

        # Check if all recent cycles shared the same strategy and all were rejected
        all_same_strategy = all(
            c.get("strategy") == current_strategy or current_strategy in c.get("hypothesis_id", "")
            for c in recent_cycles
        )
        all_rejected = all(c.get("decision") != "ACCEPTED" for c in recent_cycles)

        # Measure validation score trend
        val_scores = [c.get("validation_score", c.get("holdout_score", 0.0)) for c in recent_cycles]
        max_val = max(val_scores)
        min_val = min(val_scores)

        if all_rejected and (max_val - min_val < self.min_validation_delta):
            return StagnationAssessment(
                is_stagnated=True,
                reason=StagnationReason.NO_VALIDATION_IMPROVEMENT,
                message=(
                    f"No validation progress across last {self.validation_patience} cycles "
                    f"(score variance {max_val - min_val:.4f} < {self.min_validation_delta:.4f}). "
                    f"Strategy '{current_strategy}' has saturated."
                ),
                details={
                    "strategy": current_strategy,
                    "recent_cycle_ids": [c.get("cycle_id") for c in recent_cycles],
                    "val_scores": val_scores,
                },
            )

        return StagnationAssessment(
            is_stagnated=False,
            reason=StagnationReason.NONE,
            message="Validation performance is non-stagnant.",
        )

    def check_ordinal_bounds(
        self,
        strategy: str,
        ordinal: int,
        max_ordinal: int,
        tried_ordinals: Set[int],
    ) -> StagnationAssessment:
        """Verify that mutation ordinal is strictly within search space boundaries."""
        if ordinal > max_ordinal or (len(tried_ordinals) >= max_ordinal and set(range(1, max_ordinal + 1)) <= tried_ordinals):
            return StagnationAssessment(
                is_stagnated=True,
                reason=StagnationReason.SEARCH_SPACE_EXHAUSTED,
                message=(
                    f"Strategy '{strategy}' search space exhausted. "
                    f"Attempted {len(tried_ordinals)}/{max_ordinal} ordinals. Requested ordinal {ordinal} exceeds bounds."
                ),
                details={
                    "strategy": strategy,
                    "max_ordinal": max_ordinal,
                    "tried_ordinals": sorted(list(tried_ordinals)),
                },
            )

        if ordinal in tried_ordinals:
            return StagnationAssessment(
                is_stagnated=True,
                reason=StagnationReason.DUPLICATE_SOURCE_SHA,
                message=f"Strategy '{strategy}' ordinal {ordinal} has already been attempted.",
                details={"strategy": strategy, "ordinal": ordinal},
            )

        return StagnationAssessment(
            is_stagnated=False,
            reason=StagnationReason.NONE,
            message=f"Ordinal {ordinal} is valid and unexplored for '{strategy}'.",
        )
