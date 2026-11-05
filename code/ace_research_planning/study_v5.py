"""R6-v5 public online metareasoning: probe/act/search decisions under cost.

This is a researcher-specified finite policy search, not autonomous reasoning or
blind evaluation. Transfer is generated only after train/validation selection.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import random

from .planning import Meter, hierarchical_route, World, generate, forced_key_order_certificate
from .online_v5 import OnlinePolicy, PROBE_MODES, PLANNER_MODES, rollout
from .study_v2 import independent_optimal_cost
from .study_v4 import (FAMILIES as BASE_FAMILIES, _portal_edges, _interior_portals)
from .study_v2 import neutral_surprise

SEEDS = {
    "train": tuple(range(32100, 32118)),
    "validation": tuple(range(33100, 33118)),
    "transfer": tuple(range(34100, 34118)),
}
FAMILIES = BASE_FAMILIES
CONDITIONS = ("static", "neutral_closure", "reference_targeted")
BUDGETS = (300, 900)
POLICIES = tuple(OnlinePolicy(p, q) for q in PLANNER_MODES for p in PROBE_MODES)


def reference_targeted(base: World, seed: int) -> World:
    """Design stress: closure chosen on a PUBLIC fixed hierarchical reference path.

    Deliberately biased to probes on that reference; not neutral and not
    evidence of general shock-prediction capability. If NO reference-route
    edge can be closed without destroying solvability, use an explicitly
    documented neutral fallback instead of filtering out difficult seeds.
    No contestant decisions are consulted to choose the closure.
    """
    meter = Meter(10_000)
    reference_route = hierarchical_route(replace(base, shock=None), (0, 0), frozenset(), meter)
    if reference_route.route is None:
        raise ValueError("reference cannot plan initial path")
    nodes = (0,) + reference_route.route
    edges = list(dict.fromkeys(tuple(sorted((u, v))) for u, v in zip(nodes, nodes[1:])))
    random.Random(seed ^ 0xD15C0).shuffle(edges)
    for edge in edges:
        if independent_optimal_cost(base, frozenset((edge,))) is not None:
            return replace(base, shock=edge)
    # A unique path may have no legal single-edge closure. Avoid dropping the
    # seed based on outcome; preserve paired coverage with a neutral fallback.
    return neutral_surprise(base, seed ^ 0xD15C0)


def make_world(split: str, seed: int, family: str, condition: str) -> World:
    if (split not in SEEDS or seed not in SEEDS[split] or family not in FAMILIES[split]
            or condition not in CONDITIONS):
        raise ValueError("unregistered benchmark world")
    # Separate seed bank from v4; reuse only the documented, PUBLIC mechanisms.
    if family == "ordered_grid":
        base = generate(2*seed + 1, "ood")
        if not forced_key_order_certificate(base):
            raise AssertionError("ordered reference unexpectedly uncertified")
    elif family == "gated_bypass":
        basic = generate(2*seed + 1, "ood")
        base = _portal_edges(basic, ((basic.keys[0], basic.keys[-1]),
                            (0, basic.goal), (basic.keys[1], basic.goal)), needed=1)
    else:
        basic = replace(generate(seed, "ood"), locks=())
        if family == "free_grid":
            base = basic
        elif family == "terminal_portal":
            base = _portal_edges(basic, ((0, basic.keys[-1]), (basic.keys[0], basic.goal),
                                        (basic.keys[-1], basic.goal), (0, basic.keys[0])))
        elif family == "interior_portals":
            base = _interior_portals(basic, seed)
        elif family == "weight_shift":
            base = replace(basic, weights=tuple((u, v, 1 + ((seed + u*3 + v*7 + cost)%13))
                                                for u, v, cost in basic.weights))
        else:
            raise AssertionError("unexpected mechanism")
    if condition == "static":
        return base
    if condition == "neutral_closure":
        return neutral_surprise(base, seed + 900000)
    return reference_targeted(base, seed)


def utility(row: dict) -> float:
    """Prespecified synthetic reward, conditional route quality and paid probe costs.

    Task success dominates within the tested budget range. Failure attempts are
    not free; route quality reference is post-closure hindsight lower bound.
    """
    if row["success"]:
        return (1000.0 - 120.0 * (row["travel_cost"] / row["reference"] - 1.0)
                - 0.04 * row["work_units"] - 6.0 * row["failed_actions"]
                - 0.5 * row["probes"])
    return (-200.0 - 0.04 * row["work_units"]
            - 6.0 * row["failed_actions"] - 0.5 * row["probes"])


def evaluate(split: str, n: int, budget: int) -> list[dict]:
    if split not in SEEDS or isinstance(n, bool) or not 1 <= n <= len(SEEDS[split]):
        raise ValueError("invalid split/count")
    rows = []
    for seed in SEEDS[split][:n]:
        for family in FAMILIES[split]:
            for condition in CONDITIONS:
                world = make_world(split, seed, family, condition)
                blocked = frozenset((world.shock,)) if world.shock else frozenset()
                ref = independent_optimal_cost(world, blocked)
                if ref is None:
                    raise AssertionError("unsolvable benchmark world")
                targeted_actual = None
                if condition == "reference_targeted":
                    route = hierarchical_route(replace(world, shock=None), (0, 0), frozenset(), Meter(10_000))
                    candidate_edges = set(tuple(sorted((u, v))) for u,v in
                                          zip((0,)+route.route, route.route[0:])) if route.route is not None else set()
                    targeted_actual = world.shock in candidate_edges
                for policy in POLICIES:
                    result = rollout(world, policy, work_limit=budget)
                    rows.append(dict(split=split, seed=seed, family=family,
                                     condition=condition, targeted_actual=targeted_actual,
                                     policy=policy.export(), reference=ref, **result))
    return rows


def policy_rows(rows: list[dict], policy: OnlinePolicy) -> list[dict]:
    return [r for r in rows if r["policy"] == policy.export()]


def summarize(rows: list[dict], policy: OnlinePolicy) -> dict:
    a = policy_rows(rows, policy)
    if not a:
        raise ValueError("policy not in rows")
    solved = [r for r in a if r["success"]]
    return dict(n=len(a), success=len(solved),
                utility=round(mean(map(utility, a)), 6),
                mean_work=round(mean(r["work_units"] for r in a), 3),
                mean_probes=round(mean(r["probes"] for r in a), 3),
                actual_discoveries=sum(r["encountered"] for r in a),
                recovered=sum(r["recovered"] for r in a),
                prevented_failed_actions=sum(r["positive_probes"] for r in a),
                failed_actions=sum(r["failed_actions"] for r in a),
                mean_cost_ratio_success_only=round(mean(r["travel_cost"]/r["reference"] for r in solved), 5)
                if solved else None)


def fit(train: list[dict], validation: list[dict]) -> tuple[OnlinePolicy, list[dict]]:
    ranked = sorted(POLICIES, key=lambda p: (-summarize(train, p)["utility"],
                                             POLICIES.index(p)))
    shortlist = ranked[:8]
    scores = [(summarize(validation, p)["utility"], summarize(train, p)["utility"],
               i, p) for i, p in enumerate(shortlist)]
    scores.sort(key=lambda v: (-v[0], -v[1], v[2]))
    return scores[0][3], [dict(policy=x[3].export(), validation=x[0], train=x[1]) for x in scores]


def pair_delta(rows: list[dict], lhs: OnlinePolicy, rhs: OnlinePolicy, draws: int = 999) -> dict:
    """Seed-level cluster bootstrap, not independent scientific inference."""
    def grouped(policy: OnlinePolicy):
        out = {}
        for row in policy_rows(rows, policy):
            out.setdefault(row["seed"], []).append(utility(row))
        return {k: mean(v) for k, v in out.items()}
    a, b = grouped(lhs), grouped(rhs)
    if not a or set(a) != set(b):
        raise AssertionError("not matched")
    diffs = [a[s] - b[s] for s in sorted(a)]
    rng = random.Random(12621)
    bootstrap = sorted(mean(diffs[rng.randrange(len(diffs))] for _ in diffs)
                       for _ in range(draws))
    return dict(seeds=len(diffs), mean_utility_delta=round(mean(diffs), 6),
                descriptive_seed_bootstrap_95pct=[round(bootstrap[int(.025*(draws-1))],6),
                                                    round(bootstrap[int(.975*(draws-1))],6)],
                draws=draws)


def run(n_train: int = 12, n_validation: int = 12,
        n_transfer: int = 18, budgets: tuple[int, ...] = BUDGETS) -> dict:
    for s, n in (("train", n_train), ("validation", n_validation), ("transfer", n_transfer)):
        if isinstance(n, bool) or not isinstance(n, int) or n < 1 or n > len(SEEDS[s]):
            raise ValueError("invalid count")
    if (not budgets or tuple(sorted(set(budgets))) != budgets or
            any(isinstance(x, bool) or not isinstance(x, int) or not 1 <= x <= 10_000 for x in budgets)):
        raise ValueError("invalid budget")
    summaries = {}
    policy_receipts = {}
    transfer_rows = []
    for budget in budgets:
        train = evaluate("train", n_train, budget)
        validation = evaluate("validation", n_validation, budget)
        winner, shortlist = fit(train, validation)
        fixed = [OnlinePolicy("never", "hier"), OnlinePolicy("never", "dijkstra"),
                 OnlinePolicy("always", "hier"), OnlinePolicy("always", "dijkstra")]
        control = max(fixed, key=lambda p: (summarize(validation,p)["utility"], -POLICIES.index(p)))
        receipt = dict(budget=budget, winner=winner.export(),
                       validation_fixed_control=control.export(), shortlist=shortlist)
        frozen = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        receipt["pretransfer_freeze_sha256"] = sha256(frozen).hexdigest()
        # Transfer generation and scoring are deliberately after policy freeze.
        transfer = evaluate("transfer", n_transfer, budget)
        receipt["paired_vs_fixed"] = pair_delta(transfer, winner, control)
        # Critical negative control: an online switch is a researcher-authored
        # candidate. Compare explicitly with that SAME fixed online rule.
        receipt["paired_vs_predefined_switch"] = pair_delta(
            transfer, winner, OnlinePolicy("never", "after_discovery_dijkstra"))
        target_cases = [r for r in policy_rows(transfer, winner) if r["condition"] == "reference_targeted"]
        receipt["target_stress"] = dict(attempted=len(target_cases), actual=sum(r["targeted_actual"] for r in target_cases),
                                         neutral_fallback=sum(not r["targeted_actual"] for r in target_cases))
        policy_receipts[str(budget)] = receipt
        transfer_rows.extend(transfer)
        for split, data in (("train",train), ("validation",validation), ("transfer",transfer)):
            for label, p in (("learned",winner), ("val_fixed",control),
                             ("never_hier",OnlinePolicy("never","hier")),
                             ("never_dijkstra",OnlinePolicy("never","dijkstra")),
                             ("always_hier",OnlinePolicy("always","hier")),
                             ("always_dijkstra",OnlinePolicy("always","dijkstra")),
                             ("predefined_switch",OnlinePolicy("never","after_discovery_dijkstra"))):
                summaries[f"{budget}/{split}/{label}"] = summarize(data,p)
        for condition in CONDITIONS:
            for label, p in (("learned",winner), ("val_fixed",control),
                             ("never_hier",OnlinePolicy("never","hier")),
                             ("always_hier",OnlinePolicy("always","hier")),
                             ("predefined_switch",OnlinePolicy("never","after_discovery_dijkstra"))):
                slice_rows = [r for r in transfer if r["condition"] == condition]
                summaries[f"{budget}/transfer/{condition}/{label}"] = summarize(slice_rows,p)
    report = dict(protocol="ACE-R6-v5-public-online-probing", seeds={k:[v[0],v[-1]] for k,v in SEEDS.items()},
                  sample_counts={"train":n_train,"validation":n_validation,"transfer":n_transfer},
                  families=FAMILIES, conditions=CONDITIONS, budgets=budgets,
                  candidates=len(POLICIES),
                  disclosure="Researcher-authored finite probe/plan policies; route-targeted stress is biased to "
                  "hierarchical reference. Transfer mechanisms remain public and author-visible. "
                  "Targeting falls back to a neutral closure if every reference-route closure makes the task unsolvable. "
                  "The planner does not see the hidden shock before sensing or failed action; "
                  "instrumented work units are not FLOPs. Hindsight optimal is only a lower bound.",
                  policies=policy_receipts, summary=summaries, transfer_rows=transfer_rows)
    report["sha256"] = sha256(json.dumps(report,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
    return report


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--n-train",type=int,default=12)
    p.add_argument("--n-validation",type=int,default=12)
    p.add_argument("--n-transfer",type=int,default=18)
    p.add_argument("--output",default="/tmp/r6_v5_results.json")
    args=p.parse_args()
    result=run(args.n_train,args.n_validation,args.n_transfer)
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("R6-v5",result["sha256"],"cases",len(result["transfer_rows"]))
    for budget in BUDGETS:
        print(budget,result["policies"][str(budget)]["winner"],
              result["policies"][str(budget)]["paired_vs_fixed"])

if __name__ == "__main__":
    main()
