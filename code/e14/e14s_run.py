"""Exhaustively audit the bounded qualification policy against graph path costs."""

import argparse
import gzip
import json
import os
import shutil
from collections import Counter
from itertools import product
from pathlib import Path

from e13.contract import canonical_json, input_value, integer, read_json
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import sha
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14p_graph import minimum, paths
from .e14q_run import stage
from .e14r_run import frozen as prior_frozen
from .e14r_worker import mappings, witness
from .e14s_worker import decide

WORKER = "code/e14/e14s_worker.py"
SOURCE = "code/e14/e14s_run.py"
LOCK = "design/e1.4/E14S_LOCK_v1.json"
FILES = (WORKER, SOURCE, "code/e14/test_e14s.py", "design/e1.4/E14S_PROTOCOL_v1.md",
         "design/e1.4/E14R_LOCK_v1.json")
LENGTHS = (7, 8, 9)
POLICIES = (("receipt", 1), ("fixed", 2), ("active", 2), ("fixed", 3), ("active", 3))
TARGETS = tuple(word for length in range(5, 10) for word in product((1, 2), repeat=length))


def manifest():
    return {"version": 1, "sha256": {path: sha((REPO / path).read_bytes()) for path in FILES}}


def drive(first, truth, mode, budget, select):
    labels = [first]
    cost = Counter(labels=1)
    while True:
        action = select(mode, budget, labels)
        if action["action"] != "query":
            accepted = action["action"] == "accept"
            matched = accepted and tuple(action["word"]) == truth
            cost.update(correct=int(matched), wrong=int(accepted and not matched), abstain=int(not accepted))
            return cost
        graph = action["graph"]
        input_value("G", graph)
        verify(len(labels) < budget and graph["nodes"] <= 16 and len(graph["edges"]) <= 16,
               "invalid second query or exceeded label cap")
        labels.append(minimum(paths(graph), truth))
        cost.update(labels=1, followup_nodes=graph["nodes"], followup_edges=len(graph["edges"]))


def enumerate_length(length):
    scores = {f"{mode}-{cap}": Counter() for mode, cap in POLICIES}
    mapped_count = short_aliases = null_receipts = 0
    for word in product((1, 2), repeat=length):
        candidate_words = mappings(word)
        graph = decide(word, "active", 3, [])["graph"]
        input_value("G", graph)
        verify(graph["nodes"] <= 16 and len(graph["edges"]) <= 16, "first query over graph cap")
        routes = paths(graph)
        verify(dict(routes) == {w: length + 1 + 4 * i for i, w in enumerate(candidate_words)},
               "first query has incorrect costs")
        for truth in TARGETS:
            label = minimum(routes, truth)
            if label is None:
                null_receipts += 1
                continue
            if truth in candidate_words:
                mapped_count += 1
            else:
                short_aliases += 1
            for mode, cap in POLICIES:
                result = drive(label, truth, mode, cap, lambda m, b, ys: decide(word, m, b, ys))
                scores[f"{mode}-{cap}"].update(result)
    for counts in scores.values():
        counts.update(labels=null_receipts, abstain=null_receipts)
    total = (2 ** length) * len(TARGETS)
    for counts in scores.values():
        verify(sum(counts[k] for k in ("correct", "wrong", "abstain")) == total, "incomplete enumeration")
    active = scores["active-3"]
    passed = active["correct"] == mapped_count and active["wrong"] == 0 and scores["receipt-1"]["wrong"] > 0
    return {"status": "scored", "correct": int(passed), "total": 1, "source_length": length,
            "pairs": total, "mapped": mapped_count, "shorter_aliases": short_aliases,
            "null_receipts": null_receipts, "policies": {k: dict(sorted(v.items())) for k, v in scores.items()}}


def sandbox_examples():
    boundary = validate_boundary()
    checked = 0
    with stage() as root:
        shutil.copyfile(REPO / "code/e14/e14r_worker.py", root / "e14/e14r_worker.py")
        shutil.copyfile(REPO / WORKER, root / "e14/e14s_worker.py")
        raw, _ = _sandbox_python(["-c", "import importlib.util,sys; sys.path.insert(0,'/solver'); "
                                  "print(all(importlib.util.find_spec(m) is None for m in "
                                  "('e14.e14p_graph','e14.e14r_run','e14.e14s_run')))"], solver=root)
        verify(raw.strip() == b"True", "worker sees evaluator")
        boundary["checks"]["qualification_stage_without_evaluator"] = True
        for length in LENGTHS:
            word = tuple(1 + (i % 2) for i in range(length))
            artifact = {"kind": "edge-relative-word-v1", "word": word, "source_sha256": "0" * 64}
            for truth in (word, mappings(word)[1], word[:-1], tuple(3 - v for v in word)):
                labels = []
                while True:
                    packet = {"artifact": artifact, "mode": "active", "budget": 3, "labels": labels}
                    cmd = ("import sys; sys.path.insert(0,'/solver'); from e14.e14s_worker import main; "
                           f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
                    raw, wall = _sandbox_python(["-c", cmd], canonical_json(packet), solver=root)
                    observed = read_json(raw, 24_576)
                    integer(observed.pop("cpu_us"), 0, 1_000_000)
                    integer(observed.pop("rss_kib"), 1, 131_072)
                    integer(wall, 0, 3_000_000)
                    verify(observed == decide(word, "active", 3, labels), "sandbox result differs")
                    checked += 1
                    if observed["action"] != "query":
                        break
                    verify(len(labels) < 3, "sandbox query budget exceeded")
                    labels.append(minimum(paths(observed["graph"]), truth))
    return {**boundary, "worker_calls_checked": checked}


def run(ledger, output):
    prior_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4s freeze manifest mismatch")
    arms = tuple(Arm("G", "unrelated", "enumeration", str(length), 0, "qualification") for length in LENGTHS)
    plan = RunPlan(lock["sha256"][WORKER], sha(canonical_json(TARGETS)), lock["sha256"][SOURCE],
                   sha(canonical_json(lock)), 143501, 1, arms)
    boundary = sandbox_examples()
    rows = run_arms(ledger, plan, lambda arm: enumerate_length(int(arm.episode)))
    mapped = sum(row["mapped"] for row in rows)
    report = {"status": "completed", "plan_sha256": plan.sha256, "boundary": boundary, "rows": rows,
              "decision": "GO" if mapped == 2688 and all(row["correct"] == 1 for row in rows) else "HOLD"}
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_bytes(gzip.compress(canonical_json(report), mtime=0))
    os.replace(temporary, output)
    print(json.dumps({"status": "COMPLETE", "decision": report["decision"],
                      "cases": sum(row["pairs"] for row in rows), "mapped": mapped}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("freeze")
    runner = subparsers.add_parser("run")
    runner.add_argument("ledger", type=Path)
    runner.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "freeze":
        prior_frozen()
        (REPO / LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
