"""Benchmark Harness for Active Epistemic Querying and Semantic Drift Falsification.

Evaluates 4 experimental arms across 30 tasks:
- 20 standard capability tasks (sound ground truth)
- 10 adversarial semantic drift tasks (unobservable under passive holdouts)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Tuple

from . import (
    ACE_RUNTIME_ROLE,
    GEMINI_ROLE,
    OAIE_ESTABLISHED,
    PRESCORE_COMMIT,
    RELEASE_GATE,
    SCHEMA_VERSION,
    SCIENTIFIC_STATUS,
)
from .prober import ActiveEpistemicProber


def create_task_suite() -> List[Dict[str, Any]]:
    """Generates 30 tasks: 20 sound tasks + 10 adversarial semantic drift tasks."""
    tasks = []

    # Helper language predicates over {'a', 'b'}
    def lang_even_b(w: str) -> bool:
        return w.count("b") % 2 == 0

    def lang_starts_a(w: str) -> bool:
        return len(w) > 0 and w.startswith("a")

    def lang_no_consecutive_b(w: str) -> bool:
        return "bb" not in w

    def lang_ends_ab(w: str) -> bool:
        return w.endswith("ab")

    def lang_parity_even(w: str) -> bool:
        return len(w) % 2 == 0

    def lang_contains_aba(w: str) -> bool:
        return "aba" in w

    def lang_more_a_than_b(w: str) -> bool:
        return w.count("a") > w.count("b")

    def lang_odd_length(w: str) -> bool:
        return len(w) % 2 == 1

    base_languages = [
        ("even_b", lang_even_b),
        ("starts_a", lang_starts_a),
        ("no_consecutive_b", lang_no_consecutive_b),
        ("ends_ab", lang_ends_ab),
        ("parity_even", lang_parity_even),
        ("contains_aba", lang_contains_aba),
        ("more_a_than_b", lang_more_a_than_b),
        ("odd_length", lang_odd_length),
    ]

    # Training and validation pools (finite short words)
    train_pool = ["", "a", "b", "aa", "ab", "ba", "bb", "aaa", "aab", "aba", "abb", "baa", "bab", "bba", "bbb"]
    val_pool = ["aaaa", "aaab", "aaba", "aabb", "abaa", "abab", "abba", "abbb", "baaa", "baab", "baba", "babb", "bbaa", "bbab", "bbba", "bbbb"]

    # 1. Generate 20 Sound Tasks
    for i in range(20):
        name, pred = base_languages[i % len(base_languages)]
        train_examples = [(w, pred(w)) for w in train_pool]
        val_examples = [(w, pred(w)) for w in val_pool]
        # Candidate matches oracle
        candidate = pred
        reference = lambda w: False  # Minimal default reference
        tasks.append({
            "task_id": f"sound_task_{i:02d}_{name}",
            "is_drift": False,
            "oracle": pred,
            "reference": reference,
            "candidate": candidate,
            "train_examples": train_examples,
            "val_examples": val_examples,
        })

    # 2. Generate 10 Adversarial Semantic Drift Tasks
    # In these tasks, candidate matches oracle on ALL train_pool and val_pool words,
    # but flips semantics on an unobserved trigger condition (e.g. length >= 5 words or specific suffix).
    drift_triggers = [
        lambda w: len(w) >= 5 and w.startswith("bbb"),
        lambda w: len(w) >= 5 and "babb" in w,
        lambda w: len(w) >= 5 and w.endswith("aaa"),
        lambda w: len(w) >= 5 and w.count("b") >= 4,
        lambda w: len(w) >= 5 and "aaaa" in w,
        lambda w: len(w) >= 5 and w.startswith("aba") and w.endswith("bab"),
        lambda w: len(w) >= 5 and "bbbb" in w,
        lambda w: len(w) >= 5 and len(w) % 3 == 0 and w.count("a") == 0,
        lambda w: len(w) >= 5 and "abab" in w and w.startswith("b"),
        lambda w: len(w) >= 5 and w.count("a") >= 4 and w.endswith("b"),
    ]

    for j, trigger in enumerate(drift_triggers):
        name, true_pred = base_languages[j % len(base_languages)]
        train_examples = [(w, true_pred(w)) for w in train_pool]
        val_examples = [(w, true_pred(w)) for w in val_pool]

        # Drifted candidate flips prediction on trigger
        def make_drift_candidate(oracle_p=true_pred, trig_p=trigger):
            def _fn(w: str) -> bool:
                if trig_p(w):
                    return not oracle_p(w)
                return oracle_p(w)
            return _fn

        candidate = make_drift_candidate()
        # Reference specification: simple baseline model
        reference = true_pred

        tasks.append({
            "task_id": f"drift_task_{j:02d}_{name}",
            "is_drift": True,
            "oracle": true_pred,
            "reference": reference,
            "candidate": candidate,
            "train_examples": train_examples,
            "val_examples": val_examples,
        })

    return tasks


def run_active_epistemic_benchmark() -> Dict[str, Any]:
    """Execute evaluation across the 4 experimental arms."""
    t_start = time.perf_counter()
    tasks = create_task_suite()
    prober = ActiveEpistemicProber(alphabet=("a", "b"), seed=42)

    arms_config = [
        ("M1_passive_supervised", "passive", 0),
        ("M2_random_query_fuzzing", "random", 8),
        ("M3_active_epistemic_probing", "active", 8),
        ("M4_resource_bounded_probing", "resource_bounded", 4),
    ]

    arm_results: Dict[str, Any] = {}

    for arm_name, mode, budget in arms_config:
        t_arm = time.perf_counter()
        drift_evaluated = 0
        drift_rejected = 0
        clean_evaluated = 0
        clean_admitted = 0
        total_queries = 0
        task_records = []

        for t in tasks:
            res = prober.evaluate_candidate(
                candidate_fn=t["candidate"],
                reference_fn=t["reference"],
                oracle_fn=t["oracle"],
                train_examples=t["train_examples"],
                val_examples=t["val_examples"],
                mode=mode,
                query_budget=budget,
            )
            total_queries += res["queries_used"]
            if t["is_drift"]:
                drift_evaluated += 1
                if not res["admitted"] and res["falsified"]:
                    drift_rejected += 1
            else:
                clean_evaluated += 1
                if res["admitted"]:
                    clean_admitted += 1

            task_records.append({
                "task_id": t["task_id"],
                "is_drift": t["is_drift"],
                "admitted": res["admitted"],
                "falsified": res["falsified"],
                "queries_used": res["queries_used"],
                "falsifying_counterexample": res["falsifying_counterexample"],
            })

        drift_rejection_rate = drift_rejected / max(1, drift_evaluated)
        clean_admission_rate = clean_admitted / max(1, clean_evaluated)
        arm_elapsed = time.perf_counter() - t_arm

        arm_results[arm_name] = {
            "mode": mode,
            "query_budget": budget,
            "drift_evaluated": drift_evaluated,
            "drift_rejected": drift_rejected,
            "drift_rejection_rate": round(drift_rejection_rate, 4),
            "false_admission_rate": round(1.0 - drift_rejection_rate, 4),
            "clean_evaluated": clean_evaluated,
            "clean_admitted": clean_admitted,
            "clean_admission_rate": round(clean_admission_rate, 4),
            "avg_queries_per_task": round(total_queries / len(tasks), 2),
            "elapsed_seconds": round(arm_elapsed, 4),
            "sample_tasks": task_records[:6],
        }

    # Hypothesis Testing
    # H1: Passive blindess (rejection rate <= 0.20, false admission >= 0.80)
    h1_pass = arm_results["M1_passive_supervised"]["drift_rejection_rate"] <= 0.20
    # H2: Active superiority (M3 drift rejection >= 0.90, strictly better than M2 random fuzzing)
    m3_drift = arm_results["M3_active_epistemic_probing"]["drift_rejection_rate"]
    m2_drift = arm_results["M2_random_query_fuzzing"]["drift_rejection_rate"]
    h2_pass = (m3_drift >= 0.90) and (m3_drift > m2_drift)
    # H3: Clean admission preserved (M3 clean admission >= 0.95)
    m3_clean = arm_results["M3_active_epistemic_probing"]["clean_admission_rate"]
    h3_pass = m3_clean >= 0.95
    # H4: Resource bounded efficiency (M4 drift rejection >= 0.80 with half budget)
    m4_drift = arm_results["M4_resource_bounded_probing"]["drift_rejection_rate"]
    h4_pass = m4_drift >= 0.80

    all_gates_pass = bool(h1_pass and h2_pass and h3_pass and h4_pass)
    total_elapsed = time.perf_counter() - t_start

    result_doc = {
        "schema": SCHEMA_VERSION,
        "prescore_commit": PRESCORE_COMMIT,
        "scientific_status": SCIENTIFIC_STATUS,
        "release_gate": RELEASE_GATE,
        "oaie_established": OAIE_ESTABLISHED,
        "attribution": {
            "gemini_role": GEMINI_ROLE,
            "ace_runtime_role": ACE_RUNTIME_ROLE,
        },
        "hypotheses": {
            "H1_passive_drift_blindness": {
                "observed_false_admission_rate": arm_results["M1_passive_supervised"]["false_admission_rate"],
                "passed": h1_pass,
            },
            "H2_active_superiority": {
                "active_rejection_rate": m3_drift,
                "random_rejection_rate": m2_drift,
                "passed": h2_pass,
            },
            "H3_clean_admission_preserved": {
                "clean_admission_rate": m3_clean,
                "passed": h3_pass,
            },
            "H4_resource_bounded_efficiency": {
                "bounded_rejection_rate": m4_drift,
                "passed": h4_pass,
            },
            "all_gates_pass": all_gates_pass,
        },
        "arms": arm_results,
        "total_tasks_evaluated": len(tasks),
        "total_elapsed_seconds": round(total_elapsed, 4),
    }

    return result_doc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/capability/ace_active_epistemic_v1.json.gz"))
    args = parser.parse_args(argv)

    print("=== Running ACE Active Epistemic Querying Capability Benchmark ===")
    results = run_active_epistemic_benchmark()
    print(f"H1 Passive Blindness: {results['hypotheses']['H1_passive_drift_blindness']['passed']} (False admission: {results['hypotheses']['H1_passive_drift_blindness']['observed_false_admission_rate']:.2f})")
    print(f"H2 Active Superiority: {results['hypotheses']['H2_active_superiority']['passed']} (Active: {results['hypotheses']['H2_active_superiority']['active_rejection_rate']:.2f} vs Random: {results['hypotheses']['H2_active_superiority']['random_rejection_rate']:.2f})")
    print(f"H3 Clean Preserved: {results['hypotheses']['H3_clean_admission_preserved']['passed']} (Clean admission: {results['hypotheses']['H3_clean_admission_preserved']['clean_admission_rate']:.2f})")
    print(f"H4 Resource Bounded: {results['hypotheses']['H4_resource_bounded_efficiency']['passed']} (Bounded rejection: {results['hypotheses']['H4_resource_bounded_efficiency']['bounded_rejection_rate']:.2f})")
    print(f"All Gates Pass: {results['hypotheses']['all_gates_pass']}")

    raw_bytes = json.dumps(results, indent=2, sort_keys=True).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wb") as f:
        f.write(raw_bytes)

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    print(f"Saved evidence artifact: {args.output} (SHA-256: {sha256})")
    return 0 if results["hypotheses"]["all_gates_pass"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
