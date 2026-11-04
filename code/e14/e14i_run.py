"""Run the frozen E1.4i benchmark with isolated and resumable workers."""

import argparse
import gzip
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, integer, read_json, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, alphabet, oracle, sha
from .e14g_isolation import invoke, validate_boundary, worker_mount
from .e14g_run import METRICS, REPO, check_worker
from .e14h_route import choose_grammar, load_bank
from .e14i_bank import SEEDS, build

BANK = "evidence/e14/e14i_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14I_LOCK_v1.json"
PROTOCOL = "design/e1.4/E14I_PROTOCOL_v1.md"
SELECTOR = "code/e14/e14i_selector.py"
FILES = (BANK, PROTOCOL, "design/e1.4/E14H_LOCK_v1.json", SELECTOR, "code/e14/e14i_bank.py",
         "code/e14/e14i_run.py", "code/e14/e14i_audit.py", "code/e14/test_e14i.py")
NAMES = ("cross", "e14h", "zero", "random", "hindsight")


def manifest():
    return {"version": 1, "sha256": {name: sha((REPO / name).read_bytes()) for name in FILES}}


def frozen():
    load_bank()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4i freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    by_arm = {}
    for block in bank["blocks"]:
        for condition, pool in block["pools"].items():
            for word in block["words"]:
                regime = "related" if len(word) == 5 else "unrelated"
                arm = Arm(block["family"], regime, f'{condition}:{block["slot"]}', str(len(word)), 0, "cross")
                verify(arm not in by_arm, "duplicate world")
                by_arm[arm] = (block, word, pool)
    verify(len(by_arm) == 72, "unexpected world count")
    return by_arm


@contextmanager
def selector_mount():
    with worker_mount() as root:
        shutil.copyfile(REPO / SELECTOR, root / "e14/e14i_selector.py")
        yield root


def histogram(value):
    return {(tuple(label) if isinstance(label, list) else label): count for label, count in value}


def invoke_selector(root, family, demos, pool):
    command = ("import sys; sys.path.insert(0, '/solver'); from e14.e14i_selector import main; "
               f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    packet = canonical_json({"family": family, "demos": demos, "inputs": pool})
    output, wall = _sandbox_python(["-c", command], packet, solver=root)
    row = read_json(output, 16_384)
    require_fields(row, "classes", "cpu_us", "rss_kib")
    integer(row["cpu_us"], 0, 1_000_000)
    integer(row["rss_kib"], 1, 131_072)
    integer(wall, 0, 3_000_000)
    classes = row["classes"]
    require_fields(classes, "5", "6")
    for length, record in classes.items():
        require_fields(record, "fit_matches", "candidates", "histograms", "fit_comparisons", "prediction_calls")
        size = len(alphabet(family)) ** int(length)
        integer(record["fit_matches"], 0, 32)
        n = integer(record["candidates"], 1, size)
        verify(record["fit_comparisons"] == size * 32 and record["prediction_calls"] == 8 * n
               and len(record["histograms"]) == 8, "invalid selector resource accounting")
        for hist in record["histograms"]:
            counts = histogram(hist)
            verify(len(counts) == len(hist) and sum(counts.values()) == n
                   and all(type(c) is int and c > 0 for c in counts.values()), "invalid predictive histogram")
    return classes, {"cpu_us": row["cpu_us"], "rss_kib": row["rss_kib"], "wall_us": wall, "kind": "selector"}


def distances(classes):
    left, right = classes["5"], classes["6"]
    a, b = left["candidates"], right["candidates"]
    numerators = []
    for c5, c6 in zip(left["histograms"], right["histograms"], strict=True):
        x, y = histogram(c5), histogram(c6)
        numerators.append(sum(abs(b * x.get(k, 0) - a * y.get(k, 0)) for k in x.keys() | y.keys()))
    return numerators, 2 * a * b


def compatible(rows, seen):
    fits = [int(length) for length, row in rows.items() if row["fit_matches"] == seen]
    return fits[0] if len(fits) == 1 else None


def choice(classes, numerators):
    route = choose_grammar(classes["5"]["fit_matches"], classes["6"]["fit_matches"])
    h_query = min(range(8), key=lambda i: sum(count**2 for _, count in classes[str(route)]["histograms"][i]))
    both = all(row["fit_matches"] == 32 for row in classes.values())
    cross_query = numerators.index(max(numerators)) if both and max(numerators) > 0 else None
    return route, h_query, cross_query


def rate(family, predicted, gold):
    exact = sum(p == y for p, y in zip(predicted, gold, strict=True))
    false_positives = (sum(p is not None and y is None for p, y in zip(predicted, gold, strict=True))
                       if family == "G" else
                       sum(any(a > b for a, b in zip(p, y, strict=True)) for p, y in zip(predicted, gold, strict=True)))
    return exact, false_positives


def outcome(fits, diagnosis, fallback, target_length, labels):
    grammar = fallback if diagnosis is None else diagnosis
    fit = fits[str(grammar)]
    return {"diagnosis": diagnosis, "exact": fit["correct"], "false_positive": fit["false_positive"],
            "diagnosed_correct": int(diagnosis == target_length), "abstained": int(diagnosis is None),
            "labels": labels}


def evaluate(root, block, word, pool):
    family, probes = block["family"], block["probes"]
    target = tuple(word)

    def label(raw):
        return {"input": raw, "output": oracle(family, target, raw)}

    demos, queries = ([label(raw) for raw in role] for role in (block["demos"], pool))
    gold = [oracle(family, target, raw) for raw in probes]
    classes, resource = invoke_selector(root, family, demos, pool)
    resources = [resource]

    def fit(known):
        rows = {}
        for length in LENGTHS:
            row = invoke(root, family, "predict", known, probes, length=length)
            check_worker(row, family, length, known, probes, "predict")
            resources.append({**{name: row.pop(name) for name in METRICS}, "kind": "fit"})
            row["correct"], row["false_positive"] = rate(family, row["predictions"], gold)
            rows[str(length)] = row
        return rows

    base = fit(demos)
    branches = [fit([*demos, q]) for q in queries]
    numerators, denominator = distances(classes)
    route, h_query, cross_query = choice(classes, numerators)
    zero = outcome(base, compatible(base, 32), route, len(word), 0)
    one = [outcome(rows, compatible(rows, 33), route, len(word), 1) for rows in branches]
    cross = zero if cross_query is None else one[cross_query]
    old = outcome(branches[h_query], route, route, len(word), 1)
    return {
        "status": "scored", "correct": cross["exact"], "total": 8,
        "classes": classes, "distance": [numerators, denominator], "route_h": route,
        "query_h": h_query, "query_cross": cross_query, "base": base, "branches": branches,
        "outcomes": {"zero": zero, "e14h": old, "cross": cross, "one_label": one},
        "resources": resources, "oracle_calls": len(demos) + len(queries) + len(gold),
    }


def totals(rows):
    metrics = ("exact", "diagnosed_correct", "false_positive", "abstained", "labels")
    sums = {name: dict.fromkeys(metrics, 0) for name in NAMES}
    # Hindsight bounds each metric separately. It is not a deployable arm.
    bounds = {"exact": max, "diagnosed_correct": max, "false_positive": min,
              "abstained": min, "labels": min}
    for row in rows:
        out = row["outcomes"]
        for key in metrics:
            for name in ("cross", "e14h", "zero"):
                sums[name][key] += 8 * out[name][key]
            choices = [branch[key] for branch in out["one_label"]]
            sums["random"][key] += sum(choices)
            sums["hindsight"][key] += 8 * bounds[key](choices)
    return sums


def summarize(rows):
    cells = []
    engineered_pass = []
    for family in FAMILIES:
        for condition, length in (("natural", 5), ("natural", 6), ("witness", None), ("no_witness", None)):
            group = [row for row in rows if row["family"] == family and row["block"].startswith(condition + ":")
                     and (length is None or row["episode"] == str(length))]
            blocks = {row["block"] for row in group}
            solved_blocks = sum(all(row["outcomes"]["cross"]["diagnosed_correct"] for row in group
                                    if row["block"] == block) for block in blocks)
            ambiguous = [r for r in group if all(c["fit_matches"] == 32 for c in r["classes"].values())]
            sums = totals(group)
            cells.append({
                "family": family, "condition": condition, "length": length, "blocks": len(blocks),
                "worlds": len(group), "diagnosed_blocks": solved_blocks, "ambiguous_worlds": len(ambiguous),
                "distance_positive_ambiguous": sum(max(r["distance"][0]) > 0 for r in ambiguous),
                "hindsight_diagnosable_ambiguous": sum(any(x["diagnosed_correct"] for x in r["outcomes"]["one_label"])
                                                      for r in ambiguous),
                "hindsight_gain_ambiguous": sum(max(x["exact"] for x in r["outcomes"]["one_label"])
                                                > r["outcomes"]["zero"]["exact"] for r in ambiguous),
                "score_x8": sums,
            })
            cross = sums["cross"]
            if condition == "witness":
                engineered_pass.append(solved_blocks >= 5 and all(
                    cross[key] > max(sums["e14h"][key], sums["random"][key])
                    for key in ("exact", "diagnosed_correct")
                ) and cross["false_positive"] < sums["e14h"]["false_positive"])
            elif condition == "no_witness":
                engineered_pass.append(cross["abstained"] == 8 * len(group) and cross["labels"] == 0
                                       and all(r["outcomes"]["cross"] == r["outcomes"]["zero"] for r in group))
    return {
        "decision": "WITNESS_DEVELOPMENT_GO" if all(engineered_pass) else "WITNESS_HOLD",
        "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD",
        "worlds": len(rows), "cells": cells, "oracle_calls": sum(row["oracle_calls"] for row in rows),
        "worker_calls": sum(len(row["resources"]) for row in rows),
        "fit_comparisons": sum(record["fit_comparisons"] for r in rows
                               for fit in [r["classes"], r["base"], *r["branches"]] for record in fit.values()),
    }


def deterministic(report):
    return {**report, "rows": [{k: v for k, v in row.items() if k != "resources"} for row in report["rows"]]}


def run(ledger, output):
    bank, bank_sha, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][SELECTOR], bank_sha, lock["sha256"]["code/e14/e14i_bank.py"],
                   sha(canonical_json(lock)), SEEDS[4], 8, tuple(arms))
    with selector_mount() as root:
        canary = ("import importlib.util, sys; sys.path.insert(0, '/solver'); "
                  "print(all(importlib.util.find_spec(name) is None "
                  "for name in ('e14.e14i_bank', 'e14.e14g_bank', 'e14.e14i_run')))")
        result, _ = _sandbox_python(["-c", canary], solver=root)
        verify(result.strip() == b"True", "selector mount exposes the evaluator")
        boundary["checks"]["selector_stage_without_evaluator"] = True
        rows = run_arms(ledger, plan, lambda arm: evaluate(root, *arms[arm]))
    report = {"version": 1, "status": "completed", "bank_sha256": bank_sha, "plan_sha256": plan.sha256,
              "boundary": boundary, "rows": rows, "summary": summarize(rows)}
    temp = output.with_name(output.name + ".tmp")
    temp.write_bytes(gzip.compress(canonical_json(report), mtime=0))
    os.replace(temp, output)
    print(json.dumps(report["summary"], sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("freeze")
    runner = sub.add_parser("run")
    runner.add_argument("ledger", type=Path)
    runner.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "freeze":
        (REPO / BANK).write_bytes(gzip.compress(canonical_json(build()), mtime=0))
        (REPO / LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
