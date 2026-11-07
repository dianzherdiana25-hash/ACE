"""Generative synthesis engines and baseline benchmark arms for F10."""
from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any

from .grammar import FalsificationMetric, HypothesisDomain, PropertyKind, TypedHypothesis


def _make_runtime_goal_spec(name: str, task_name: str, train_words: list[str], val_words: list[str]) -> dict[str, Any]:
    return {
        "schema": "ace.goal.v1",
        "name": name,
        "objective": {
            "kind": "ace_task_learning_cycle",
            "tasks": [
                {
                    "name": task_name,
                    "train": train_words,
                    "validation": val_words,
                }
            ],
        },
        "policy": {
            "authorized_tools": ["ace_enqueue_task", "ace_run_tasks", "ace_status"],
            "read_prefixes": [""],
            "write_prefixes": ["candidates/"],
            "review_policy": "complete",
        },
        "budget": {
            "max_steps": 5,
            "max_candidates": 1,
            "max_retries_per_step": 0,
            "wall_seconds": 15.0,
            "cpu_seconds": 10.0,
        },
    }


class FixedCatalogGenerator:
    """Arm A: Static hand-authored catalog of research hypotheses."""

    CATALOG = [
        TypedHypothesis(
            hyp_id="FIXED_HYP_01_MOD4_STATE_BOUND",
            domain=HypothesisDomain.REGULAR_LANGUAGE,
            property_kind=PropertyKind.EXPRESSIBILITY_BOUNDARY,
            gap_reference="GAP_REGULAR_STATE_CAP",
            statement="State-merging DFA induction on mod-4 regular language requires <= 8 states for 100% validation.",
            metric=FalsificationMetric.ACCURACY_MIN,
            threshold=0.90,
            comparator="<",
            goal_spec=_make_runtime_goal_spec(
                "goal_fixed_01",
                "mod4_parity",
                ["", "a", "aa", "aaa", "aaaa", "b", "ab", "aab"],
                ["aaaaa", "aaaaaa", "aaaaaaa", "aaaaaaaa"],
            ),
            epistemic_context={"arm": "fixed_catalog", "source": "hand_authored"},
        ),
        TypedHypothesis(
            hyp_id="FIXED_HYP_02_PALINDROME_LIMIT",
            domain=HypothesisDomain.CONTEXT_FREE_MIRROR,
            property_kind=PropertyKind.EXPRESSIBILITY_BOUNDARY,
            gap_reference="GAP_CONTEXT_FREE_BOUNDARY",
            statement="Bounded DFA state merging on length-10 mirror palindrome fails validation (accuracy < 0.60).",
            metric=FalsificationMetric.ACCURACY_MIN,
            threshold=0.60,
            comparator=">=",
            goal_spec=_make_runtime_goal_spec(
                "goal_fixed_02",
                "mirror_palindrome",
                ["aa", "bb", "abba", "baab"],
                ["aabbaa", "ababbaba", "abbbbba"],
            ),
            epistemic_context={"arm": "fixed_catalog", "source": "hand_authored"},
        ),
    ]

    def generate(self, gaps: list[dict[str, Any]], rng: random.Random) -> list[TypedHypothesis]:
        return list(self.CATALOG)


class RandomGrammarGenerator:
    """Arm B: Random unbiased sampling from production rules without empirical gap grounding."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate(self, gaps: list[dict[str, Any]], rng: random.Random) -> list[TypedHypothesis]:
        hyps: list[TypedHypothesis] = []
        for i in range(len(gaps)):
            domain = rng.choice(HypothesisDomain.ALL)
            prop = rng.choice(PropertyKind.ALL)
            metric = rng.choice(FalsificationMetric.ALL)
            comparator = rng.choice(["<", ">", "<=", ">="])
            threshold = round(rng.uniform(0.50, 0.95), 2)
            hyp_id = f"RANDOM_HYP_{i}_{domain[:3]}_{prop[:3]}"
            h = TypedHypothesis(
                hyp_id=hyp_id,
                domain=domain,
                property_kind=prop,
                gap_reference=gaps[i].get("gap_id", "GAP_UNKNOWN"),
                statement=f"Random production {hyp_id} over {domain} expects {metric} {comparator} {threshold}",
                metric=metric,
                threshold=threshold,
                comparator=comparator,
                goal_spec=_make_runtime_goal_spec(
                    f"goal_{hyp_id.lower()}",
                    f"task_{hyp_id.lower()}",
                    ["a", "b", "ab", "ba"],
                    ["aa", "bb", "aba", "bab"],
                ),
                epistemic_context={"arm": "random_grammar", "random_draw": i},
            )
            hyps.append(h)
        return hyps


class NoveltyOnlyGenerator:
    """Arm C: Maximizing syntactic/token Jaccard distance from past hypotheses."""

    def __init__(self, archive: list[TypedHypothesis] | None = None):
        self.archive = list(archive or [])

    def generate(self, gaps: list[dict[str, Any]], rng: random.Random) -> list[TypedHypothesis]:
        candidates: list[TypedHypothesis] = []
        # Generate candidate pool
        for i in range(10):
            domain = rng.choice(HypothesisDomain.ALL)
            prop = rng.choice(PropertyKind.ALL)
            metric = rng.choice(FalsificationMetric.ALL)
            comparator = rng.choice(["<", ">="])
            threshold = round(rng.uniform(0.55, 0.90), 2)
            hyp_id = f"NOVELTY_CAND_{i}"
            c = TypedHypothesis(
                hyp_id=hyp_id,
                domain=domain,
                property_kind=prop,
                gap_reference=gaps[i % len(gaps)].get("gap_id", "GAP_UNKNOWN") if gaps else "GAP_DEFAULT",
                statement=f"Novelty-driven probe {hyp_id} for {domain} with {prop}",
                metric=metric,
                threshold=threshold,
                comparator=comparator,
                goal_spec=_make_runtime_goal_spec(
                    f"goal_{hyp_id.lower()}",
                    f"task_{hyp_id.lower()}",
                    ["ab", "ba", "aab", "bba"],
                    ["aabb", "bbaa", "abab"],
                ),
                epistemic_context={"arm": "novelty_only"},
            )
            candidates.append(c)

        # Select candidates that maximize novelty (least similarity to archive tokens)
        selected: list[TypedHypothesis] = []
        archive_tokens = set()
        for ah in self.archive:
            archive_tokens.update(ah.statement.split())

        for c in sorted(candidates, key=lambda x: len(set(x.statement.split()) - archive_tokens), reverse=True):
            if len(selected) < len(gaps):
                selected.append(c)
                archive_tokens.update(c.statement.split())
        return selected


class ExtraComputeGenerator:
    """Arm D: Fixed catalog with 4x evaluator budget simulation."""

    def generate(self, gaps: list[dict[str, Any]], rng: random.Random) -> list[TypedHypothesis]:
        base = FixedCatalogGenerator().generate(gaps, rng)
        extra = []
        for h in base:
            spec = copy.deepcopy(h.goal_spec)
            spec["budget"]["max_steps"] = spec["budget"]["max_steps"] * 4
            spec["budget"]["wall_seconds"] = spec["budget"]["wall_seconds"] * 4.0
            spec["budget"]["cpu_seconds"] = spec["budget"]["cpu_seconds"] * 4.0
            extra.append(
                TypedHypothesis(
                    hyp_id=f"{h.hyp_id}_EXTRA4X",
                    domain=h.domain,
                    property_kind=h.property_kind,
                    gap_reference=h.gap_reference,
                    statement=f"{h.statement} (with 4x compute budget)",
                    metric=h.metric,
                    threshold=h.threshold,
                    comparator=h.comparator,
                    goal_spec=spec,
                    epistemic_context={"arm": "extra_compute", "multiplier": 4},
                )
            )
        return extra


class StructuralHypothesisGenerator:
    """Arm E (F10): Grounded Structural Hypothesis Synthesis driven by empirical gap signals."""

    def __init__(self, seed: int = 2026):
        self.rng = random.Random(seed)

    def generate(self, gaps: list[dict[str, Any]], rng: random.Random) -> list[TypedHypothesis]:
        synthesized: list[TypedHypothesis] = []

        for idx, gap in enumerate(gaps):
            gap_id = gap.get("gap_id", f"GAP_{idx}")
            severity = float(gap.get("severity", 0.5))
            signal = str(gap.get("empirical_signal", ""))

            # Synthesize domain and property based on grounded gap signal
            if "palindrome" in signal.lower() or "mirror" in signal.lower() or "context-free" in signal.lower():
                domain = HypothesisDomain.CONTEXT_FREE_MIRROR
                prop = PropertyKind.EXPRESSIBILITY_BOUNDARY
                metric = FalsificationMetric.ACCURACY_MIN
                comparator = "<"
                threshold = 0.50  # Bounded state merger expected to fail on non-regular mirrors
                statement = (
                    f"F10 Synthesized: Bounded DFA runtime cannot validate length-12 mirror palindromes "
                    f"above chance level ({threshold}); falsified if validation accuracy exceeds {threshold}."
                )
                train_words = ["aa", "bb", "abba", "baab", "aabbaa", "baabba"]
                val_words = ["ababbaba", "bbaabb", "abbbba", "baaaab"]

            elif "drift" in signal.lower() or "semantic" in signal.lower() or "unobservable" in signal.lower():
                domain = HypothesisDomain.REPRESENTATION_OCCUPANCY
                prop = PropertyKind.DRIFT_VULNERABILITY
                metric = FalsificationMetric.DRIFT_ERROR_RATE
                comparator = ">"
                threshold = 0.80  # Expected terminal error collapse under hidden semantic drift
                statement = (
                    f"F10 Synthesized: Unobservable label inversion induces terminal error rate > {threshold} "
                    "without detection on training split; falsified if error rate <= {threshold}."
                )
                train_words = ["a", "aa", "aaa", "b", "bb", "bbb"]
                val_words = ["aaaa", "bbbb", "ab", "ba"]

            elif "repair" in signal.lower() or "ceiling" in signal.lower() or "budget" in signal.lower():
                domain = HypothesisDomain.ARITHMETIC_INVARIANT
                prop = PropertyKind.TRANSFER_EFFICIENCY
                metric = FalsificationMetric.COMPUTE_RATIO
                comparator = "<"
                threshold = 0.70  # Expected to reduce candidate evaluations to < 70% of fresh
                statement = (
                    f"F10 Synthesized: Closed AST operator mutation achieves compute ratio < {threshold} "
                    "relative to unguided random search on nominal arithmetic bugs."
                )
                train_words = ["0", "1", "2", "3", "4"]
                val_words = ["5", "6", "7", "8"]

            else:
                domain = HypothesisDomain.REGULAR_LANGUAGE
                prop = PropertyKind.SAMPLE_COMPLEXITY
                metric = FalsificationMetric.ACCURACY_DELTA
                comparator = ">="
                threshold = 0.05
                statement = (
                    f"F10 Synthesized: Modular congruence feature transfer achieves accuracy delta >= {threshold} "
                    "over uninitialized learner at sample budget B=16."
                )
                train_words = ["", "a", "aa", "b", "ab", "ba"]
                val_words = ["aaa", "aab", "aba", "baa"]

            hyp_id = f"F10_STRUCT_HYP_{idx+1}_{domain[:4]}_{prop[:4]}"
            h = TypedHypothesis(
                hyp_id=hyp_id,
                domain=domain,
                property_kind=prop,
                gap_reference=gap_id,
                statement=statement,
                metric=metric,
                threshold=threshold,
                comparator=comparator,
                goal_spec=_make_runtime_goal_spec(
                    f"goal_{hyp_id.lower()}",
                    f"task_{hyp_id.lower()}",
                    train_words,
                    val_words,
                ),
                epistemic_context={
                    "arm": "f10_structural",
                    "grounded_gap_id": gap_id,
                    "gap_severity": severity,
                },
            )
            synthesized.append(h)

        return synthesized
