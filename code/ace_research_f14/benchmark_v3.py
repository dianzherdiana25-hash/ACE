"""Independent Terminal Benchmark Runner V3 for ACE F14 Mechanism Discovery.

Evaluates autonomous mechanism discovery against 5 matched baselines across 5 paired seeds
on completely unexposed, research-disjoint task families (Family G, H, I):
- B1: Empirical Domain Reference Oracle (ground truth executed sample-by-sample)
- B2: Random AST Search (uniform sampling from G_mech without error diagnosis, N=50)
- B3: Static Feature Selection (fixed character parity heuristics)
- B4: Compute-Matched Search (3x search budget, N=150 candidates)
- B5: Cold-Start (G0 empirical baseline on sealed holdout)
- Primary: ACE Autonomous Generational Discovery Engine (G0 -> G1 -> G2)

Strictly enforces:
1. 3-tier partitioning: train_pool (search/diagnosis), validation_pool (model selection), terminal_holdout_pool (sealed Host Controller gating).
2. Zero search engine read access to terminal_holdout_pool.
3. Budget enforcement and profiling: unique candidates, evaluator calls, CPU seconds, memory MB, cost $0.00.
4. Programmatic structural novelty audit (novel primitive vs AST composition).
5. Pre-registered hypotheses evaluation (H1, H2, H3).
6. Fail-closed governance invariants: release_gate=BLOCK_RELEASE, scientific_status=NOT_ASSESSED, oaie_established=False.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ace_host_controller import (
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    SealedHoldoutEvaluator,
)
try:
    from .discovery_engine import (
        AutonomousGenerationalDiscovery,
        ErrorDiagnostic,
        GrammarSearchEngine,
        audit_primitive_novelty,
    )
    from .grammar import compile_ast_to_callable
    from .terminal_tasks_v3 import create_f14_v3_terminal_suite
except (ImportError, ValueError):
    from ace_research_f14.discovery_engine import (
        AutonomousGenerationalDiscovery,
        ErrorDiagnostic,
        GrammarSearchEngine,
        audit_primitive_novelty,
    )
    from ace_research_f14.grammar import compile_ast_to_callable
    from ace_research_f14.terminal_tasks_v3 import create_f14_v3_terminal_suite

PRE_REGISTERED_PAIRED_CONFIGS = [
    {"task_seed": 42, "search_seed": 42},
    {"task_seed": 101, "search_seed": 137},
    {"task_seed": 202, "search_seed": 256},
    {"task_seed": 303, "search_seed": 512},
    {"task_seed": 404, "search_seed": 1024},
]


def _mean(values: List[float]) -> float:
    return sum(values) / max(1, len(values))


def _std(values: List[float], ddof: int = 1) -> float:
    if len(values) <= 1:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / (len(values) - ddof)
    return math.sqrt(max(0.0, var))


def _confidence_interval_95(values: List[float]) -> Tuple[float, float]:
    """Compute 95% confidence interval using Student's t approximation for n=5 (t=2.776)."""
    n = len(values)
    if n <= 1:
        m = _mean(values)
        return m, m
    m = _mean(values)
    s = _std(values)
    margin = 2.776 * (s / math.sqrt(n))
    return round(m - margin, 4), round(m + margin, 4)


def run_single_seed_v3(
    task_seed: int = 42,
    search_seed: int = 42,
    search_budget: int = 50,
) -> Dict[str, Any]:
    """Execute single paired-seed V3 experiment across Primary Engine and Baselines B1..B5."""
    t_start = time.perf_counter()
    suite = create_f14_v3_terminal_suite(task_generation_seed=task_seed)

    # Prepare sealed terminal holdout bank for Host Controller
    holdout_banks = {t.task_id: list(t.terminal_holdout_pool) for t in suite.values()}
    evaluator = SealedHoldoutEvaluator(
        manifest_id=f"f14_v3_sealed_terminal_manifest_ts{task_seed}",
        holdout_banks=holdout_banks,
    )
    root_id = f"G0_v3_root_ts{task_seed}_ss{search_seed}"
    host_primary = HostController(
        evaluator=evaluator,
        budget=ExecutionBudget(max_execution_seconds=120.0, max_queries=1000, max_candidates=50),
        sandbox_gate=HostSandboxGate(enforce_os_containment=False),
        root_candidate_id=root_id,
        root_source_sha=f"root_sha_v3_ts{task_seed}_ss{search_seed}",
        min_gain=0.15,
        max_regression=0.02,
    )

    # 1. Primary Autonomous Discovery Engine
    discovery = AutonomousGenerationalDiscovery(seed=search_seed)
    primary_res = discovery.execute_generational_discovery(
        suite, host_primary, search_budget=search_budget
    )

    # Compute validation pool accuracy for primary candidates to evaluate generalization gap
    g0_fn = lambda w: (len(w) % 3 == 0)
    g1_fn = primary_res.get("g1_dispatch_fn")
    g2_fn = primary_res.get("g2_dispatch_fn")

    val_samples = [(tid, w, lbl) for tid, t in suite.items() for w, lbl in t.validation_pool]
    total_val = len(val_samples)
    g0_val_acc = round(sum(1 for tid, w, lbl in val_samples if g0_fn(w) == lbl) / max(1, total_val), 4)
    g1_val_acc = round(sum(1 for tid, w, lbl in val_samples if (g1_fn(w, tid) if g1_fn else g0_fn(w)) == lbl) / max(1, total_val), 4)
    g2_val_acc = round(sum(1 for tid, w, lbl in val_samples if (g2_fn(w, tid) if g2_fn else g0_fn(w)) == lbl) / max(1, total_val), 4)

    # 2. Baseline B1: Empirical Domain Reference Oracle
    b1_hits = 0
    total_ho = 0
    for tid, task in suite.items():
        for w, lbl in task.terminal_holdout_pool:
            total_ho += 1
            if task.oracle_fn(w) == lbl:
                b1_hits += 1
    b1_accuracy = round(b1_hits / max(1, total_ho), 4)

    # 3. Baseline B2: Random AST Search (N=50 uniform candidates without error diagnosis)
    searcher = GrammarSearchEngine(seed=search_seed)
    b2_solvers: Dict[str, Any] = {}
    b2_metrics_by_task: Dict[str, Any] = {}
    for tid, task in suite.items():
        r_res = searcher.search_candidates(
            diagnostic=ErrorDiagnostic(0.5, 10, 0.0, 0.0, 0.0, "flat"),
            train_samples=task.train_pool,
            budget=search_budget,
            search_mode="random",
            include_relational=True,
        )
        b2_solvers[tid] = r_res[0][0]
        b2_metrics_by_task[tid] = {
            "unique_candidates_evaluated": r_res.metrics.unique_candidates_evaluated,
            "evaluator_calls": r_res.metrics.evaluator_calls,
            "cpu_seconds": r_res.metrics.cpu_seconds,
            "memory_mb": r_res.metrics.memory_mb,
        }

    b2_ho_hits = 0
    b2_val_hits = 0
    for tid, task in suite.items():
        s_fn, _ = compile_ast_to_callable(b2_solvers[tid])
        for w, lbl in task.terminal_holdout_pool:
            if s_fn(w) == lbl:
                b2_ho_hits += 1
        for w, lbl in task.validation_pool:
            if s_fn(w) == lbl:
                b2_val_hits += 1
    b2_accuracy = round(b2_ho_hits / max(1, total_ho), 4)
    b2_val_accuracy = round(b2_val_hits / max(1, total_val), 4)

    # 4. Baseline B3: Static Feature Selection (character parity heuristics)
    b3_hits = 0
    for tid, task in suite.items():
        for w, lbl in task.terminal_holdout_pool:
            pred = (w.count("a") % 2 == 1) if tid in ("task_g2_sandwich_parity", "task_h1_chunk_alternation") else (w.count("a") % 2 == 0)
            if pred == lbl:
                b3_hits += 1
    b3_accuracy = round(b3_hits / max(1, total_ho), 4)

    # 5. Baseline B4: Compute-Matched Search (3x budget, N=150 candidates)
    b4_solvers: Dict[str, Any] = {}
    b4_metrics_by_task: Dict[str, Any] = {}
    for tid, task in suite.items():
        c_res = searcher.search_candidates(
            diagnostic=ErrorDiagnostic(0.5, 10, 0.0, 0.0, 0.0, "flat"),
            train_samples=task.train_pool,
            budget=search_budget * 3,
            search_mode="compute_matched",
            include_relational=True,
        )
        b4_solvers[tid] = c_res[0][0]
        b4_metrics_by_task[tid] = {
            "unique_candidates_evaluated": c_res.metrics.unique_candidates_evaluated,
            "evaluator_calls": c_res.metrics.evaluator_calls,
            "cpu_seconds": c_res.metrics.cpu_seconds,
            "memory_mb": c_res.metrics.memory_mb,
        }

    b4_hits = 0
    for tid, task in suite.items():
        s_fn, _ = compile_ast_to_callable(b4_solvers[tid])
        for w, lbl in task.terminal_holdout_pool:
            if s_fn(w) == lbl:
                b4_hits += 1
    b4_accuracy = round(b4_hits / max(1, total_ho), 4)

    # 6. Baseline B5: Cold-Start G0
    b5_accuracy = primary_res["g0_empirical_accuracy"]

    elapsed_total = round(time.perf_counter() - t_start, 4)

    return {
        "task_seed": task_seed,
        "search_seed": search_seed,
        "search_budget": search_budget,
        "evaluator_manifest_digest": evaluator.manifest.manifest_digest,
        "g0_accuracy": b5_accuracy,
        "g0_val_accuracy": g0_val_acc,
        "g1_accuracy": primary_res["g1_accuracy"],
        "g1_val_accuracy": g1_val_acc,
        "g1_gain": primary_res["g1_gain"],
        "g1_accepted": primary_res["g1_accepted"],
        "g2_accuracy": primary_res["g2_accuracy"],
        "g2_val_accuracy": g2_val_acc,
        "g2_gain": primary_res["g2_gain"],
        "g2_regression": primary_res["g2_regression"],
        "g2_accepted": primary_res["g2_accepted"],
        "active_head_id": primary_res.get("active_head_id", host_primary.lineage.active_head_id),
        "is_novel_primitive_discovered": primary_res.get("is_novel_primitive_discovered", False),
        "novelty_audits": primary_res.get("novelty_audits", {}),
        "primary_search_metrics": primary_res.get("search_metrics", {}),
        "b1_accuracy": b1_accuracy,
        "b2_accuracy": b2_accuracy,
        "b2_val_accuracy": b2_val_accuracy,
        "b2_search_metrics": b2_metrics_by_task,
        "b3_accuracy": b3_accuracy,
        "b4_accuracy": b4_accuracy,
        "b4_search_metrics": b4_metrics_by_task,
        "b5_accuracy": b5_accuracy,
        "total_elapsed_seconds": elapsed_total,
        "search_cost_usd": 0.0,
        "raw_labels": primary_res.get("raw_labels", []),
        "raw_predictions": primary_res.get("raw_predictions", {}),
        "g1_solvers_signatures": primary_res.get("g1_solvers_signatures", {}),
        "g2_solvers_signatures": primary_res.get("g2_solvers_signatures", {}),
    }


def run_f14_v3_benchmark(
    paired_configs: Optional[List[Dict[str, int]]] = None,
    search_budget: int = 50,
) -> Dict[str, Any]:
    """Execute complete 5-seed F14 V3 Independent Scientific Benchmark."""
    configs = paired_configs or PRE_REGISTERED_PAIRED_CONFIGS
    per_seed_runs: List[Dict[str, Any]] = []

    for cfg in configs:
        res = run_single_seed_v3(
            task_seed=cfg["task_seed"],
            search_seed=cfg["search_seed"],
            search_budget=search_budget,
        )
        per_seed_runs.append(res)

    # Aggregate Primary Metrics
    g0_accs = [r["g0_accuracy"] for r in per_seed_runs]
    g1_accs = [r["g1_accuracy"] for r in per_seed_runs]
    g1_gains = [r["g1_gain"] for r in per_seed_runs]
    g2_accs = [r["g2_accuracy"] for r in per_seed_runs]
    g2_gains = [r["g2_gain"] for r in per_seed_runs]
    g2_regs = [r["g2_regression"] for r in per_seed_runs]
    b1_accs = [r["b1_accuracy"] for r in per_seed_runs]
    b2_accs = [r["b2_accuracy"] for r in per_seed_runs]
    b3_accs = [r["b3_accuracy"] for r in per_seed_runs]
    b4_accs = [r["b4_accuracy"] for r in per_seed_runs]

    mean_g0 = round(_mean(g0_accs), 4)
    mean_g1 = round(_mean(g1_accs), 4)
    mean_g1_gain = round(_mean(g1_gains), 4)
    mean_g2 = round(_mean(g2_accs), 4)
    mean_g2_gain = round(_mean(g2_gains), 4)
    mean_g2_reg = round(_mean(g2_regs), 4)
    mean_b1 = round(_mean(b1_accs), 4)
    mean_b2 = round(_mean(b2_accs), 4)
    mean_b3 = round(_mean(b3_accs), 4)
    mean_b4 = round(_mean(b4_accs), 4)

    # Generalization gaps: abs(terminal holdout - validation)
    g1_val_gaps = [abs(r["g1_accuracy"] - r["g1_val_accuracy"]) for r in per_seed_runs]
    g2_val_gaps = [abs(r["g2_accuracy"] - r["g2_val_accuracy"]) for r in per_seed_runs]
    mean_g1_val_gap = round(_mean(g1_val_gaps), 4)
    mean_g2_val_gap = round(_mean(g2_val_gaps), 4)

    # Paired differences
    diff_g1_vs_random = [g1 - b2 for g1, b2 in zip(g1_accs, b2_accs)]
    diff_g2_vs_random = [g2 - b2 for g2, b2 in zip(g2_accs, b2_accs)]
    diff_g2_vs_static = [g2 - b3 for g2, b3 in zip(g2_accs, b3_accs)]
    mean_g2_vs_random = round(_mean(diff_g2_vs_random), 4)

    # Audit novelty: check if any run discovered genuine novel primitive
    any_novel_primitive = any(r["is_novel_primitive_discovered"] for r in per_seed_runs)

    # Evaluate Pre-registered Hypotheses H1, H2, H3
    # H1: Genuine primitive discovery
    h1_confirmed = any_novel_primitive and (mean_g1_gain >= 0.15 or mean_g2_gain >= 0.15)
    h1_status = "CONFIRMED" if h1_confirmed else "FALSIFIED_COMBINATORIAL_SEARCH_ONLY"

    # H2: Representation transfer (guided - random >= 0.10 and val_gap <= 0.05)
    h2_confirmed = (mean_g2_vs_random >= 0.10) and (mean_g2_val_gap <= 0.05)
    h2_status = "CONFIRMED" if h2_confirmed else "FALSIFIED_NO_REPRESENTATION_TRANSFER"

    # H3: Recursive capability growth (g1_gain >= 0.15, g2_gain >= 0.15, reg <= 0.02)
    h3_g1_ok = mean_g1_gain >= 0.15
    h3_g2_ok = mean_g2_gain >= 0.15
    h3_reg_ok = mean_g2_reg <= 0.02
    h3_confirmed = h3_g1_ok and h3_g2_ok and h3_reg_ok
    h3_status = "CONFIRMED" if h3_confirmed else "FALSIFIED_GROWTH_HALTED"

    final_results = {
        "benchmark_id": "ACE_F14_V3_SCIENTIFIC_VALIDATION",
        "timestamp": "2026-11-07T14:00:00Z",
        "evaluation_task_suite": "code/ace_research_f14/terminal_tasks_v3.py",
        "disjoint_task_families": ["family_g", "family_h", "family_i"],
        "paired_configs": configs,
        "search_budget_enforced": search_budget,
        "primary_discovery_summary": {
            "g0_accuracy_mean": mean_g0,
            "g0_accuracy_ci95": list(_confidence_interval_95(g0_accs)),
            "g1_accuracy_mean": mean_g1,
            "g1_accuracy_ci95": list(_confidence_interval_95(g1_accs)),
            "g1_gain_mean": mean_g1_gain,
            "g1_generalization_gap_mean": mean_g1_val_gap,
            "g2_accuracy_mean": mean_g2,
            "g2_accuracy_ci95": list(_confidence_interval_95(g2_accs)),
            "g2_gain_mean": mean_g2_gain,
            "g2_regression_mean": mean_g2_reg,
            "g2_generalization_gap_mean": mean_g2_val_gap,
            "any_novel_primitive_discovered": any_novel_primitive,
        },
        "baselines_summary": {
            "B1_empirical_domain_reference": mean_b1,
            "B2_random_ast_search": mean_b2,
            "B3_static_feature_selection": mean_b3,
            "B4_compute_matched_search_3x": mean_b4,
            "B5_cold_start_g0": mean_g0,
            "ACE_F14_v3_primary_g1": mean_g1,
            "ACE_F14_v3_primary_g2": mean_g2,
        },
        "paired_seed_differences": {
            "g1_vs_random_b2_mean_delta": round(_mean(diff_g1_vs_random), 4),
            "g1_vs_random_b2_ci95": list(_confidence_interval_95(diff_g1_vs_random)),
            "g2_vs_random_b2_mean_delta": mean_g2_vs_random,
            "g2_vs_random_b2_ci95": list(_confidence_interval_95(diff_g2_vs_random)),
            "g2_vs_static_b3_mean_delta": round(_mean(diff_g2_vs_static), 4),
            "g2_vs_static_b3_ci95": list(_confidence_interval_95(diff_g2_vs_static)),
        },
        "hypotheses_evaluation": {
            "H1_genuine_primitive_discovery": {
                "question": "Does ACE discover novel computational primitives beyond G_mech catalog?",
                "observed_novel_primitive": any_novel_primitive,
                "status": h1_status,
                "confirmed": h1_confirmed,
            },
            "H2_cross_family_representation_transfer": {
                "question": "Does diagnostic guidance transfer representations across families G, H, I?",
                "observed_guided_vs_random_delta": mean_g2_vs_random,
                "observed_generalization_gap": mean_g2_val_gap,
                "threshold_delta": 0.10,
                "threshold_gap": 0.05,
                "status": h2_status,
                "confirmed": h2_confirmed,
            },
            "H3_recursive_capability_growth": {
                "question": "Does generational succession G0->G1->G2 produce monotonic regression-bounded growth?",
                "observed_g1_gain": mean_g1_gain,
                "observed_g2_gain": mean_g2_gain,
                "observed_g2_regression": mean_g2_reg,
                "g1_promoted": h3_g1_ok,
                "g2_promoted": h3_g2_ok,
                "status": h3_status,
                "confirmed": h3_confirmed,
            },
        },
        "governance": {
            "release_gate": "BLOCK_RELEASE",
            "scientific_status": "NOT_ASSESSED",
            "oaie_established": False,
        },
        "per_seed_runs": per_seed_runs,
    }

    return final_results


def save_evidence_v3(
    results: Dict[str, Any],
    output_path: str = "evidence/f14/ace_f14_v3_scientific_validation.json.gz",
) -> str:
    """Save F14 V3 benchmark results to compressed JSON evidence artifact."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(results, indent=2).encode("utf-8")
    with gzip.open(p, "wb") as f:
        f.write(payload)
    return str(p)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run F14 V3 Independent Scientific Benchmark")
    parser.add_argument("--budget", type=int, default=50, help="Search budget per task (default: 50)")
    parser.add_argument("--output", type=str, default="evidence/f14/ace_f14_v3_scientific_validation.json.gz")
    args = parser.parse_args()

    print(f"Executing F14 V3 Benchmark across 5 paired seeds (budget={args.budget})...")
    res = run_f14_v3_benchmark(search_budget=args.budget)
    out_file = save_evidence_v3(res, output_path=args.output)
    print(f"Evidence artifact saved to: {out_file}")
    print(f"H1 Status: {res['hypotheses_evaluation']['H1_genuine_primitive_discovery']['status']}")
    print(f"H2 Status: {res['hypotheses_evaluation']['H2_cross_family_representation_transfer']['status']}")
    print(f"H3 Status: {res['hypotheses_evaluation']['H3_recursive_capability_growth']['status']}")
