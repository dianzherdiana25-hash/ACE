"""Score a frozen public bank through isolated workers and a resumable evaluator."""

import argparse
import gzip
import json
import os
from pathlib import Path

from e13.contract import canonical_json, integer, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms

from .e14g_bank import FAMILIES, LENGTHS, PROBE_N, alphabet, oracle, sha, trace
from .e14g_isolation import invoke, validate_boundary, worker_mount

REPO = Path(__file__).resolve().parents[2]
BANK = "evidence/e14/e14g_public_bank_v1.json.gz"
HISTORY = "evidence/e14/e14g_prior_inputs_v1.json.gz"
LOCK = "design/e1.4/E14G_LOCK_v1.json"
PROTOCOL = "design/e1.4/E14G_PROTOCOL_v1.md"
BOUND = (BANK, HISTORY, PROTOCOL, "tools/ace_bounded_runner.py",
         *(f"code/e14/{name}.py" for name in ("__init__", "e14g_bank", "e14g_worker",
                                              "e14g_isolation", "e14g_run", "e14g_audit", "test_e14g")),
         *(f"code/e13/{name}.py" for name in ("__init__", "contract", "isolation", "comparators",
                                               "dsl", "extension", "baseline", "blind", "evaluator/__init__",
                                               "evaluator/run_ledger")))
ORDER = 142104
POLICIES = ("no_label", "gini", "minimax", "static", "random", "hindsight", "informed")
METRICS = ("cpu_us", "rss_kib", "wall_us")


def frozen():
    manifest = json.loads((REPO / LOCK).read_bytes())
    actual = {name: sha((REPO / name).read_bytes()) for name in BOUND}
    if manifest != {"version": 1, "sha256": actual}:
        raise ValueError("E1.4g freeze manifest mismatch")
    bank = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(bank), sha(bank), manifest


def pick(partitions, pool, family):
    return {
        "gini": min(range(8), key=lambda i: (sum(n * n for n in partitions[i]), i)),
        "minimax": min(range(8), key=lambda i: (max(partitions[i]), -len(partitions[i]), i)),
        "static": min(range(8), key=lambda i: (-len(trace(family, pool[i])), i)),
    }


def check_worker(row, family, length, demos, inputs, operation):
    fields = ("partitions",) if operation == "select" else ("word", "predictions")
    require_fields(row, *fields, *METRICS, "candidates", "fit_matches", "fit_comparisons",
                   "prediction_calls")
    size = len(alphabet(family)) ** length
    candidates = integer(row["candidates"], 1, size)
    integer(row["fit_matches"], 0, len(demos))
    if row["fit_comparisons"] != size * len(demos):
        raise ValueError("wrong fit comparison count")
    if operation == "select":
        parts = row["partitions"]
        if (len(parts) != len(inputs) or row["prediction_calls"] != candidates * len(inputs)
                or any(part != sorted(part) or sum(part) != candidates
                       or any(type(n) is not int or n <= 0 for n in part) for part in parts)):
            raise ValueError("invalid committee partitions")
    else:
        word = row["word"]
        if (len(word) != length or any(type(x) is not int or x not in alphabet(family) for x in word)
                or len(row["predictions"]) != len(inputs) or row["prediction_calls"] != len(inputs)):
            raise ValueError("invalid prediction response")
        for raw, prediction in zip(inputs, row["predictions"], strict=True):
            if family == "S":
                if (type(prediction) is not list or len(prediction) != len(raw) - 1
                        or any(type(bit) is not int or bit not in (0, 1) for bit in prediction)):
                    raise ValueError("invalid symbol prediction")
            elif prediction is not None and (type(prediction) is not int
                                             or prediction != sum(edge[3] for edge in raw["edges"])):
                raise ValueError("invalid graph prediction")


def score_world(root, block, world):
    family, length, pool, probes = (block[key] for key in ("family", "length", "pool", "probes"))
    word = tuple(block["words"][world])

    def label(raw):
        return {"input": raw, "output": oracle(family, word, raw)}

    demos, queries = ([label(raw) for raw in block[key]] for key in ("demos", "pool"))
    gold = [oracle(family, word, raw) for raw in probes]
    resources = []

    def worker(operation, data, inputs, grammar=5):
        row = invoke(root, family, operation, data, inputs, length=grammar)
        check_worker(row, family, grammar, data, inputs, operation)
        resources.append({**{key: row.pop(key) for key in METRICS}, "operation": operation})
        return row

    def fitted(data, grammar=5):
        row = worker("predict", data, probes, grammar)
        row["correct"] = sum(pred == target for pred, target in zip(row["predictions"], gold, strict=True))
        return row

    selection = worker("select", demos, pool)
    chosen = pick(selection["partitions"], pool, family)
    baseline = fitted(demos)
    alternatives = [fitted([*demos, query]) for query in queries]
    informed_selection = worker("select", demos, pool, length)
    informed_query = pick(informed_selection["partitions"], pool, family)["gini"]
    informed = fitted([*demos, queries[informed_query]], length)
    outcomes = [row["correct"] for row in alternatives]
    return {
        "status": "scored", "correct": baseline["correct"], "total": len(gold),
        "selection": selection, "chosen": chosen, "no_label": baseline, "branches": alternatives,
        "informed_selection": informed_selection, "informed_query": informed_query, "informed": informed,
        "score_x8": {"no_label": 8 * baseline["correct"],
                     **{name: 8 * outcomes[i] for name, i in chosen.items()},
                     "random": sum(outcomes), "hindsight": 8 * max(outcomes),
                     "informed": 8 * informed["correct"]},
        "oracle_calls": len(demos) + len(queries) + len(gold), "resources": resources,
    }


def summarize(rows):
    cells = []
    for distribution in ("natural", "opportunity"):
        for family in FAMILIES:
            for length in LENGTHS:
                regime = "related" if length == 5 else "unrelated"
                group = [row for row in rows if row["block"].startswith(distribution + ":")
                         and row["family"] == family and row["regime"] == regime]
                pairs = []
                for block_id in sorted({row["block"] for row in group}):
                    pair = [row["score_x8"] for row in group if row["block"] == block_id]
                    pairs.append({name: sum(row[name] for row in pair) for name in POLICIES})
                score = {name: sum(pair[name] for pair in pairs) for name in POLICIES}
                positives = {
                    f"{a}_gt_{b}": sum(pair[a] > pair[b] for pair in pairs)
                    for a, b in (("hindsight", "no_label"), ("gini", "no_label"),
                                 ("gini", "random"), ("minimax", "random"),
                                 ("informed", "hindsight"))
                }
                cells.append({
                    "distribution": distribution, "family": family, "length": length, "blocks": len(pairs),
                    "worlds": len(group), "probe_total": 8 * len(group), "score_x8": score,
                    "positive_blocks": positives,
                    "gini_harm_worlds": sum(row["score_x8"]["gini"] < row["score_x8"]["no_label"] for row in group),
                    "unanimous_pools": sum(all(len(part) == 1 for part in row["selection"]["partitions"])
                                          for row in group),
                    "oracle_calls": sum(row["oracle_calls"] for row in group),
                })
    in_basis = [c for c in cells if c["distribution"] == "opportunity" and c["length"] == 5]
    out_basis = [c for c in cells if c["distribution"] == "opportunity" and c["length"] == 6]
    natural = [c for c in cells if c["distribution"] == "natural" and c["length"] == 5]

    def in_basis_pass(cell):
        positives, scores = cell["positive_blocks"], cell["score_x8"]
        return (all(positives[metric] >= 5 for metric in
                    ("hindsight_gt_no_label", "gini_gt_random", "minimax_gt_random"))
                and min(scores["gini"], scores["minimax"]) > max(scores["no_label"], scores["static"]))

    engineered = all(map(in_basis_pass, in_basis)) and all(
        c["score_x8"]["hindsight"] <= 4 * 8 * c["worlds"]
        and c["positive_blocks"]["informed_gt_hindsight"] >= 5 for c in out_basis)
    natural_gate = all(c["positive_blocks"]["hindsight_gt_no_label"] >= 3
                       and c["positive_blocks"]["gini_gt_no_label"] >= 2
                       and c["score_x8"]["gini"] > c["score_x8"]["random"] for c in natural)
    return {
        "decision": ("BENCHMARK_DEVELOPMENT_GO" if engineered else "BENCHMARK_HOLD_REDESIGN"),
        "engineered_gate": engineered, "natural_gate": natural_gate,
        "natural_decision": "NATURAL_DEVELOPMENT_GO" if natural_gate else "NATURAL_HOLD",
        "blocks": sum(c["blocks"] for c in cells), "worlds": len(rows),
        "oracle_calls": sum(r["oracle_calls"] for r in rows),
        "worker_calls": sum(len(r["resources"]) for r in rows),
        "cells": cells,
    }


def deterministic(report):
    return {**report, "rows": [{key: value for key, value in row.items() if key != "resources"}
                              for row in report["rows"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    bank, bank_sha, manifest = frozen()
    boundary = validate_boundary()
    by_arm = {}
    for block in bank["blocks"]:
        regime = "related" if block["length"] == 5 else "unrelated"
        for world in range(len(block["words"])):
            arm = Arm(block["family"], regime, f'{block["distribution"]}:{block["block"]}',
                      str(world), 0, "world")
            if arm in by_arm:
                raise ValueError("duplicate world coordinate")
            by_arm[arm] = block
    files = manifest["sha256"]
    plan = RunPlan(files["code/e14/e14g_worker.py"], bank_sha, files["code/e14/e14g_bank.py"],
                   sha(canonical_json(manifest)), ORDER, PROBE_N, tuple(by_arm))
    with worker_mount() as root:
        rows = run_arms(args.ledger, plan, lambda arm: score_world(root, by_arm[arm], int(arm.episode)))
    report = {"version": 1, "status": "completed", "plan_sha256": plan.sha256, "bank_sha256": bank_sha,
              "boundary": boundary, "summary": summarize(rows), "rows": rows}
    raw = canonical_json(report)
    temp = args.output.with_name(args.output.name + ".tmp")
    temp.write_bytes(gzip.compress(raw, mtime=0))
    os.replace(temp, args.output)
    print(json.dumps({"result_sha256": sha(raw), "deterministic_sha256": sha(canonical_json(deterministic(report))),
                      "summary": report["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
