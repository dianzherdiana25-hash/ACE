"""Exploratory R6-v2: structure-aware planning under neutral path changes.

Author-designed public synthetic evaluation; no blinded holdout or agent learning.
Run `python -m ace_research_planning.study_v2` with PYTHONPATH=code.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
from heapq import heappop, heappush
import json
from pathlib import Path
import random
from statistics import mean
from typing import Optional

from .planning import World, generate, simulate

METHODS = ("bfs", "greedy", "astar", "hier_fixed", "hier_replan", "adaptive", "structural")
# Fresh public seeds, NOT a blinded or unexposed holdout.
SEEDS = {"dev2": tuple(range(2000, 2024)), "transfer2": tuple(range(9500, 9524))}
BUDGETS = (60, 120, 1800)
CONDITIONS = ("static", "policy_targeted", "neutral")


def independent_optimal_cost(world: World, blocked: frozenset[tuple[int, int]] = frozenset()) -> Optional[int]:
    """Independent finite-state Dijkstra, not a call to the planner search routine.

    Builds action candidates from the physical edge-weight table; checks
    geometry, gate-key preconditions and pickup semantics independently.
    """
    n = world.width * world.height
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for a, b, weight in world.weights:
        if tuple(sorted((a, b))) in blocked:
            continue
        adjacency[a].append((b, weight))
        adjacency[b].append((a, weight))
    gates = set(range(len(world.keys))) if world.locks is None else set(world.locks)
    all_keys = (1 << len(world.keys)) - 1
    initial = (0, sum(1 << i for i, node in enumerate(world.keys) if node == 0))
    distances = {initial: 0}
    queue = [(0, initial)]
    while queue:
        cost, (pos, held) = heappop(queue)
        if cost != distances[(pos, held)]:
            continue
        if pos == n - 1 and held == all_keys:
            return cost
        for nxt, weight in adjacency[pos]:
            if pos % world.width != nxt % world.width:
                crossing = min(pos % world.width, nxt % world.width)
                if crossing in gates and not held & (1 << crossing):
                    continue
            new_held = held
            for i, key_pos in enumerate(world.keys):
                if key_pos == nxt:
                    new_held |= 1 << i
            state = (nxt, new_held)
            new_cost = cost + weight
            if new_cost < distances.get(state, 10**30):
                distances[state] = new_cost
                heappush(queue, (new_cost, state))
    return None


def neutral_surprise(world: World, seed: int) -> World:
    """Choose a solvability-preserving closure WITHOUT inspecting any planner route.

    Samples a deterministic shuffled list of physical edges. Conditions only
    on global solvability; does not guarantee a failure will be encountered.
    """
    options = [tuple(sorted((a, b))) for a, b, _ in world.weights]
    random.Random(seed + 7_000_001).shuffle(options)
    for edge in options:
        if independent_optimal_cost(world, frozenset((edge,))) is not None:
            return replace(world, shock=edge)
    raise RuntimeError(f"no valid neutral surprise for seed {seed}")


def world_for(family: str, seed: int, condition: str) -> World:
    if family not in SEEDS or seed not in SEEDS[family]:
        raise ValueError("seed/family not precommitted")
    source_family = "dev" if family == "dev2" else "ood"
    if condition == "policy_targeted":
        return generate(seed, source_family, True)
    world = generate(seed, source_family, False)
    if condition == "neutral":
        return neutral_surprise(world, seed)
    if condition == "static":
        return world
    raise ValueError("unknown condition")


def run(n: int = 24, budgets: tuple[int, ...] = BUDGETS) -> dict:
    if not (1 <= n <= 24 and budgets and all(1 <= b <= 100000 for b in budgets)
            and tuple(sorted(set(budgets))) == budgets):
        raise ValueError("invalid prespecified study bounds")
    rows = []
    for family, seeds in SEEDS.items():
        for seed in seeds[:n]:
            for condition in CONDITIONS:
                world = world_for(family, seed, condition)
                blocked = frozenset((world.shock,)) if world.shock else frozenset()
                ref = independent_optimal_cost(world, blocked)
                if ref is None:
                    raise AssertionError("generated task is not solvable after change")
                for budget in budgets:
                    for method in METHODS:
                        outcome = simulate(world, method, budget)
                        # The lower bound is hindsight optimal, not an achievable
                        # policy value under unknown future failures.
                        rows.append(dict(family=family, seed=seed, condition=condition,
                                         method=method, budget=budget, vertices=world.width * world.height,
                                         keys=len(world.keys), forced_order=(world.locks != ()),
                                         offline_oracle_lower_bound=ref, **{k:v for k,v in outcome.items() if k != 'budget'}))
    summary = {}
    for family in SEEDS:
        for condition in CONDITIONS:
            for budget in budgets:
                for method in METHODS:
                    r = [x for x in rows if x["family"] == family and x["condition"] == condition
                         and x["budget"] == budget and x["method"] == method]
                    successes = [x for x in r if x["success"]]
                    summary[f"{family}/{condition}/cap{budget}/{method}"] = dict(
                        n=len(r), success=len(successes), encounter=sum(x["failed_actions"] > 0 for x in r),
                        conditional_recovery=sum(x["success"] and x["failed_actions"] > 0 for x in r),
                        mean_expanded=round(mean(x["expanded"] for x in r), 2),
                        mean_heuristics=round(mean(x["heuristics"] for x in r), 2),
                        mean_cost_over_offline_lower_bound=round(mean(x["cost"] / x["offline_oracle_lower_bound"]
                                                               for x in successes), 4) if successes else None,
                        failed_due_budget=sum(x["status"] == "budget" for x in r))
    report = dict(protocol="ace-r6-v2-exploratory", seeds=SEEDS, budgets=budgets, conditions=CONDITIONS,
                  methods=METHODS, disclosure="Public author-chosen nonblinded study; prior v1 OOD was already examined. "
                      "Neutral edge sampling does not select for any planner's intended route. "
                      "Post-change oracle is a hindsight lower bound. Equal node caps are NOT equal FLOPs.",
                  summary=summary, rows=rows)
    report["sha256"] = sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/r6_v2_results.json")
    parser.add_argument("--n", type=int, default=24)
    args = parser.parse_args()
    report = run(args.n)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("protocol", report["protocol"], "cases", len(report["rows"]), "sha256", report["sha256"])
    for family in SEEDS:
        for condition in ("policy_targeted", "neutral"):
            for method in ("hier_replan", "adaptive", "structural", "astar"):
                k = f"{family}/{condition}/cap1800/{method}"
                if k in report['summary']:
                    print(k, report['summary'][k])


if __name__ == "__main__":
    main()
