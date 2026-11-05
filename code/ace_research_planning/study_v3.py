"""ACE R6-v3 public topology-shift stress: graph shortcuts break Manhattan A*.

All seeds and mechanism choices are author-visible; this is a falsification
benchmark, not a blind proof of autonomous generalization.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from .planning import World, generate, geometric_lower_bound_certificate, simulate
from .study_v2 import independent_optimal_cost, neutral_surprise

# Public, fixed before examining v3 outcomes. Not a blind scientific holdout.
SEEDS = tuple(range(12100, 12124))
BUDGETS = (60, 180, 1800)
METHODS = ("greedy", "hier_replan", "structural", "astar", "dijkstra", "astar_metric", "robust")
FAMILIES = ("paired_control", "nonlocal_portals")
CONDITIONS = ("static", "neutral_closure")


def make_world(seed: int, family: str, condition: str) -> World:
    if seed not in SEEDS or family not in FAMILIES or condition not in CONDITIONS:
        raise ValueError("v3 only accepts its predeclared seeds/families/conditions")
    # The common seed controls graph, edge weights and key positions. In v3 all
    # key orders are free; one variant changes *only* extra physical shortcuts.
    base = replace(generate(seed, "ood", False), locks=())
    if family == "nonlocal_portals":
        weights = list(base.weights)
        used = {tuple(sorted((a, b))) for a, b, _ in weights}
        candidates = [(0, base.keys[-1]), (base.keys[0], base.goal),
                      (base.keys[-1], base.goal), (0, base.keys[0])]
        added = 0
        for a, b in candidates:
            edge = tuple(sorted((a, b)))
            if a == b or edge in used:
                continue
            if abs(a % base.width - b % base.width) + abs(a // base.width - b // base.width) < 4:
                continue
            weights.append((edge[0], edge[1], 1))
            used.add(edge)
            added += 1
            if added == 2:
                break
        if added < 1:
            raise AssertionError("portal family failed to create novel topology")
        adj = [set(neighbors) for neighbors in base.adjacency]
        for a, b, _ in weights[len(base.weights):]:
            adj[a].add(b)
            adj[b].add(a)
        base = replace(base, adjacency=tuple(tuple(sorted(neighbors)) for neighbors in adj),
                       weights=tuple(sorted(weights)))
        if geometric_lower_bound_certificate(base):
            raise AssertionError("nonlocal control lacks a metric violation")
    if condition == "neutral_closure":
        return neutral_surprise(base, seed + 1000000)
    return base


def run(n: int = 24, budgets: tuple[int, ...] = BUDGETS) -> dict:
    if not (1 <= n <= len(SEEDS)):
        raise ValueError("n outside prespecified seed set")
    if not (budgets and tuple(sorted(set(budgets))) == budgets
            and all(isinstance(b, int) and not isinstance(b, bool) and 1 <= b <= 100000 for b in budgets)):
        raise ValueError("bad budgets")
    rows = []
    for seed in SEEDS[:n]:
        for family in FAMILIES:
            for condition in CONDITIONS:
                w = make_world(seed, family, condition)
                blocked = frozenset((w.shock,)) if w.shock else frozenset()
                reference = independent_optimal_cost(w, blocked)
                if reference is None:
                    raise AssertionError("reference world unsolvable")
                for budget in budgets:
                    for method in METHODS:
                        outcome = simulate(w, method, budget)
                        rows.append(dict(seed=seed, family=family, condition=condition, method=method,
                                         budget=budget, vertices=w.width*w.height, keys=len(w.keys),
                                         visible_metric_certificate=geometric_lower_bound_certificate(w),
                                         offline_lower_bound=reference,
                                         **{k: v for k, v in outcome.items() if k != 'budget'}))
    summary = {}
    for family in FAMILIES:
        for condition in CONDITIONS:
            for budget in budgets:
                for method in METHODS:
                    rs = [r for r in rows if r['family'] == family and r['condition'] == condition
                          and r['budget'] == budget and r['method'] == method]
                    good = [r for r in rs if r['success']]
                    summary[f'{family}/{condition}/cap{budget}/{method}'] = dict(
                        n=len(rs), success=len(good), encounters=sum(r['shock_encountered'] for r in rs),
                        recovered=sum(r['shock_encountered'] and r['success'] for r in rs),
                        optimal_on_static=sum(r['success'] and r['cost'] == r['offline_lower_bound']
                                              for r in rs) if condition == 'static' else None,
                        mean_expanded=round(mean(r['expanded'] for r in rs),2),
                        mean_heuristics=round(mean(r['heuristics'] for r in rs),2),
                        mean_metric_edge_scans=round(mean(r.get('metric_edge_scans',0) for r in rs),2),
                        mean_cost_ratio_success_only=round(mean(r['cost']/r['offline_lower_bound'] for r in good),4)
                        if good else None,
                        budget_failures=sum(r['status']=='budget' for r in rs))
    out = dict(protocol='ace-r6-v3-public-metric-topology-shift', seed_range=[SEEDS[0],SEEDS[n-1]],
               budgets=list(budgets), families=FAMILIES, conditions=CONDITIONS, methods=METHODS,
               disclosure='AUTHOR-VISIBLE falsification only. Portals deliberately violate the Manhattan '
               'edge lower-bound. Node expansions do not equal compute; graph-metric Dijkstra '
               'precomputation counted as scans and heap pops. Dynamic oracle is hindsight lower bound.',
               summary=summary, rows=rows)
    out['sha256'] = sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return out


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='/tmp/ace_r6_v3.json')
    p.add_argument('--n',type=int,default=24)
    a=p.parse_args()
    report=run(a.n)
    Path(a.output).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print('R6-v3 runs',len(report['rows']),'digest',report['sha256'])
    for condition in CONDITIONS:
        for method in METHODS:
            print('nonlocal_portals/'+condition+'/cap1800/'+method,
                  report['summary']['nonlocal_portals/'+condition+'/cap1800/'+method])

if __name__ == '__main__':
    main()
