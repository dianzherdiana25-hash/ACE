"""R7.2 locked public-development certificate-oriented active acquisition.

Only uses the original R7 evaluator as a locally deterministic synthetic
simulation. The R7.2 world IDs and world RNG are disjoint from pilot worlds.
No expensive oracle, sealed data, dynamic execution or runtime ACE promotion.
"""
from __future__ import annotations

import json
import math

from . import experiment as baseline

SEED = 20261106
BUDGETS = (0, 6, 12, 24)
METHODS = ("fixed", "random", "random_lcb", "certificate")
CONFIG = baseline.Config(12, 1.0)


def make_worlds(split: str, n: int) -> tuple[baseline.Task, ...]:
    if split not in ("train", "validation", "test", "ood"):
        raise ValueError("invalid research split")
    if type(n) is not int or not 1 <= n <= 1000:
        raise ValueError("invalid split size")
    family = "shift" if split == "ood" else "stable"
    base = baseline.SHIFT if family == "shift" else baseline.STABLE
    worlds = []
    for i in range(n):
        rng = baseline.rng_for(SEED, "r72-new-world", split, i)
        p = tuple(min(.99, max(.01, v + rng.uniform(-.09, .09)))
                  for v in base)
        worlds.append(baseline.Task(f"{split}:{family}:r72:{i}", family, p))
    return tuple(worlds)


def predictive_pmf(a: float, b: float, horizon: int, successes: int) -> float:
    """Beta-binomial predictive: no hidden task truth is consulted."""
    return math.exp(math.lgamma(horizon + 1)
                    - math.lgamma(successes + 1)
                    - math.lgamma(horizon - successes + 1)
                    + math.lgamma(a + successes)
                    + math.lgamma(b + horizon - successes)
                    - math.lgamma(a + b + horizon)
                    - math.lgamma(a)
                    - math.lgamma(b)
                    + math.lgamma(a + b))


def certifiable(a: float, b: float, count: int) -> bool:
    sd = math.sqrt(a*b/((a+b)**2*(a+b+1)))
    return count >= 3 and a/(a+b) - CONFIG.z*sd >= baseline.TARGET_ACCURACY


def next_certificate_group(belief: baseline.Belief, remaining: int) -> int | None:
    """Maximize expected positive payoff per next label acquisition horizon.

    Lookahead is exactly 1..min(8,remaining) acquired labels for one group.
    For each possible future success count, compute posterior predictive
    probability and risk-sensitive utility of acceptance. An already accepted
    group is excluded. Returning None is explicit early stopping.
    """
    best = (0.0, 0, 0)
    group = None
    for g in range(baseline.GROUPS):
        a, b = belief.a[g], belief.b[g]
        count = belief.counts[g]
        if certifiable(a, b, count):
            continue
        for horizon in range(1, min(8, remaining) + 1):
            expected = 0.0
            for successes in range(horizon + 1):
                new_a = a + successes
                new_b = b + horizon - successes
                if not certifiable(new_a, new_b, count + horizon):
                    continue
                mean = new_a / (new_a + new_b)
                sd = math.sqrt(new_a*new_b /
                               ((new_a + new_b)**2*(new_a + new_b + 1)))
                good = .5 * math.erfc((baseline.TARGET_ACCURACY - mean) /
                                      (sd * math.sqrt(2)))
                payoff = max(0.0, 20 * good - 60 * (1 - good))
                expected += predictive_pmf(a, b, horizon, successes) * payoff
            index = expected/horizon - 1.0  # prospective payoff minus label cost
            candidate = (index, -horizon, -g)
            if index > 0 and candidate > best:
                best = candidate
                group = g
    return group


def simulate_certificate(task: baseline.Task, prior: tuple[float, ...],
                         budget: int) -> dict:
    if budget not in BUDGETS:
        raise ValueError("unexpected budget")
    evaluator = baseline.Evaluator(task, budget)
    belief = baseline.Belief(prior, CONFIG)
    for _ in range(budget):
        group = next_certificate_group(belief, budget - evaluator.purchases)
        if group is None:
            break
        label = evaluator.query(group)
        belief.observe(group, label)
    mean = tuple(belief.mean(g) for g in range(baseline.GROUPS))
    decision = tuple(belief.accept(g, "active_lcb", CONFIG.z)
                     for g in range(baseline.GROUPS))
    return evaluator.score(mean, decision)


def aggregate_certificate(tasks: tuple[baseline.Task, ...],
                          prior: tuple[float, ...], budget: int) -> dict:
    rows = [simulate_certificate(t, prior, budget) for t in tasks]
    bins = [[0., 0., 0] for _ in range(10)]
    for row in rows:
        for j, values in enumerate(row["calibration"]):
            for k in range(3):
                bins[j][k] += values[k]
    n = sum(row["evaluated_labels"] for row in rows)
    ece = sum(abs(predicted - actual)/n
              for predicted, actual, count in bins if count)
    agg = {k: sum(row[k] for row in rows)
           for k in ("false_accepts", "true_accepts", "abstentions", "purchases")}
    accepted = agg["true_accepts"] + agg["false_accepts"]
    agg.update({"tasks": len(tasks), "budget_per_task": budget,
                "brier": round(sum(r["brier_sum"] for r in rows) / n, 6),
                "ece": round(ece, 6),
                "false_acceptance_rate": (round(agg["false_accepts"] / accepted, 6)
                                          if accepted else None),
                "correct_accepts_per_100_labels": (
                    round(100 * agg["true_accepts"] / agg["purchases"], 6)
                    if agg["purchases"] else None)})
    return agg


def validation_smoke() -> dict:
    train = make_worlds("train", 30)
    validation = make_worlds("validation", 12)
    prior, offline_labels = baseline.fit_prior(train)
    return {"prior": prior, "offline_training_labels": offline_labels,
            "validation": {
                method: (aggregate_certificate(validation, prior, 24)
                         if method == "certificate" else baseline.aggregate(
                             validation, prior, method,
                             CONFIG if method == "random_lcb"
                             else baseline.Config(0, 1.0), 24))
                for method in METHODS}}


def utility(row: dict) -> int:
    return (20*row["true_accepts"] - 60*row["false_accepts"]
            - 2*row["abstentions"] - row["purchases"])


def run_final() -> dict:
    """Run after protocol and code lock; score both new final splits ONCE."""
    train = make_worlds("train", 30)
    prior, offline_labels = baseline.fit_prior(train)
    splits = {"test": make_worlds("test", 24),
              "ood": make_worlds("ood", 24)}
    result = {}
    for split, tasks in splits.items():
        result[split] = {}
        for budget in BUDGETS:
            key = str(budget)
            result[split][key] = {}
            for method in METHODS:
                row = (aggregate_certificate(tasks, prior, budget)
                       if method == "certificate"
                       else baseline.aggregate(tasks, prior, method,
                              CONFIG if method == "random_lcb"
                              else baseline.Config(0, 1.0), budget))
                accepted = row["true_accepts"] + row["false_accepts"]
                row["false_acceptance_rate"] = (
                    round(row["false_accepts"]/accepted, 6) if accepted else None)
                row["utility"] = utility(row)
                result[split][key][method] = row
        ceilings = [baseline.Evaluator(t, 0).oracle_upper_bound() for t in tasks]
        result[split]["oracle_ceiling"] = {
            k: sum(a[k] for a in ceilings)
            for k in ("true_accepts", "false_accepts", "abstentions", "purchases")}
    verdict = {}
    for split in ("test", "ood"):
        active = result[split]["24"]["certificate"]
        matched = result[split]["24"]["random_lcb"]
        verdict[split] = {
            "safe_coverage_not_worse": active["true_accepts"] >= matched["true_accepts"],
            "false_acceptance_not_worse": active["false_accepts"] <= matched["false_accepts"],
            "strict_improvement": (
                active["true_accepts"] > matched["true_accepts"] or
                active["false_accepts"] < matched["false_accepts"]),
            "positive_coverage": active["true_accepts"] > 0}
    success = all(v["safe_coverage_not_worse"] and
                  v["false_acceptance_not_worse"] and
                  v["positive_coverage"] for v in verdict.values()) and any(
                      v["strict_improvement"] for v in verdict.values())
    return {
        "status": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
        "protocol": "R72_PROTOCOL.md", "seed": SEED,
        "source_prior": prior,
        "offline_training_labels": offline_labels,
        "config": {"strength":CONFIG.strength, "z":CONFIG.z},
        "split_hashes": {name:baseline.digest([t.uid for t in tasks])
                         for name, tasks in splits.items()},
        "results": result,
        "precommitted_gate": verdict, "gate_passed": success,
        "interpretation": "HOLD until independently reproduced and sealed",
        "known_limitations": [
            "the original R7 in-process evaluator and old RNG are reused",
            "new world IDs and world jitter are disjoint from R7.1",
            "source prior is not shift-aware",
            "one synthetic mechanism-change family, not a real model benchmark",
            "pilot after final read is public development, not an independently sealed holdout",
            "lower confidence bound is heuristic Gaussian, not guaranteed coverage"]}


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=("validation", "final"), required=True)
    a = p.parse_args()
    value = validation_smoke() if a.phase == "validation" else run_final()
    print(json.dumps(value, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
