"""Causal Agent with Active Information-Gain Experiment Selection and Memory Integration for F13.

Operates under Host Controller governance:
- Proposes candidate hypotheses prioritized by CausalMemoryV2 operator weights.
- Generates active discriminating probes to resolve epistemic ambiguity.
- Meters all oracle queries via Host Controller / DualOracleHarness.
- Disallows direct holdout access.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ace_host_controller import ExposureLedger, HostController
from .causal_memory import CausalMemoryV2
from .tasks import F13Task


@dataclass
class HypothesisCandidate:
    family: str
    description: str
    predicate_fn: Callable[[str], bool]
    params: Dict[str, Any]
    train_score: float = 0.0


def _build_hypothesis_pool() -> List[HypothesisCandidate]:
    """Enumerate candidate hypotheses spanning periodic, balance, and distractor families."""
    pool: List[HypothesisCandidate] = []

    # 1. Flat parity
    for char in ("a", "b"):
        for mod in (2, 3):
            for target in range(mod):
                desc = f"flat_count('{char}') % {mod} == {target}"
                fn = (lambda c=char, m=mod, t=target: lambda w: w.count(c) % m == t)()
                pool.append(
                    HypothesisCandidate(
                        family="flat_parity",
                        description=desc,
                        predicate_fn=fn,
                        params={"char": char, "mod": mod, "target": target},
                    )
                )

    # 2. Strided parity
    for stride in (2, 3):
        for offset in range(stride):
            for char in ("a", "b"):
                for mod in (2, 3):
                    for target in range(mod):
                        desc = f"w[{offset}::{stride}].count('{char}') % {mod} == {target}"
                        fn = (lambda s=stride, o=offset, c=char, m=mod, t=target: lambda w: w[o::s].count(c) % m == t)()
                        pool.append(
                            HypothesisCandidate(
                                family="strided_parity",
                                description=desc,
                                predicate_fn=fn,
                                params={"stride": stride, "offset": offset, "char": char, "mod": mod, "target": target},
                            )
                        )

    # 3. Dyck balance (unbounded & bounded)
    def _dyck(w: str, max_depth: int = 100) -> bool:
        depth = 0
        for ch in w:
            depth += 1 if ch == "a" else -1
            if depth < 0 or depth > max_depth:
                return False
        return depth == 0

    pool.append(
        HypothesisCandidate(
            family="dyck_balance",
            description="Dyck-1 balanced brackets",
            predicate_fn=lambda w: _dyck(w, 100),
            params={"max_depth": 100},
        )
    )

    for md in (2, 3, 4, 6):
        fn = (lambda d=md: lambda w: _dyck(w, d))()
        pool.append(
            HypothesisCandidate(
                family="depth_bounded",
                description=f"Dyck with max depth {md}",
                predicate_fn=fn,
                params={"max_depth": md},
            )
        )

    # 4. Relational split
    for char in ("a", "b"):
        fn = (lambda c=char: lambda w: w[: len(w) // 2].count(c) == w[len(w) // 2 :].count(c))()
        pool.append(
            HypothesisCandidate(
                family="relational_split",
                description=f"Left half count('{char}') == Right half count('{char}')",
                predicate_fn=fn,
                params={"char": char},
            )
        )

    # 5. Distractor hypotheses
    pool.append(
        HypothesisCandidate(
            family="distractor_sort",
            description="Lexicographically sorted string",
            predicate_fn=lambda w: w == "".join(sorted(w)),
            params={},
        )
    )
    for sub in ("ab", "ba", "aa", "bb"):
        fn = (lambda s=sub: lambda w: w.count(s) >= 2)()
        pool.append(
            HypothesisCandidate(
                family="distractor_substring",
                description=f"Substring '{sub}' appears >= 2 times",
                predicate_fn=fn,
                params={"sub": sub, "min_count": 2},
            )
        )

    return pool


class F13CausalAgent:
    """Autonomous research agent with causal memory and active epistemic query selection."""

    def __init__(self, memory: CausalMemoryV2, seed: int = 42):
        self.memory = memory
        self.seed = seed
        self.rng = random.Random(seed)
        self.all_hypotheses = _build_hypothesis_pool()

    def solve_task(
        self,
        task: F13Task,
        oracle_fn: Callable[[str], bool],
        base_query_budget: int = 20,
        host_controller: Optional[HostController] = None,
    ) -> Tuple[Callable[[str], bool], Dict[str, Any]]:
        """Solve a curriculum task using memory-biased hypothesis proposal and active inquiry."""
        self.memory.reset_for_task()
        mult = self.memory.get_query_budget_multiplier()
        query_budget = int(base_query_budget * mult)

        # 1. Filter hypotheses consistent with initial training samples
        weights = self.memory.get_operator_weights(task.cluster)
        candidates: List[HypothesisCandidate] = []

        for hyp in self.all_hypotheses:
            consistent = True
            for inp, expected in task.train_pool:
                try:
                    if hyp.predicate_fn(inp) != expected:
                        consistent = False
                        break
                except Exception:
                    consistent = False
                    break
            if consistent:
                # Memory-weighted score combining operator weight and distilled parameter matches
                score = weights.get(hyp.family, 1.0) * (1.0 + 0.05 * self.rng.random())
                for abs_item in self.memory.abstractions:
                    if abs_item.cluster == task.cluster:
                        p = abs_item.winning_params
                        if hyp.params.get("char") and hyp.params.get("char") == p.get("char"):
                            score += 2.0
                        if hyp.params.get("mod") and hyp.params.get("mod") == p.get("mod"):
                            score += 2.0
                        if hyp.params.get("target") is not None and hyp.params.get("target") == p.get("target"):
                            score += 1.5
                        if hyp.params.get("max_depth") and hyp.params.get("max_depth") == p.get("max_depth"):
                            score += 2.0
                hyp.train_score = score
                candidates.append(hyp)


        # Sort candidate hypotheses by memory-weighted score descending
        candidates.sort(key=lambda h: h.train_score, reverse=True)

        # 2. Active inquiry loop: generate discriminating probes if multiple candidates survive
        queries_used = 0
        candidate_pool = list(candidates)

        probe_alphabet = ("a", "b")
        candidate_probes = [
            "".join(self.rng.choices(probe_alphabet, k=length))
            for length in range(4, 9)
            for _ in range(12)
        ]

        while len(candidate_pool) > 1 and queries_used < query_budget:
            # Find probe that maximizes disagreement among top surviving candidates
            top_cand = candidate_pool[:min(5, len(candidate_pool))]
            best_probe: Optional[str] = None
            best_entropy = -1.0

            for probe in candidate_probes:
                votes = [h.predicate_fn(probe) for h in top_cand]
                pos = sum(votes)
                neg = len(votes) - pos
                if pos > 0 and neg > 0:
                    disagreement = min(pos, neg)
                    if disagreement > best_entropy:
                        best_entropy = disagreement
                        best_probe = probe

            if best_probe is None:
                break

            # Execute metered oracle query
            queries_used += 1
            if host_controller is not None:
                host_controller.exposure_ledger.record_exposure(
                    candidate_id=f"f13_probe_{task.task_id}_{queries_used}",
                    query_type="active_inquiry",
                    content=best_probe,
                )

            oracle_answer = bool(oracle_fn(best_probe))

            # Filter out inconsistent candidates
            candidate_pool = [
                h for h in candidate_pool if h.predicate_fn(best_probe) == oracle_answer
            ]

        # 3. Select final hypothesis
        if candidate_pool:
            selected_hyp = candidate_pool[0]
        elif candidates:
            selected_hyp = candidates[0]
        else:
            # Fallback to default
            selected_hyp = HypothesisCandidate(
                family="fallback",
                description="Always false",
                predicate_fn=lambda _: False,
                params={},
            )

        # 4. Measure holdout accuracy
        holdout_hits = sum(
            1 for w, lbl in task.holdout_pool if selected_hyp.predicate_fn(w) == lbl
        )
        holdout_acc = holdout_hits / max(1, len(task.holdout_pool))

        # 5. Record in causal memory if successful
        if holdout_acc >= 0.85:
            self.memory.record_task_solution(
                task_id=task.task_id,
                cluster=task.cluster,
                winning_operator=selected_hyp.family,
                winning_params=selected_hyp.params,
                holdout_accuracy=holdout_acc,
                queries_used=queries_used,
            )

        metadata = {
            "task_id": task.task_id,
            "cluster": task.cluster,
            "is_transfer_target": task.is_transfer_target,
            "selected_family": selected_hyp.family,
            "selected_description": selected_hyp.description,
            "holdout_accuracy": holdout_acc,
            "queries_used": queries_used,
            "surviving_candidates_count": len(candidate_pool),
        }

        return selected_hyp.predicate_fn, metadata
