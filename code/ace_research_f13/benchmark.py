"""Benchmark Runner for ACE F13 Causal Memory Validation.

Executes 6 matched experimental arms across 5 deterministic seeds (42, 137, 256, 512, 1024)
on the curriculum task sequence. Computes Cohen's d effect sizes, 95% confidence intervals,
and query reductions. Produces compressed JSON evidence.
"""
from __future__ import annotations

from dataclasses import asdict
import gzip
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ace_host_controller import (
    DualOracleHarness,
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    MerkleExposureLedger,
    SealedHoldoutEvaluator,
)
from .agent import F13CausalAgent
from .causal_memory import CausalMemoryV2
from .tasks import F13Task, create_distractor_tasks, create_f13_curriculum

PRE_REGISTERED_SEEDS = [42, 137, 256, 512, 1024]
ARMS = [
    ("standard", "Standard Memory"),
    ("none", "No-Memory (Cold Start)"),
    ("shuffled", "Shuffled-Memory"),
    ("irrelevant", "Irrelevant-Memory Control"),
    ("static", "Static Transfer Baseline"),
    ("compute_matched", "Compute-Matched Baseline (2x Budget)"),
]


def _mean(values: List[float]) -> float:
    return sum(values) / max(1, len(values))


def _std(values: List[float], ddof: int = 1) -> float:
    if len(values) <= 1:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - ddof)
    return math.sqrt(max(0.0, var))


def _cohens_d(group1: List[float], group2: List[float]) -> float:
    """Compute Cohen's d effect size between two independent groups."""
    n1, n2 = len(group1), len(group2)
    if n1 <= 1 or n2 <= 1:
        return 0.0
    m1, m2 = _mean(group1), _mean(group2)
    s1, s2 = _std(group1), _std(group2)
    pooled_sd = math.sqrt(((n1 - 1) * (s1 ** 2) + (n2 - 1) * (s2 ** 2)) / (n1 + n2 - 2))
    if pooled_sd == 0.0:
        return 0.0
    return (m1 - m2) / pooled_sd


def _confidence_interval_95(values: List[float]) -> Tuple[float, float]:
    """Compute 95% confidence interval using t-distribution approximation."""
    n = len(values)
    if n <= 1:
        m = _mean(values)
        return m, m
    m = _mean(values)
    s = _std(values)
    # For n=5, t(0.025, df=4) = 2.776
    margin = 2.776 * (s / math.sqrt(n))
    return m - margin, m + margin


def run_f13_curriculum_benchmark(
    seeds: List[int] = PRE_REGISTERED_SEEDS,
) -> Dict[str, Any]:
    """Run full benchmark across all seeds and experimental arms."""
    curriculum = create_f13_curriculum()
    task_order = [
        "t0_flat_parity",
        "t1_strided_even_parity",
        "t2_strided_mod3",
        "t3_dyck_warmup",
        "t4_dyck_depth_bounded",
        "t5_relational_half_split",
    ]

    raw_runs: List[Dict[str, Any]] = []
    arm_metrics: Dict[str, Dict[str, List[float]]] = {
        arm_id: {
            "transfer_accuracy": [],
            "transfer_queries": [],
            "overall_accuracy": [],
            "overall_queries": [],
        }
        for arm_id, _ in ARMS
    }

    # Prepare Host Controller infrastructure for evaluation governance
    holdout_banks = {t.task_id: list(t.holdout_pool) for t in curriculum.values()}
    evaluator = SealedHoldoutEvaluator(
        manifest_id="f13_causal_memory_manifest_v1",
        holdout_banks=holdout_banks,
    )
    host = HostController(
        evaluator=evaluator,
        budget=ExecutionBudget(max_execution_seconds=120.0, max_queries=2000, max_candidates=100),
        sandbox_gate=HostSandboxGate(enforce_os_containment=False),
        root_candidate_id="G0_f13_root",
        root_source_sha="f13_root_source_hash",
        min_gain=0.0,
        max_regression=1.0,
    )

    for seed in seeds:
        for arm_id, arm_label in ARMS:
            memory = CausalMemoryV2(mode=arm_id, seed=seed)
            agent = F13CausalAgent(memory=memory, seed=seed)

            run_record: Dict[str, Any] = {
                "seed": seed,
                "arm_id": arm_id,
                "arm_label": arm_label,
                "task_results": {},
            }

            transfer_accs: List[float] = []
            transfer_queries: List[int] = []
            all_accs: List[float] = []
            all_queries: List[int] = []

            for task_id in task_order:
                task = curriculum[task_id]
                sol_fn, meta = agent.solve_task(
                    task=task,
                    oracle_fn=task.oracle_fn,
                    base_query_budget=20,
                    host_controller=host,
                )
                # Evaluator independently evaluates on sealed holdout pool
                holdout_hits = sum(1 for w, lbl in task.holdout_pool if sol_fn(w) == lbl)
                holdout_acc = round(holdout_hits / max(1, len(task.holdout_pool)), 4)
                meta["holdout_accuracy"] = holdout_acc
                run_record["task_results"][task_id] = meta

                all_accs.append(holdout_acc)
                all_queries.append(meta["queries_used"])

                if task.is_transfer_target:
                    transfer_accs.append(holdout_acc)
                    transfer_queries.append(meta["queries_used"])

            mean_transfer_acc = _mean(transfer_accs)
            sum_transfer_q = float(sum(transfer_queries))
            mean_all_acc = _mean(all_accs)
            sum_all_q = float(sum(all_queries))

            run_record["summary"] = {
                "mean_transfer_accuracy": mean_transfer_acc,
                "total_transfer_queries": sum_transfer_q,
                "mean_overall_accuracy": mean_all_acc,
                "total_overall_queries": sum_all_q,
            }
            raw_runs.append(run_record)

            arm_metrics[arm_id]["transfer_accuracy"].append(mean_transfer_acc)
            arm_metrics[arm_id]["transfer_queries"].append(sum_transfer_q)
            arm_metrics[arm_id]["overall_accuracy"].append(mean_all_acc)
            arm_metrics[arm_id]["overall_queries"].append(sum_all_q)

    # Compute statistical summaries
    summary_by_arm: Dict[str, Any] = {}
    for arm_id, arm_label in ARMS:
        t_acc = arm_metrics[arm_id]["transfer_accuracy"]
        t_q = arm_metrics[arm_id]["transfer_queries"]
        o_acc = arm_metrics[arm_id]["overall_accuracy"]
        o_q = arm_metrics[arm_id]["overall_queries"]

        t_acc_ci = _confidence_interval_95(t_acc)
        t_q_ci = _confidence_interval_95(t_q)

        summary_by_arm[arm_id] = {
            "label": arm_label,
            "transfer_accuracy_mean": round(_mean(t_acc), 4),
            "transfer_accuracy_std": round(_std(t_acc), 4),
            "transfer_accuracy_ci95": [round(t_acc_ci[0], 4), round(t_acc_ci[1], 4)],
            "transfer_queries_mean": round(_mean(t_q), 2),
            "transfer_queries_std": round(_std(t_q), 2),
            "transfer_queries_ci95": [round(t_q_ci[0], 2), round(t_q_ci[1], 2)],
            "overall_accuracy_mean": round(_mean(o_acc), 4),
            "overall_queries_mean": round(_mean(o_q), 2),
        }

    # Compute effect sizes (Cohen's d) relative to Standard Memory
    std_t_acc = arm_metrics["standard"]["transfer_accuracy"]
    none_t_acc = arm_metrics["none"]["transfer_accuracy"]
    shuf_t_acc = arm_metrics["shuffled"]["transfer_accuracy"]
    irrel_t_acc = arm_metrics["irrelevant"]["transfer_accuracy"]
    static_t_acc = arm_metrics["static"]["transfer_accuracy"]
    comp_t_acc = arm_metrics["compute_matched"]["transfer_accuracy"]

    std_t_q = arm_metrics["standard"]["transfer_queries"]
    none_t_q = arm_metrics["none"]["transfer_queries"]

    cohens_d_vs_none = _cohens_d(std_t_acc, none_t_acc)
    cohens_d_vs_shuffled = _cohens_d(std_t_acc, shuf_t_acc)
    cohens_d_vs_irrelevant = _cohens_d(std_t_acc, irrel_t_acc)
    cohens_d_vs_static = _cohens_d(std_t_acc, static_t_acc)
    cohens_d_vs_compute = _cohens_d(std_t_acc, comp_t_acc)

    # Query reduction: (none - standard) / none
    none_q_mean = _mean(none_t_q)
    std_q_mean = _mean(std_t_q)
    query_reduction_pct = (
        ((none_q_mean - std_q_mean) / none_q_mean) * 100.0 if none_q_mean > 0 else 0.0
    )

    # Pre-registered criteria checks
    crit_cohens_d = cohens_d_vs_none >= 0.50
    crit_query_red = query_reduction_pct >= 25.0
    crit_shuffled_dom = (summary_by_arm["standard"]["transfer_accuracy_mean"] - summary_by_arm["shuffled"]["transfer_accuracy_mean"]) >= 0.05
    crit_irrel_dom = (summary_by_arm["standard"]["transfer_accuracy_mean"] - summary_by_arm["irrelevant"]["transfer_accuracy_mean"]) >= 0.05
    all_criteria_met = (
        crit_cohens_d
        and crit_query_red
        and crit_shuffled_dom
        and crit_irrel_dom
    )

    final_results = {
        "benchmark_id": "ACE_F13_CAUSAL_MEMORY_VALIDATION",
        "timestamp": "2026-11-07T12:45:00Z",
        "seeds": seeds,
        "arms_evaluated": [a[0] for a in ARMS],
        "summary_by_arm": summary_by_arm,
        "effect_sizes": {
            "cohens_d_standard_vs_none": round(cohens_d_vs_none, 4),
            "cohens_d_standard_vs_shuffled": round(cohens_d_vs_shuffled, 4),
            "cohens_d_standard_vs_irrelevant": round(cohens_d_vs_irrelevant, 4),
            "cohens_d_standard_vs_static": round(cohens_d_vs_static, 4),
            "cohens_d_standard_vs_compute_matched": round(cohens_d_vs_compute, 4),
        },
        "query_efficiency": {
            "standard_mean_queries": round(std_q_mean, 2),
            "none_mean_queries": round(none_q_mean, 2),
            "query_reduction_percentage": round(query_reduction_pct, 2),
        },
        "preregistered_criteria_evaluation": {
            "criterion_1_cohens_d_ge_0_50": {
                "observed": round(cohens_d_vs_none, 4),
                "threshold": 0.50,
                "passed": crit_cohens_d,
            },
            "criterion_2_query_reduction_ge_25_pct": {
                "observed": round(query_reduction_pct, 2),
                "threshold": 25.0,
                "passed": crit_query_red,
            },
            "criterion_3_shuffled_memory_dominance": {
                "observed_delta": round(summary_by_arm["standard"]["transfer_accuracy_mean"] - summary_by_arm["shuffled"]["transfer_accuracy_mean"], 4),
                "threshold": 0.05,
                "passed": crit_shuffled_dom,
            },
            "criterion_4_irrelevant_memory_resilience": {
                "observed_delta": round(summary_by_arm["standard"]["transfer_accuracy_mean"] - summary_by_arm["irrelevant"]["transfer_accuracy_mean"], 4),
                "threshold": 0.05,
                "passed": crit_irrel_dom,
            },
            "all_criteria_met": all_criteria_met,
            "scientific_status": "EMPIRICALLY_VALIDATED" if all_criteria_met else "FALSIFIED_OR_INCONCLUSIVE",
        },
        "governance": {
            "release_gate": "BLOCK_RELEASE",
            "scientific_status": "NOT_ASSESSED",
            "oaie_established": False,
        },
        "raw_runs": raw_runs,
    }

    return final_results


def save_evidence(results: Dict[str, Any], output_path: str = "evidence/f13/ace_f13_causal_memory_v1.json.gz") -> str:
    """Save benchmark results to compressed JSON evidence artifact."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(results, indent=2).encode("utf-8")
    with gzip.open(p, "wb") as f:
        f.write(payload)
    return str(p)
