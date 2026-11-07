"""Structured Causal Memory and Inductive Abstraction System for ACE F13.

Supports 6 matched experimental arms:
- standard: Learns and transfers inductive abstractions across curriculum tasks.
- none: Cold start, zero memory retention between tasks.
- shuffled: Shuffles learned operator/template associations.
- irrelevant: Distractor memory initialized with irrelevant domain abstractions.
- static: Fixed immutable hand-engineered priors.
- compute_matched: Cold start (none) with 2x search and inquiry budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any, Dict, List, Optional, Tuple

# Core operator families in the hypothesis space
OPERATOR_FAMILIES = (
    "flat_parity",
    "strided_parity",
    "dyck_balance",
    "depth_bounded",
    "relational_split",
    "distractor_sort",
    "distractor_substring",
)


@dataclass
class DistilledAbstraction:
    task_id: str
    cluster: str
    winning_operator: str
    winning_params: Dict[str, Any]
    holdout_accuracy: float
    queries_used: int


class CausalMemoryV2:
    """Manages inductive priors across curriculum tasks according to experimental arm."""

    def __init__(self, mode: str = "standard", seed: int = 42):
        if mode not in ("standard", "none", "shuffled", "irrelevant", "static", "compute_matched"):
            raise ValueError(f"Unknown memory mode: {mode}")
        self.mode = mode
        self.seed = seed
        self.rng = random.Random(seed)
        self.abstractions: List[DistilledAbstraction] = []

        # Default baseline prior weights
        self._default_weights: Dict[str, float] = {op: 1.0 for op in OPERATOR_FAMILIES}

        # Initialize irrelevant memory with heavy weights on distractor operators
        if self.mode == "irrelevant":
            self._default_weights["distractor_sort"] = 10.0
            self._default_weights["distractor_substring"] = 10.0
            self._default_weights["flat_parity"] = 0.2
            self._default_weights["strided_parity"] = 0.2
            self._default_weights["dyck_balance"] = 0.2
            self._default_weights["depth_bounded"] = 0.2
            self._default_weights["relational_split"] = 0.2

    def record_task_solution(
        self,
        task_id: str,
        cluster: str,
        winning_operator: str,
        winning_params: Dict[str, Any],
        holdout_accuracy: float,
        queries_used: int,
    ) -> None:
        """Record a successful task solution and distill inductive abstractions."""
        if self.mode in ("none", "compute_matched", "irrelevant"):
            return

        if self.mode == "shuffled":
            shuffled_params = dict(winning_params)
            keys = list(shuffled_params.keys())
            vals = list(shuffled_params.values())
            self.rng.shuffle(vals)
            abstraction = DistilledAbstraction(
                task_id=task_id,
                cluster=cluster,
                winning_operator=winning_operator,
                winning_params=dict(zip(keys, vals)),
                holdout_accuracy=holdout_accuracy,
                queries_used=queries_used,
            )
            self.abstractions.append(abstraction)
            return

        abstraction = DistilledAbstraction(
            task_id=task_id,
            cluster=cluster,
            winning_operator=winning_operator,
            winning_params=dict(winning_params),
            holdout_accuracy=holdout_accuracy,
            queries_used=queries_used,
        )
        self.abstractions.append(abstraction)


    def get_operator_weights(self, current_cluster: Optional[str] = None) -> Dict[str, float]:
        """Compute operator proposal weights conditioned on memory mode and task context."""
        if self.mode in ("none", "compute_matched"):
            return {op: 1.0 for op in OPERATOR_FAMILIES}

        if self.mode == "static":
            # Fixed human prior: prefers parity slightly, never updates
            return {
                "flat_parity": 3.0,
                "strided_parity": 1.0,
                "dyck_balance": 1.0,
                "depth_bounded": 1.0,
                "relational_split": 1.0,
                "distractor_sort": 0.5,
                "distractor_substring": 0.5,
            }

        if self.mode == "irrelevant":
            # Persistent distraction
            return dict(self._default_weights)

        # Mode is standard or shuffled
        weights = {op: 1.0 for op in OPERATOR_FAMILIES}
        for abs_item in self.abstractions:
            op = abs_item.winning_operator
            boost = 3.0 if abs_item.cluster == current_cluster else 1.5
            weights[op] = weights.get(op, 1.0) + boost

        if self.mode == "shuffled":
            # Permute the weights across operators
            keys = list(weights.keys())
            vals = list(weights.values())
            self.rng.shuffle(vals)
            return dict(zip(keys, vals))

        return weights

    def get_query_budget_multiplier(self) -> float:
        """Compute-matched baseline receives 2.0x budget multiplier; all others receive 1.0x."""
        return 2.0 if self.mode == "compute_matched" else 1.0

    def reset_for_task(self) -> None:
        """Per-task lifecycle hook (wipes memory for cold-start modes)."""
        if self.mode in ("none", "compute_matched"):
            self.abstractions.clear()
