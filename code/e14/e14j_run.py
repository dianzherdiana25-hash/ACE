"""Run bounded public E1.4j query synthesis and preserve per-arm evidence."""

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
from .e14g_bank import FAMILIES, LENGTHS, alphabet, oracle, sha, trace
from .e14g_isolation import validate_boundary, worker_mount
from .e14g_run import REPO
from .e14i_run import frozen as prior_frozen
from .e14j_bank import SEEDS, build
from .e14j_worker import CAP, MODES

BANK = "evidence/e14/e14j_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14J_LOCK_v1.json"
PROTOCOL = "design/e1.4/E14J_PROTOCOL_v1.md"
WORKER = "code/e14/e14j_worker.py"
FILES = (BANK, PROTOCOL, "design/e1.4/E14I_LOCK_v1.json", WORKER, "code/e14/e14j_bank.py",
         "code/e14/e14j_run.py", "code/e14/e14j_audit.py", "code/e14/test_e14j.py")


def manifest():
    return {"version": 1, "sha256": {name: sha((REPO / name).read_bytes()) for name in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4j freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    result = {}
    for block in bank["blocks"]:
        for word in block["words"]:
            length = len(word)
            arm = Arm(block["family"], "related" if length == 5 else "unrelated",
                      f'{block["condition"]}:{block["slot"]}', str(length), 0, "synthesis")
            verify(arm not in result, "duplicate E1.4j arm")
            result[arm] = (block, word)
    verify(len(result) == 72, "incorrect world count")
    return result


@contextmanager
def stage():
    with worker_mount() as root:
        shutil.copyfile(REPO / WORKER, root / "e14/e14j_worker.py")
        yield root


def invoke(root, packet):
    script = ("import sys; sys.path.insert(0, '/solver'); from e14.e14j_worker import main; "
              f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw, wall = _sandbox_python(["-c", script], canonical_json(packet), solver=root)
    output = read_json(raw, 16_384)
    require_fields(output, "cpu_us", "rss_kib", "diagnosis", "word", "compatible", "offers", "choice",
                   "demo_comparisons", "candidate_checks", "proposal_attempts")
    resources = {"cpu_us": integer(output.pop("cpu_us"), 0, 1_000_000),
                 "rss_kib": integer(output.pop("rss_kib"), 1, 131_072),
                 "wall_us": integer(wall, 0, 3_000_000)}
    return output, resources


def score_prediction(family, word, probes, gold):
    pred = [oracle(family, tuple(word), raw) for raw in probes]
    exact = sum(p == y for p, y in zip(pred, gold, strict=True))
    fp = (sum(p is not None and y is None for p, y in zip(pred, gold, strict=True)) if family == "G" else
          sum(any(a > b for a, b in zip(p, y, strict=True)) for p, y in zip(pred, gold, strict=True)))
    return {"exact": exact, "false_positive": fp}


def evaluate(root, block, word):
    family = block["family"]
    true_word = tuple(word)

    def label(raw):
        return {"input": raw, "output": oracle(family, true_word, raw)}

    demos = [label(raw) for raw in block["demos"]]
    gold = [oracle(family, true_word, raw) for raw in block["probes"]]
    branches = {}
    resources = {}
    for mode in MODES:
        steps, metrics = [], []
        known = demos.copy()
        seen = {trace(family, row["input"]) for row in demos}
        for step in range(3):
            packet = {"family": family, "demos": known, "mode": mode,
                      "seed": (block["seed"] + step) % 2**32, "pool": block["pool"] if mode == "fixed" else []}
            worker, usage = invoke(root, packet)
            diagnosis = worker["diagnosis"]
            pred_word = worker["word"]
            verify((diagnosis is None or type(diagnosis) is int and diagnosis in LENGTHS)
                   and len(pred_word) == (diagnosis or 5)
                   and all(type(v) is int and v in alphabet(family) for v in pred_word), "invalid prediction")
            offers = worker["offers"]
            verify(len(offers) <= CAP and all(len(trace(family, q["input"])) in LENGTHS for q in offers),
                   "invalid offer")
            selected = worker["choice"]
            revealed = None
            if selected is not None:
                integer(selected, 0, len(offers)-1)
                verify(step < 2 and diagnosis is None, "inadmissible acquisition")
                raw = offers[selected]["input"]
                events = trace(family, raw)
                verify(events not in seen, "query repeats an already labeled trace")
                seen.add(events)
                revealed = label(raw)
            steps.append({**worker, **score_prediction(family, pred_word, block["probes"], gold),
                          "revealed": revealed})
            metrics.append(usage)
            if revealed is None:
                break
            known.append(revealed)
        branches[mode] = steps
        resources[mode] = metrics
    return {"status": "scored", "correct": branches["guided"][-1]["exact"], "total": 8,
            "branches": branches, "resources": resources,
            "oracle_calls": len(demos) + len(gold) + sum(len(steps)-1 for steps in branches.values())}


def summary(rows):
    cells = []
    gates = []
    for family in FAMILIES:
        for condition in ("natural", "single", "sequence", "beyond"):
            group = [r for r in rows if r["family"] == family and r["block"].startswith(condition+":")]
            arms = {}
            for mode in MODES:
                arms[mode] = {}
                for budget in range(3):
                    records = [(r, r["branches"][mode][min(budget, len(r["branches"][mode])-1)])
                               for r in group]
                    arms[mode][str(budget)] = {
                        "diagnosed": sum(x["diagnosis"] == int(r["episode"]) for r, x in records),
                        "wrong": sum(x["diagnosis"] not in (None, int(r["episode"])) for r, x in records),
                        "abstained": sum(x["diagnosis"] is None for _, x in records),
                        "exact": sum(x["exact"] for _, x in records),
                        "false_positive": sum(x["false_positive"] for _, x in records),
                        "labels": sum(min(budget, len(r["branches"][mode])-1) for r, _ in records),
                        "candidate_inputs": sum(len(x["offers"]) for r, _ in records for x in r["branches"][mode][:budget]),
                        "candidate_checks": sum(x["candidate_checks"] for r, _ in records for x in r["branches"][mode][:budget]),
                        "proposal_attempts": sum(x["proposal_attempts"] for r, _ in records for x in r["branches"][mode][:budget]),
                    }
            long = [r for r in group if r["episode"] == "6"]
            paired_single = sum(all(r["branches"]["guided"][min(1, len(r["branches"]["guided"])-1)]["diagnosis"]
                                     == int(r["episode"]) for r in group if r["block"] == b)
                                for b in {r["block"] for r in group})
            new_long = sum(len(r["branches"]["guided"]) == 3 and r["branches"]["guided"][1]["diagnosis"] is None
                           and r["branches"]["guided"][2]["diagnosis"] == 6 for r in long)
            long_abstain = sum(r["branches"]["guided"][-1]["diagnosis"] is None for r in long)
            cells.append({"family": family, "condition": condition, "worlds": len(group), "arms": arms,
                          "paired_guided_at_one": paired_single, "long_resolved_only_at_two": new_long,
                          "long_abstained_at_two": long_abstain})
            if condition == "single":
                gates.append(paired_single >= 3 and arms["guided"]["1"]["diagnosed"] >
                             max(arms[c]["1"]["diagnosed"] for c in ("random", "fixed")))
            if condition == "sequence":
                gates.append(new_long >= 3 and arms["guided"]["2"]["diagnosed"] >
                             max(arms[c]["2"]["diagnosed"] for c in ("random", "fixed")))
            if condition == "beyond":
                gates.append(long_abstain >= 3)
    no_wrong = all(c["arms"]["guided"]["2"]["wrong"] == 0 for c in cells)
    return {"decision": "SYNTHESIS_DEVELOPMENT_GO" if all(gates) and no_wrong else "SYNTHESIS_HOLD",
            "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD", "cells": cells,
            "oracle_calls": sum(r["oracle_calls"] for r in rows),
            "worker_calls": sum(len(m) for r in rows for m in r["resources"].values()),
            "fit_comparisons": sum(x["demo_comparisons"] for r in rows for steps in r["branches"].values() for x in steps),
            "worlds": len(rows)}


def deterministic(report):
    return {**report, "rows": [{k: v for k, v in r.items() if k != "resources"} for r in report["rows"]]}


def run(ledger, output):
    bank, digest, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], digest, lock["sha256"]["code/e14/e14j_bank.py"],
                   sha(canonical_json(lock)), SEEDS[4], 8, tuple(arms))
    with stage() as root:
        check = ("import importlib.util, sys; sys.path.insert(0, '/solver'); "
                 "print(all(importlib.util.find_spec(m) is None "
                 "for m in ('e14.e14j_bank','e14.e14j_run','e14.e14g_bank')))")
        out, _ = _sandbox_python(["-c", check], solver=root)
        verify(out.strip() == b"True", "worker mount exposes evaluator")
        boundary["checks"]["synthesis_stage_without_evaluator"] = True
        rows = run_arms(ledger, plan, lambda arm: evaluate(root, *arms[arm]))
    report = {"version": 1, "status": "completed", "bank_sha256": digest, "plan_sha256": plan.sha256,
              "boundary": boundary, "rows": rows, "summary": summary(rows)}
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
