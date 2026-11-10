#!/usr/bin/env python3
"""Public preregistered diagnostic; terminal cells never select or revise programs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from ace_cognition.reasoning import (BudgetExhausted, Meter, Problem, ReasoningMemory,
                                    SCHEMA, canonical, digest, encode_program,
                                    implementation_digest, predict, solve, verify_development)
from ace_component_synthesis.component_synthesizer import ComponentSynthesizer


X, Y = {"var": "x"}, {"var": "y"}


def op(name, a, b):
    return {"op": name, "args": [a, b]}


# Explicit researcher-supplied truth and advice fixtures, not autonomous discovery.
RULES = (
    ("add", lambda x, y: x + y, op("add", X, Y)),
    ("subtract", lambda x, y: x - y, op("sub", X, Y)),
    ("multiply", lambda x, y: x * y, op("mul", X, Y)),
    ("double_sum", lambda x, y: 2 * (x + y), op("mul", {"const": 2}, op("add", X, Y))),
    ("square_shift", lambda x, y: x * x + y, op("add", op("mul", X, X), Y)),
    ("equality", lambda x, y: x == y, op("eq", X, Y)),
    ("less", lambda x, y: x < y, op("lt", X, Y)),
    ("sum_equals_two", lambda x, y: x + y == 2, op("eq", op("add", X, Y), {"const": 2})),
)
SEEDS = (20261110, 20261111, 20261112)


def sample_splits(seed):
    rng = random.Random(seed)
    used = set()
    splits = []
    for radius, count in ((3, 12), (6, 12), (12, 24)):
        pool = [(x, y) for x in range(-radius, radius + 1)
                for y in range(-radius, radius + 1) if (x, y) not in used]
        rng.shuffle(pool)
        chosen = pool[:count]
        used.update(chosen)
        splits.append(chosen)
    return splits


def make_problem(rule, seed, suffix=""):
    name, fn, _ = rule
    train, val, terminal = sample_splits(seed)
    rows = lambda pairs: [{"inputs": {"x": x, "y": y}, "output": fn(x, y)} for x, y in pairs]
    return {"schema": SCHEMA, "id": f"{name}_{seed}{suffix}",
            "goal": "Infer a bounded rule from labeled development observations.",
            "train": rows(train), "validation": rows(val)}, rows(terminal)


def measured(fn):
    cpu, wall = time.process_time(), time.perf_counter()
    value = fn()
    return value, {"cpu_seconds": time.process_time() - cpu,
                   "wall_seconds": time.perf_counter() - wall,
                   "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def fresh_baseline(problem):
    meter = Meter()
    result = {"status": "ABSTAIN", "program": None, "search_candidates": None}
    try:
        fitted = ComponentSynthesizer(library=meter.library(), max_level=2,
                                     max_candidates=5000, timeout_sec=5).synthesize(problem.train)
        result["search_candidates"] = fitted.candidates_generated
        if fitted.program and verify_development(fitted.program, problem, meter) is None:
            result.update(status="STAGED_EMPIRICAL", program=encode_program(fitted.program))
    except BudgetExhausted:
        pass
    result["primitive_operations"] = meter.used
    return result


def terminal_score(program, rows):
    # Terminal scoring is a separate caller, after all development decisions.
    if program is None:
        return {"correct": 0, "total": len(rows), "abstained": len(rows), "predictions": [],
                "primitive_operations": 0}
    meter = Meter()
    preds = [predict(program, row["inputs"], meter) for row in rows]
    hits = sum(type(a) is type(r["output"]) and a == r["output"] for a, r in zip(preds, rows))
    return {"correct": hits, "total": len(rows), "abstained": 0, "predictions": preds,
            "primitive_operations": meter.used}


def run():
    cells, profiles, retention = [], [], []
    for seed in SEEDS:
        for rule in RULES:
            task, terminal = make_problem(rule, seed)
            problem = Problem.from_data(task)
            with tempfile.TemporaryDirectory(prefix="ace-reasoning-") as tmp:
                def internal():
                    with ReasoningMemory(tmp) as memory:
                        return solve(problem, memory=memory)
                a, pa = measured(internal)
                f, pf = measured(lambda: fresh_baseline(problem))
                b, pb = measured(lambda: solve(problem, advice=[{"source": "import os"},
                                                                 {"const": False}, rule[2]]))
                # New development inputs, same underlying rule, DISTINCT process.
                second, _ = make_problem(rule, seed + 101, "_retained")
                second_path = Path(tmp) / "new_problem.json"
                second_path.write_text(canonical(second))
                cp = subprocess.run([sys.executable, str(ROOT / "tools/ace_reasoning.py"),
                                     "--workspace", tmp, "--problem", str(second_path)],
                                    check=True, capture_output=True, text=True, timeout=10)
                retained = json.loads(cp.stdout)
                retention.append({"task": task["id"], "status": retained["status"],
                                  "origin": retained["origin"],
                                  "search_candidates": retained["search_candidates"],
                                  "program_digest_unchanged": a["program_digest"] == retained["program_digest"],
                                  "primitive_operations": retained["primitive_operations"]})
            # No terminal labels enter A, F, B or retention selection.
            weak_preds = [row["inputs"]["x"] + row["inputs"]["y"] for row in terminal]
            weak_hits = sum(type(p) is type(r["output"]) and p == r["output"]
                            for p, r in zip(weak_preds, terminal))
            cells.append({"task": task["id"], "family": rule[0], "seed": seed,
                          "train": task["train"], "validation": task["validation"], "terminal": terminal,
                          "A_internal": {"decision": a, "terminal": terminal_score(a["program"], terminal)},
                          "F_same_fresh_solver": {"decision": f, "terminal": terminal_score(f["program"], terminal)},
                          "B_SYNTHETIC_FIXTURE": {"decision": b, "terminal": terminal_score(b["program"], terminal)},
                          "weak_fixed_add": {"correct": weak_hits, "total": len(terminal)}})
            profiles.append({"task": task["id"], "A": pa, "F": pf, "B_fixture": pb})
    # Same development evidence, different unobserved terminal semantics. No tuning.
    hidden_task, terminal = make_problem(RULES[0], SEEDS[0])
    hidden_decision = solve(hidden_task)
    inverted = [{"inputs": r["inputs"], "output": r["output"] + 1} for r in terminal]
    hidden = {"decision": hidden_decision,
              "terminal": terminal_score(hidden_decision["program"], inverted),
              "false_admission": hidden_decision["status"] == "STAGED_EMPIRICAL",
              "interpretation": "Identical development data cannot reveal an unobserved rule change."}
    family_pass = {name: all(c["A_internal"]["terminal"]["correct"] / 24 >= .95
                            for c in cells if c["family"] == name) for name, _, _ in RULES}
    report = {"schema": "ace.reasoning.public.v1", "protocol": "docs/research/ACE_INTERNAL_REASONING_PROTOCOL_20261110.md",
              "implementation_digest": implementation_digest(), "seeds": SEEDS, "cells": cells,
              "retention": retention, "hidden_shift": hidden,
              "summary": {"family_pass": family_pass, "H1_engineering_pass": sum(family_pass.values()) >= 7,
                          "H3_within_rule_retention_pass": all(r["origin"] == "REVALIDATED_MEMORY" and
                              r["search_candidates"] == 0 and r["program_digest_unchanged"] for r in retention),
                          "A_correct": sum(c["A_internal"]["terminal"]["correct"] for c in cells),
                          "F_correct": sum(c["F_same_fresh_solver"]["terminal"]["correct"] for c in cells),
                          "B_fixture_correct": sum(c["B_SYNTHETIC_FIXTURE"]["terminal"]["correct"] for c in cells),
                          "terminal_predictions_per_arm": len(cells) * 24,
                          "development_labels_unique": len(cells) * 24,
                          "retention_development_labels": len(retention) * 24,
                          "terminal_labels_unique": len(cells) * 24,
                          "external_model_calls": 0, "external_provider_cost_usd": 0,
                          "real_B": "NOT_RUN_NO_AUTHENTICATED_PROVIDER", "real_C": "NOT_RUN_NO_AUTHENTICATED_PROVIDER",
                          "scientific_status": "NOT_ASSESSED", "release_gate": "BLOCK_RELEASE",
                          "novel_primitive_discovery": False, "cross_family_transfer": "NOT_ASSESSED"}}
    return report, {"platform": sys.platform, "python": sys.version, "pid": os.getpid(),
                    "per_task": profiles, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    "metric_limits": "RSS is process high water mark, not incremental allocation; subprocess retention excluded from per-arm CPU."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--profile", required=True)
    args = p.parse_args()
    report, profile = run()
    Path(args.output).write_text(canonical(report) + "\n")
    Path(args.profile).write_text(json.dumps(profile, indent=2) + "\n")
    print(json.dumps({"sha256": hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
                      "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
