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
        from ace_evaluator.sealed_generator import get_evaluation_seed_and_status
        seed, self.claim_status = get_evaluation_seed_and_status()
        self._seed = seed

    def _get_confirmation_instances(self, task_id: str) -> List[Tuple[int, int, int, int]]:
        import random
        rng = random.Random(self._seed + (abs(hash(task_id)) % 10000))
        instances = []
        for _ in range(16):
            length = rng.randint(10, 25)
            density = rng.randint(2, 8)
            stride_val = rng.randint(1, 4)
            if task_id == "task_k2":
                expected = 1 if ((stride_val * 2 - density) % 3 == 0) else 0
            else:
                expected = 1 if (length + density) % 2 == 0 else 0
            instances.append((length, density, stride_val, expected))
        return instances

    def evaluate_predicate(
        self,
        predicate_fn: Callable[[int, int, int], int],
        task_id: str = "task_k2",
    ) -> Tuple[float, int, int]:
        """Evaluates a predicate against the dynamically generated confirmation instances."""
        bank = self._get_confirmation_instances(task_id)
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
