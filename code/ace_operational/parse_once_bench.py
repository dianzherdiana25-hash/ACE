"""Before/after bench for the parse-once / compile-once candidate.

The candidate (in `pilot_abc`): one shared `ast.parse` per
`variants_by_group` call instead of one parse per operator group,
and `CachingBudget` (compile-once per distinct source) in
`_budget_for`. This module holds the frozen BASELINE reference —
the pre-candidate behaviour, reconstructed from the unshared path
(group functions called without a tree parse it themselves, exactly
as they did before) plus the plain `reasoning_lab.Budget` and a
line-for-line copy of the old solve loop — so a bench run compares
candidate against baseline in one process, checks their outputs are
identical per task, and times both in ABBA blocks.

Confirmation discipline (from the profiling blueprint):

* The workload that SELECTED the candidate (profiling pilot, seeds
  1–12) may be used for the equivalence replay, never for the
  speedup verdict.
* The speedup verdict uses a fresh workload (default seeds
  501–512), a preregistered delta (``DELTA = 0.05``), and a
  task-cluster bootstrap: CONFIRMED when the whole 95% CI of the
  median per-task wall ratio lies below ``1 - DELTA``; REGRESSION
  when it lies entirely above 1.0; INCONCLUSIVE otherwise.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from typing import Any

DELTA = 0.05  # preregistered minimum improvement for CONFIRMED


# ---------------------------------------------------------------------------
# Baseline reference (pre-candidate behaviour)
# ---------------------------------------------------------------------------

def variants_unshared(code: str, spec: str) -> dict[str, list[str]]:
    """The original variants_by_group: every group parses itself."""
    from ace_operational import pilot_abc
    groups: dict[str, list[str]] = {}
    for name, fn in pilot_abc.GROUP_FN.items():
        seen: list[str] = []
        for variant in fn(code, spec):
            if variant != code and variant not in seen:
                seen.append(variant)
        groups[name] = seen
    return groups


def solve_reference(task: dict[str, Any], budget: Any,
                    config: dict[str, Any]) -> dict[str, Any]:
    """Line-for-line the pre-candidate solve loop, on the plain
    Budget and the unshared variants path."""
    current = task["buggy_code"]
    best = budget.score(current)
    credits: dict[str, int] = {g: 0 for g in config["operators"]}
    for _ in range(config["rounds"]):
        improved = False
        groups = variants_unshared(current, task["spec"])
        for group in config["operators"]:
            for variant in groups.get(group, []):
                if budget.used >= budget.limit:
                    return {"code": current, "shown_score": best,
                            "credits": credits, "evals": budget.used}
                score = budget.score(variant)
                if score > best:
                    current, best, improved = variant, score, True
                    credits[group] += 1
                    break
            if improved:
                break
        if not improved:
            break
    return {"code": current, "shown_score": best,
            "credits": credits, "evals": budget.used}


def _plain_budget(task: dict[str, Any], limit: int):
    from ace_operational.reasoning_lab import Budget
    shown = [tuple(c) for c in task["shown_cases"]]
    by_case = {tuple(c): e for c, e in zip(task["cases"], task["expected"])}
    return Budget(limit, entrypoint=task["entrypoint"], shown_cases=shown,
                  shown_expected=[by_case[c] for c in shown])


def _public(task: dict[str, Any]) -> dict[str, Any]:
    return {k: task[k] for k in ("buggy_code", "spec", "shown_cases",
                                 "entrypoint", "seed")}


# ---------------------------------------------------------------------------
# Bench runner
# ---------------------------------------------------------------------------

def run_bench(*, families: tuple[str, ...] = ("pricing", "shipping"),
              levels: tuple[int, ...] = (1, 2, 3),
              seeds: tuple[int, ...] = tuple(range(501, 513)),
              budget_limit: int = 200, reps: int = 5,
              bootstrap_iterations: int = 2000) -> dict[str, Any]:
    """Paired candidate vs baseline per task, alternating order.

    Each task is solved ``reps`` times per mode with the starting
    mode alternating per rep; the per-mode median is the task's
    timing (jobs here are milliseconds on a shared VM — a median of
    two would be an average and one scheduling stall would poison
    it). A warm-up solve per mode runs before any timing.

    Returns per-task output equivalence, wall ratios, a task-cluster
    bootstrap CI for the median ratio, and the three-state verdict.
    """
    import random

    from ace_operational import pilot_abc

    tasks = pilot_abc.generate_universe(families=list(families),
                                        levels=list(levels),
                                        seeds=list(seeds))
    config = pilot_abc.BASE_CONFIG

    def solve(mode: str, task: dict[str, Any]) -> dict[str, Any]:
        public = _public(task)
        if mode == "base":
            return solve_reference(
                public, _plain_budget(task, budget_limit), config)
        return pilot_abc.solve_with_config(
            public, pilot_abc._budget_for(task, budget_limit), config)

    if tasks:  # warm-up: both modes once, untimed
        solve("base", tasks[0])
        solve("cand", tasks[0])

    per_task: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for task in tasks:
        runs: dict[str, list[float]] = {"base": [], "cand": []}
        outputs: set = set()
        for rep in range(reps):
            for mode in (("base", "cand") if rep % 2 == 0
                         else ("cand", "base")):
                t0 = time.perf_counter()
                result = solve(mode, task)
                runs[mode].append(time.perf_counter() - t0)
                outputs.add((result["code"], result["shown_score"],
                             result["evals"],
                             tuple(sorted(result["credits"].items()))))
        if len(outputs) != 1:
            mismatches.append(task["task_id"])
        base_med = statistics.median(runs["base"])
        cand_med = statistics.median(runs["cand"])
        per_task.append({
            "task_id": task["task_id"], "family": task["family"],
            "level": task["level"], "seed": task["seed"],
            "base_s": base_med, "cand_s": cand_med,
            "ratio": cand_med / base_med if base_med else None,
        })
    ratios = [t["ratio"] for t in per_task if t["ratio"] is not None]
    point = statistics.median(ratios) if ratios else None
    rng = random.Random(20261113)
    boot = []
    if ratios:
        for _ in range(bootstrap_iterations):
            sample = [rng.choice(ratios) for _ in ratios]
            boot.append(statistics.median(sample))
        boot.sort()
        ci_lo = boot[int(0.025 * len(boot))]
        ci_hi = boot[min(len(boot) - 1, int(0.975 * len(boot)))]
    else:
        ci_lo = ci_hi = None
    if mismatches:
        verdict = "EQUIVALENCE_FAILED"
    elif ci_hi is not None and ci_hi < 1 - DELTA:
        verdict = "CONFIRMED"
    elif ci_lo is not None and ci_lo > 1.0:
        verdict = "REGRESSION"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "tasks": len(tasks),
        "seeds": list(seeds), "levels": list(levels),
        "families": list(families), "budget_limit": budget_limit,
        "delta_preregistered": DELTA,
        "output_mismatches": mismatches,
        "median_ratio_cand_over_base": point,
        "ratio_ci95": [ci_lo, ci_hi],
        "base_total_s": sum(t["base_s"] for t in per_task),
        "cand_total_s": sum(t["cand_s"] for t in per_task),
        "verdict": verdict,
        "per_task": per_task,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    seeds = tuple(range(501, 513))
    if "--seeds" in argv:
        lo, hi = argv[argv.index("--seeds") + 1].split("-")
        seeds = tuple(range(int(lo), int(hi) + 1))
    result = run_bench(seeds=seeds)
    slim = {k: v for k, v in result.items() if k != "per_task"}
    print(json.dumps(slim, indent=1))
    return 0 if result["verdict"] != "EQUIVALENCE_FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
