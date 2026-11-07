"""Independent Evaluator & Scientific Meta-Productivity Benchmark.

Enforces genuine separation between candidate generators and evaluators:
- Private confirmation holdout banks inaccessible to generators.
- Negative controls and adversarial challenge sets.
- Meta-productivity measurement assessing whether research throughput improves.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class IndependentEvaluator:
    """Evaluates candidates using held-out confirmation tasks and negative controls."""

    def __init__(self):
        # Private confirmation bank (isolated from generator)
        self._private_confirmation_bank = {
            "task_k2": [
                (12, 4, 3, 1), (15, 6, 3, 1), (10, 2, 2, 0), (14, 5, 2, 0),
                (18, 6, 3, 1), (20, 8, 4, 1), (11, 3, 1, 0), (16, 7, 2, 0),
            ],
            "task_j1": [
                (12, 4, 3, 1), (15, 5, 3, 0), (14, 2, 2, 1), (10, 4, 2, 1),
                (16, 6, 3, 0), (20, 4, 4, 1), (18, 8, 3, 0), (22, 6, 4, 1),
            ],
        }

    def evaluate_predicate(
        self,
        predicate_fn: Callable[[int, int, int], int],
        task_id: str = "task_k2",
    ) -> Tuple[float, int, int]:
        """Evaluates a predicate against the private confirmation bank."""
        bank = self._private_confirmation_bank.get(task_id, [])
        if not bank:
            return 0.0, 0, 0

        hits = 0
        total = len(bank)
        for length, density, stride_val, expected in bank:
            try:
                pred = int(predicate_fn(length, density, stride_val))
                if pred == expected:
                    hits += 1
            except Exception:
                pass

        score = hits / total if total > 0 else 0.0
        return score, hits, total

    def evaluate_negative_control(
        self,
        predicate_fn: Callable[[int, int, int], int],
    ) -> bool:
        """Verifies that candidate does not trivially predict 1 on inverted/adversarial controls."""
        # Adversarial sample: all inputs negative or corrupted
        adversarial_samples = [
            (0, 0, 0), (-1, -1, -1), (999, 1, 0)
        ]
        all_ones = True
        for l, d, s in adversarial_samples:
            try:
                if int(predicate_fn(l, d, s)) != 1:
                    all_ones = False
            except Exception:
                pass

        # If it blindly returns 1 on everything, negative control fails!
        return not all_ones

    def compute_meta_productivity(
        self,
        cycle_count: int,
        novel_candidates_count: int,
        eval_durations: List[float],
    ) -> Dict[str, float]:
        """Computes research meta-productivity: candidate novelty throughput per unit time."""
        if cycle_count <= 0 or not eval_durations:
            return {"novelty_rate": 0.0, "mean_latency_s": 0.0, "meta_productivity_index": 0.0}

        novelty_rate = novel_candidates_count / cycle_count
        mean_latency = sum(eval_durations) / len(eval_durations)
        # Meta-productivity: novelty rate normalized by latency
        index = novelty_rate / max(0.001, mean_latency)

        return {
            "novelty_rate": round(novelty_rate, 4),
            "mean_latency_s": round(mean_latency, 6),
            "meta_productivity_index": round(index, 2),
        }
