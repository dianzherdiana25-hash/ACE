"""Generation-context bench: equivalence replay + fresh confirmation.

Candidate: the shipped candidate path WITH the per-round generation
context (``pilot_abc.variants_by_group`` builds one
``_round_context`` per round). Baseline: the immediately preceding
shipped path — parse-once tree sharing WITHOUT the context (group
functions called with ``tree=`` only) and the same
``CachingBudget`` — so the measured delta is this candidate's
alone, not parse-once's (that was PR #180's bench).

Promotion gates (fixed in the pilot-2 report, PR #183, before this
build): (1) equivalence replay — per-task outputs (code,
shown_score, evals, credits) identical between baseline and
candidate on the pilot workload (seeds 1–12); (2) fresh-workload
confirmation (seeds 901–912) with the preregistered delta
``DELTA = 0.05`` and the three-state verdict. The runner mirrors
``parse_once_bench.run_bench`` exactly (warm-up, 5 reps with
alternating start, per-mode medians, task-cluster bootstrap) so
both benches measure the same way.
"""

from __future__ import annotations

import ast
import json
import statistics
import sys
import time
from typing import Any

from ace_operational.parse_once_bench import DELTA, _public


def variants_no_context(code: str, spec: str) -> dict[str, list[str]]:
    """Parse-once WITHOUT the generation context (frozen baseline)."""
    from ace_operational import pilot_abc
    tree = ast.parse(code)
    groups: dict[str, list[str]] = {}
    for name, fn in pilot_abc.GROUP_FN.items():
        seen: list[str] = []
        for variant in fn(code, spec, tree=tree):
            if variant != code and variant not in seen:
                seen.append(variant)
        groups[name] = seen
    return groups


def solve_no_context(task: dict[str, Any], budget: Any,
                     config: dict[str, Any]) -> dict[str, Any]:
    """solve_with_config's loop over the no-context variants."""
    current = task["buggy_code"]
    best = budget.score(current)
    credits: dict[str, int] = {g: 0 for g in config["operators"]}
    for _ in range(config["rounds"]):
        improved = False
        groups = variants_no_context(current, task["spec"])
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


def run_bench(*, families: tuple[str, ...] = ("pricing", "shipping"),
              levels: tuple[int, ...] = (1, 2, 3),
              seeds: tuple[int, ...] = tuple(range(901, 913)),
              budget_limit: int = 200, reps: int = 5,
              bootstrap_iterations: int = 2000) -> dict[str, Any]:
    """Paired candidate vs no-context baseline per task (mirrors
    parse_once_bench.run_bench; see its docstring for the method)."""
    import random

    from ace_operational import pilot_abc

    tasks = pilot_abc.generate_universe(families=list(families),
                                        levels=list(levels),
                                        seeds=list(seeds))
    config = pilot_abc.BASE_CONFIG

    def solve(mode: str, task: dict[str, Any]) -> dict[str, Any]:
        public = _public(task)
        budget = pilot_abc._budget_for(task, budget_limit)
        if mode == "base":
            return solve_no_context(public, budget, config)
        return pilot_abc.solve_with_config(public, budget, config)

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
    seeds = tuple(range(901, 913))
    if "--seeds" in argv:
        lo, hi = argv[argv.index("--seeds") + 1].split("-")
        seeds = tuple(range(int(lo), int(hi) + 1))
    result = run_bench(seeds=seeds)
    slim = {k: v for k, v in result.items() if k != "per_task"}
    print(json.dumps(slim, indent=1))
    return 0 if result["verdict"] != "EQUIVALENCE_FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
