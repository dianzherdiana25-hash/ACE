"""Measure a one-label disagreement query against uniform one-label controls."""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import product
from pathlib import Path
from time import perf_counter_ns, process_time_ns

from e13.contract import canonical_json
from e13.dsl import Fuel, predict
from e13.evaluator.order_challenge import _readout_key
from e13.evaluator.pilot import source_digest as e13_digest
from e13.evaluator.selection_budget import FIT_STEPS, LIMITS, evaluate_arm
from e13.extension import _definitions
from e13.patterns import pattern_ast

from .isolated import fit_isolated
from .pilot import source_digest
from .query_bank import REGIMES, answer_query, bank, bank_digest
from .query_selector import QUERY_CPU_US, QUERY_STEPS, QUERY_WALL_US, choose_query


class OneLabel:
    """Evaluator-side budget for one independent arm."""

    def __init__(self, case):
        self.case = case
        self.used = False

    def reveal(self, index):
        if self.used:
            raise ValueError("one-label budget already spent")
        result = answer_query(self.case, index)
        self.used = True
        return result


def _evaluate(episode):
    row = evaluate_arm(episode, "adaptive", fit_policy=fit_isolated,
                       reference_extension=True, keep_trace=True)
    return {"correct": sum(s["correct"] for s in row["scores"].values()),
            "total": sum(s["total"] for s in row["scores"].values()), **row}


def _refit(case, index):
    oracle = OneLabel(case)
    start = process_time_ns()
    label = oracle.reveal(index)
    oracle_cpu_us = (process_time_ns() - start) // 1_000
    raw = json.loads(case.episode.fit_request)
    raw["target"].append(label)
    score = _evaluate(replace(case.episode, fit_request=canonical_json(raw)))
    return {"question": index, "labels": int(oracle.used), "oracle_cpu_us": oracle_cpu_us, **score}


def _initial_hypotheses(raw):
    request = json.loads(raw)
    request["fuel"] = FIT_STEPS
    payload = canonical_json(request)
    return tuple(fit_isolated(payload, policy=policy) for policy in ("counter_only", "order_only"))


def _episode(case):
    counter, order = _initial_hypotheses(case.episode.fit_request)
    seed = json.loads(case.episode.fit_request)["seed"]
    choice = choose_query(counter, order, case.pool, seed=seed)
    # Each simulation starts at the same visible demonstrations and gets one label.
    # The selected active outcome is exactly the same intervention as its matched
    # random-control member, so evaluate each possible intervention only once.
    chosen = _refit(case, choice.index)
    alternatives = [chosen if index == choice.index else _refit(case, index)
                    for index in range(len(case.pool))]
    baseline = _evaluate(case.episode)
    return {
        "task_id": baseline["task_id"], "family": case.episode.family,
        "regime": case.episode.regime, "selector": asdict(choice), "initial": baseline,
        "hypotheses": [{"ast_sha256": fit.program.sha256, "status": fit.status,
                        "metrics": asdict(fit.metrics), "fit_steps": fit.steps, "trace": fit.trace}
                       for fit in (counter, order)],
        "active_question": choice.index, "uniform_one_label_arms": alternatives,
    }


def _summary(rows):
    records = []
    for family in ("S", "G"):
        for regime in REGIMES:
            group = [r for r in rows if r["family"] == family and r["regime"] == regime]
            active = [r["uniform_one_label_arms"][r["active_question"]] for r in group]
            expected = [Fraction(sum(a["correct"] for a in r["uniform_one_label_arms"]),
                                 len(r["uniform_one_label_arms"])) for r in group]
            matched = [a["correct"] - e for a, e in zip(active, expected, strict=True)]
            records.append({
                "family": family, "regime": regime, "episodes": len(group),
                "total_per_policy": sum(a["total"] for a in active),
                "initial_correct": sum(r["initial"]["correct"] for r in group),
                "active_correct": sum(a["correct"] for a in active),
                "uniform_expected_correct": float(sum(expected)),
                "active_vs_uniform": {"wins": sum(x > 0 for x in matched),
                                      "ties": sum(x == 0 for x in matched),
                                      "losses": sum(x < 0 for x in matched)},
                "selection_reasons": dict(Counter(r["selector"]["reason"] for r in group)),
            })
    return records


def _decision(summary):
    primary = [row for row in summary if row["regime"] == "witness_pool"]
    if all(row["active_correct"] > max(row["uniform_expected_correct"], row["initial_correct"])
           for row in primary):
        return "go_to_public_replication"
    return "hold_for_diagnosis"


def _signature(family, prediction):
    return prediction[-1] if family == "S" else prediction is not None


def _coverage_certificate(case):
    family = case.episode.family
    probes = case.episode.in_distribution + case.episode.extrapolation
    tables = _definitions(family, 8)
    words = [canonical_json(pattern_ast(family, pattern))
             for n in (1, 2, 3) for pattern in product(range(3), repeat=n)]

    def count_key(table, probe):
        key = _readout_key(family, table, json.loads(probe.input))
        return key if family == "S" else tuple(value is not None for value in key)

    distinguishes = []
    for a, b in zip(probes[::2], probes[1::2], strict=True):
        if _signature(family, a.expected) == _signature(family, b.expected):
            raise ValueError("out-of-basis pair has no oracle contrast")
        distinguishes.append({
            "counter_definitions": sum(count_key(t.table, a) != count_key(t.table, b) for t in tables),
            "order_words": sum(_signature(family, predict(ast, a.input, Fuel(10_000))) !=
                               _signature(family, predict(ast, b.input, Fuel(10_000))) for ast in words),
        })
    return {"family": family, "task_id": json.loads(case.episode.fit_request)["task_id"],
            "counter_basis": len(tables), "order_basis": len(words), "distinguishes": distinguishes}


def _budget(rows):
    setup_cpu = []
    setup_wall = []
    active_cpu = []
    uniform_cpu = []
    active_steps = []
    uniform_steps = []
    for row in rows:
        cpu = sum(h["metrics"]["cpu_us"] for h in row["hypotheses"])
        wall = sum(h["metrics"]["wall_us"] for h in row["hypotheses"])
        setup_cpu.append(cpu)
        setup_wall.append(wall)
        active = row["uniform_one_label_arms"][row["active_question"]]
        active_cpu.append(cpu + row["selector"]["cpu_us"] + active["total_cpu_us"])
        uniform_cpu.extend(cpu + a["total_cpu_us"] for a in row["uniform_one_label_arms"])
        steps = sum(h["fit_steps"] for h in row["hypotheses"])
        active_steps.append(steps + row["selector"]["steps"]
                            + active["fit_steps"] + active["predict_steps"])
        uniform_steps.extend(steps + a["fit_steps"] + a["predict_steps"]
                             for a in row["uniform_one_label_arms"])
    return {
        "max_initial_hypotheses_cpu_us": max(setup_cpu),
        "max_initial_hypotheses_sandbox_wall_us": max(setup_wall),
        "max_active_solver_and_selector_cpu_us": max(active_cpu),
        "max_uniform_solver_cpu_us": max(uniform_cpu),
        "max_active_solver_and_selector_steps": max(active_steps),
        "max_uniform_solver_steps": max(uniform_steps),
        "max_query_oracle_cpu_us": max(a["oracle_cpu_us"] for r in rows
                                     for a in r["uniform_one_label_arms"]),
        "selector_caps": sum(r["selector"]["reason"] == "query_budget_exhausted"
                             or r["selector"]["cpu_us"] > QUERY_CPU_US
                             or r["selector"]["wall_us"] > QUERY_WALL_US for r in rows),
        "fit_caps": sum(h["status"] == "fuel_exhausted" for r in rows for h in r["hypotheses"])
                    + sum(a["fit_status"] == "fuel_exhausted" for r in rows
                          for a in (r["initial"], *r["uniform_one_label_arms"])),
        "prediction_caps": sum(a["cap_reached"] for r in rows
                               for a in (r["initial"], *r["uniform_one_label_arms"])),
    }


def run():
    cases = bank()
    rows = [_episode(case) for case in cases]
    summary = _summary(rows)
    budget = _budget(rows)
    decision = "hold_for_resource_review" if any(
        budget[key] for key in ("selector_caps", "fit_caps", "prediction_caps")
    ) else _decision(summary)
    return {
        "mode": "public_development", "scope": "one-label acquisition on designed finite cases",
        "bank_sha256": bank_digest(cases),
        "source_sha256": hashlib.sha256(canonical_json([e13_digest(), source_digest()])).hexdigest(),
        "episodes": len(cases), "isolated_fits": sum(3 + len(r["uniform_one_label_arms"]) for r in rows),
        "limits": {**LIMITS, "query_steps": QUERY_STEPS, "query_cpu_us": QUERY_CPU_US,
                   "query_wall_us": QUERY_WALL_US},
        "summary": summary, "budget": budget, "decision": decision,
        "outside_basis": [_coverage_certificate(case) for case in cases
                          if case.episode.regime == "out_of_basis"],
        "rows": rows,
    }


def deterministic(report):
    """Keep scores, choices, fuel, decisions and hashes. Drop host timings."""
    if isinstance(report, list):
        return [deterministic(item) for item in report]
    if isinstance(report, dict):
        return {key: deterministic(value) for key, value in report.items()
                if not (key.startswith("max_") and key.endswith(("_cpu_us", "_wall_us")))
                and key not in ("cpu_us", "wall_us", "rss_kib", "oracle_cpu_us",
                                "predict_cpu_us", "total_cpu_us")}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    report = run()
    if args.verify is not None and deterministic(report) != deterministic(json.loads(args.verify.read_text())):
        raise ValueError("query pilot replay differs")
    print(json.dumps(report, separators=(",", ":")))


if __name__ == "__main__":
    main()
