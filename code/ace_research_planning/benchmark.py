"""Precommitted synthetic R6 comparison: no training, policy selection or holdout tuning."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from .planning import generate, simulate, oracle_cost

METHODS = ("bfs", "greedy", "astar", "hier_fixed", "hier_replan", "adaptive")
SEEDS = {"dev": tuple(range(1000, 1018)), "ood": tuple(range(9000, 9018))}


def run(limit: int = 1800, n: int = 18) -> dict:
    if not (1 <= n <= 18 and 1 <= limit <= 100000):
        raise ValueError("invalid fixed-budget configuration")
    rows = []
    for family in ("dev", "ood"):
        for i, seed in enumerate(SEEDS[family][:n]):
            for shock in (False, True):
                world = generate(seed, family, shock)
                actual = frozenset((world.shock,)) if world.shock else frozenset()
                reference = oracle_cost(world, actual)
                for method in METHODS:
                    result = simulate(world, method, limit)
                    rows.append(dict(family=family, seed=seed, condition="shock" if shock else "static",
                                     method=method, keys=len(world.keys), vertices=world.width * world.height,
                                     oracle_postshock_lower_bound=reference, **result))
    groups = {}
    for family in ("dev", "ood"):
        for shock in ("static", "shock"):
            for method in METHODS:
                rs = [x for x in rows if (x["family"], x["condition"], x["method"]) == (family, shock, method)]
                succeeded = [r for r in rs if r["success"]]
                groups[f"{family}/{shock}/{method}"] = dict(n=len(rs), success=sum(r["success"] for r in rs),
                    success_rate=round(mean(r["success"] for r in rs), 4),
                    expanded_mean=round(mean(r["expanded"] for r in rs), 2),
                    expanded_max=max(r["expanded"] for r in rs),
                    heuristic_calls_mean=round(mean(r["heuristics"] for r in rs), 2),
                    cost_mean_on_success=round(mean(r["cost"] for r in succeeded), 2) if succeeded else None,
                    suboptimality_mean_on_success=round(mean(r["cost"] / r["oracle_postshock_lower_bound"] for r in succeeded), 3) if succeeded else None,
                    shock_encounters=sum(r["shock_encountered"] for r in rs),
                    recovery_success=sum(r["success"] and r["shock_encountered"] for r in rs),
                    search_budget_failures=sum(r["status"] == "budget" for r in rs))
    report = dict(protocol="ace-r6-v1", seed_sets=SEEDS, limits=dict(expansions_per_agent=limit, tasks_per_family_condition=n),
                  warning="Public author-designed development & OOD splits; no independent blind validation; postshock optimum is a lower bound, not an attainable dynamic oracle.",
                  summary=groups, rows=rows)
    report["sha256"] = sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/ace_r6_benchmark.json")
    parser.add_argument("--limit", type=int, default=1800)
    parser.add_argument("--n", type=int, default=18)
    args = parser.parse_args()
    report = run(args.limit, args.n)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for key, value in report["summary"].items():
        print(key, "success", f'{value["success"]}/{value["n"]}', "expanded", value["expanded_mean"],
              "ratio", value["suboptimality_mean_on_success"], "recover", value["recovery_success"])
    print("sha256:", report["sha256"])


if __name__ == "__main__":
    main()
