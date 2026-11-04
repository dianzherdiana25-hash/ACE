"""Score frozen compound questions through an isolated, resumable evaluator."""

import argparse
import gzip
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, input_value, integer, read_json, require_fields
from e13.evaluator.run_ledger import RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, alphabet, oracle, sha, trace
from .e14g_isolation import validate_boundary, worker_mount
from .e14g_run import REPO
from .e14j_run import frozen as prior_frozen, schedule, score_prediction
from .e14k_bank import CONDITIONS, SEEDS, build
from .e14k_worker import CAP, LONG, MODES

BANK = "evidence/e14/e14k_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14K_LOCK_v1.json"
WORKER = "code/e14/e14k_worker.py"
FILES = (BANK, WORKER, "design/e1.4/E14J_LOCK_v1.json", "design/e1.4/E14K_PROTOCOL_v1.md",
         "code/e14/e14k_bank.py", "code/e14/e14k_run.py", "code/e14/e14k_audit.py", "code/e14/test_e14k.py")


def manifest():
    return {"version": 1, "sha256": {path: sha((REPO / path).read_bytes()) for path in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4k freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


@contextmanager
def stage():
    with worker_mount() as root:
        for name in ("e14j_worker.py", "e14k_worker.py"):
            shutil.copyfile(REPO / "code/e14" / name, root / "e14" / name)
        yield root


def invoke(root, packet):
    command = ("import sys; sys.path.insert(0, '/solver'); "
               "from e14.e14k_worker import main; "
               f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw, wall = _sandbox_python(["-c", command], canonical_json(packet), solver=root)
    out = read_json(raw, 16_384)
    require_fields(out, "cpu_us", "rss_kib", "diagnosis", "word", "compatible", "offers", "choice",
                   "proposal_attempts", "demo_comparisons", "candidate_checks")
    resources = {"cpu_us": integer(out.pop("cpu_us"), 0, 1_000_000),
                 "rss_kib": integer(out.pop("rss_kib"), 1, 131_072),
                 "wall_us": integer(wall, 0, 3_000_000)}
    return out, resources


def evaluate(root, block, word):
    family = block["family"]
    target = tuple(word)
    probes = block["probes"]
    gold = [oracle(family, target, x) for x in probes]
    demos = [{"input": x, "output": oracle(family, target, x)} for x in block["demos"]]
    branches, resources = {}, {}
    for mode in MODES:
        known = demos.copy()
        seen = {trace(family, x["input"]) for x in demos}
        steps, metrics = [], []
        lengths = LENGTHS if mode == "short" else (LONG,)
        for step in range(3):
            row, usage = invoke(root, {"family": family, "mode": mode, "demos": known,
                                      "seed": (block["seed"] + step) % 2**32})
            diagnosis, word, offers = (row[key] for key in ("diagnosis", "word", "offers"))
            verify((diagnosis is None or type(diagnosis) is int and diagnosis in LENGTHS)
                   and len(word) == (diagnosis or 5)
                   and all(type(x) is int and x in alphabet(family) for x in word)
                   and len(offers) <= CAP, "inadmissible worker response")
            for offered in offers:
                raw = offered["input"]
                input_value(family, raw)
                verify(len(trace(family, raw)) in lengths, "query length outside frozen budget")
            revealed = None
            if row["choice"] is not None:
                verify(step < 2 and diagnosis is None, "inadmissible label acquisition")
                raw = offers[integer(row["choice"], 0, len(offers)-1)]["input"]
                events = trace(family, raw)
                verify(events not in seen, "worker repeated a labeled trace")
                seen.add(events)
                revealed = {"input": raw, "output": oracle(family, target, raw)}
            steps.append({**row, **score_prediction(family, word, probes, gold), "revealed": revealed})
            metrics.append(usage)
            if revealed is None:
                break
            known.append(revealed)
        branches[mode], resources[mode] = steps, metrics
    return {"status": "scored", "total": 8, "correct": branches["compound"][-1]["exact"],
            "branches": branches, "resources": resources,
            "oracle_calls": 40 + sum(len(x)-1 for x in branches.values())}


def budget_totals(rows, family, mode, cap):
    counts = dict.fromkeys(("diagnosed", "long_diagnosed", "wrong", "abstained", "exact", "false_positive",
                            "fallback_false_positive", "fallback_probes", "labels", "bought_events", "offers",
                            "offered_events", "proposal_attempts", "candidate_checks", "short_eliminated",
                            "long_eliminated", "short_covered", "long_covered", "long_world_short_eliminated"), 0)
    for row in rows:
        steps = row["branches"][mode]
        purchased = min(cap, len(steps)-1)
        terminal = steps[purchased]
        actual = int(row["episode"])
        diagnosis = terminal["diagnosis"]
        counts["diagnosed"] += diagnosis == actual
        counts["long_diagnosed"] += diagnosis == actual == 6
        counts["wrong"] += diagnosis not in (None, actual)
        counts["abstained"] += diagnosis is None
        counts["exact"] += terminal["exact"]
        counts["false_positive"] += terminal["false_positive"]
        if diagnosis is None:
            counts["fallback_false_positive"] += terminal["false_positive"]
            counts["fallback_probes"] += 8
        counts["labels"] += purchased
        counts["bought_events"] += sum(len(trace(family, step["revealed"]["input"])) for step in steps[:purchased])
        # At cap one, the second-round search is not part of deployed cost.
        for step in steps[:cap]:
            counts["offers"] += len(step["offers"])
            counts["offered_events"] += sum(len(trace(family, x["input"])) for x in step["offers"])
            counts["proposal_attempts"] += step["proposal_attempts"]
            counts["candidate_checks"] += step["candidate_checks"]
        start_short, start_long = steps[0]["compatible"]
        end_short, end_long = terminal["compatible"]
        counts["short_eliminated"] += start_short - end_short
        counts["long_eliminated"] += start_long - end_long
        if actual == 6:
            counts["long_world_short_eliminated"] += start_short - end_short
        for step in steps[:purchased]:
            short_covered, long_covered = step["offers"][step["choice"]]["covered"]
            counts["short_covered"] += short_covered
            counts["long_covered"] += long_covered
    return counts


def summary(rows):
    cells, gates = [], []
    for family in FAMILIES:
        for condition in CONDITIONS:
            group = [r for r in rows if r["family"] == family and r["block"].startswith(condition + ":")]
            arms = {mode: {str(cap): budget_totals(group, family, mode, cap) for cap in range(3)}
                    for mode in MODES}
            cells.append({"family": family, "condition": condition, "worlds": len(group), "arms": arms})
            if condition == "packable":
                primary = arms["compound"]["1"]
                gates.append(primary["long_diagnosed"] >= 4 and all(
                    primary[k] > max(arms[mode]["1"][k] for mode in ("short", "random"))
                    for k in ("long_diagnosed", "long_world_short_eliminated")))
    no_wrong = all(c["arms"]["compound"]["2"]["wrong"] == 0 for c in cells)
    return {"decision": "COMPOUND_DEVELOPMENT_GO" if all(gates) and no_wrong else "COMPOUND_HOLD",
            "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD", "worlds": len(rows), "cells": cells,
            "oracle_calls": sum(r["oracle_calls"] for r in rows),
            "worker_calls": sum(len(m) for r in rows for m in r["resources"].values()),
            "fit_comparisons": sum(s["demo_comparisons"] for r in rows for p in r["branches"].values() for s in p)}


def deterministic(report):
    return {**report, "rows": [{k: v for k, v in row.items() if k != "resources"} for row in report["rows"]]}


def run(ledger, output):
    bank, bank_sha, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], bank_sha, lock["sha256"]["code/e14/e14k_bank.py"],
                   sha(canonical_json(lock)), SEEDS[4], 8, tuple(arms))
    with stage() as root:
        check = ("import importlib.util,sys; sys.path.insert(0,'/solver'); "
                 "print(all(importlib.util.find_spec(m) is None "
                 "for m in ('e14.e14g_bank','e14.e14k_bank','e14.e14k_run')))")
        result, _ = _sandbox_python(["-c", check], solver=root)
        verify(result.strip() == b"True", "worker mount exposes evaluator")
        boundary["checks"]["compound_stage_without_evaluator"] = True
        rows = run_arms(ledger, plan, lambda arm: evaluate(root, *arms[arm]))
    report = {"version": 1, "status": "completed", "bank_sha256": bank_sha, "plan_sha256": plan.sha256,
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
