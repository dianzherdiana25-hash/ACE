"""Bounded end-to-end scoring with separately tracked discovery and recovery."""

import argparse
import gzip
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from e13.contract import canonical_json, input_value, integer, read_json, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, oracle, sha, trace
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14l_run import selective
from .e14n_run import deterministic, frozen as prior_frozen, stage as prior_stage, validate_classes
from .e14n_worker import EXPANSION_LENGTHS
from .e14o_bank import CONDITIONS, SEEDS, build
from .e14o_worker import CAP, LABEL_CAP, MODES

BANK = "evidence/e14/e14o_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14O_LOCK_v1.json"
WORKER = "code/e14/e14o_worker.py"
SOURCE = "code/e14/e14o_bank.py"
FILES = (BANK, WORKER, SOURCE, "design/e1.4/E14N_LOCK_v1.json", "design/e1.4/E14O_PROTOCOL_v1.md",
         "code/e14/e14o_run.py", "code/e14/e14o_audit.py", "code/e14/test_e14o.py", "tools/ace_sprint_runner.py")


def manifest():
    return {"version": 1, "sha256": {p: sha((REPO/p).read_bytes()) for p in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO/LOCK).read_bytes())
    verify(lock == manifest(), "E1.4o freeze manifest mismatch")
    raw = gzip.decompress((REPO/BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    arms = {}
    for b in bank["blocks"]:
        for w in b["worlds"]:
            l = len(w["word"])
            arm = Arm(b["family"], "related" if l == 5 else "unrelated",
                      f'{w["condition"]}:{b["slot"]}', str(l), 0, "autonomous-repair")
            verify(arm not in arms, "duplicate world")
            arms[arm] = b, tuple(w["word"])
    verify(len(arms) == 48, "unexpected world count")
    return arms


@contextmanager
def stage():
    with prior_stage() as root:
        shutil.copyfile(REPO/WORKER, root/"e14/e14o_worker.py")
        yield root


def invoke(root, packet):
    cmd = ("import sys; sys.path.insert(0,'/solver'); from e14.e14o_worker import main; "
           f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw, wall = _sandbox_python(["-c", cmd], canonical_json(packet), solver=root)
    row = read_json(raw, 24_576)
    require_fields(row, "classes", "trigger", "offers", "choice", "offer_attempts", "expansion_fits",
                   "anchor_checks", "model_checks", "base_comparisons", "cpu_us", "rss_kib")
    meter = {"cpu_us": integer(row.pop("cpu_us"), 0, 1_000_000), "rss_kib": integer(row.pop("rss_kib"), 1, 131_072),
             "wall_us": integer(wall, 0, 3_000_000)}
    return row, meter


def evaluate(root, block, target):
    family, probes = block["family"], block["probes"]
    gold = [oracle(family, target, x) for x in probes]
    demos = [{"input": x, "output": oracle(family, target, x)} for x in block["demos"]]
    branches, resources = {}, {}
    for mode in MODES:
        known = demos.copy()
        seen = {trace(family, x["input"]) for x in known}
        steps, meters = [], []
        for round_index in range(LABEL_CAP+1):
            row, meter = invoke(root, {"family": family, "demos": known, "mode": mode,
                                      "seed": (block["seed"]+round_index) % 2**32})
            classes, triggered, offers = row.pop("classes"), row["trigger"], row["offers"]
            verify(type(triggered) is bool and len(offers) <= CAP, "invalid worker outcome")
            validate_classes(family, classes, EXPANSION_LENGTHS if triggered else LENGTHS)
            answer = None
            if row["choice"] is not None:
                verify(round_index < LABEL_CAP, "label cap exceeded")
                raw = offers[integer(row["choice"], 0, len(offers)-1)]["input"]
                input_value(family, raw)
                events = trace(family, raw)
                verify(events not in seen and len(events) in (EXPANSION_LENGTHS if triggered else (9,)),
                       "invalid or duplicate query")
                seen.add(events)
                answer = {"input": raw, "output": oracle(family, target, raw)}
            steps.append({**row, **selective(family, classes, probes, gold),
                          "class_sha256": sha(canonical_json(classes)), "survivors": sum(map(len, classes)),
                          "revealed": answer})
            meters.append(meter)
            if answer is None:
                break
            known.append(answer)
        branches[mode], resources[mode] = steps, meters
    end = branches["active"][-1]
    return {"status": "scored", "total": 8, "correct": end["selective_covered"]-end["selective_errors"],
            "branches": branches, "resources": resources,
            "oracle_calls": 40+sum(len(x)-1 for x in branches.values())}


def totals(rows, mode):
    out = dict.fromkeys(("detected", "full", "covered", "errors", "labels", "events", "repair_labels",
                         "expansion_fits", "model_checks"), 0)
    for row in rows:
        steps = row["branches"][mode]
        end = steps[-1]
        out["detected"] += end["trigger"]
        out["full"] += end["selective_covered"] == 8 and end["selective_errors"] == 0
        out["covered"] += end["selective_covered"]
        out["errors"] += end["selective_errors"]
        out["labels"] += len(steps)-1
        for s in steps:
            out["expansion_fits"] += s["expansion_fits"]
            out["model_checks"] += s["model_checks"]
            if s["revealed"] is not None:
                out["events"] += len(trace(row["family"], s["revealed"]["input"]))
                out["repair_labels"] += s["trigger"]
    return out


def summary(rows):
    cells = []
    for f in FAMILIES:
        for c in CONDITIONS:
            group = [r for r in rows if r["family"] == f and r["block"].startswith(c+":")]
            cells.append({"family": f, "condition": c, "worlds": len(group),
                          "arms": {m: totals(group, m) for m in MODES}})
    reachable = [c["arms"] for c in cells if c["condition"] == "reachable"]
    false_triggers = sum(c["arms"][m]["detected"] for c in cells if c["condition"] in ("natural", "matched") for m in MODES)
    enough = all(c["active"]["full"] >= 5 for c in reachable)
    better = all(sum(c["active"]["full"] for c in reachable) > sum(c[m]["full"] for c in reachable)
                 for m in ("passive", "random"))
    return {"autonomous_repair": "GO" if enough and better and not false_triggers else "HOLD",
            "false_triggers": false_triggers, "rare_decision": "RARE_HOLD", "natural_decision": "NATURAL_HOLD",
            "worlds": len(rows), "cells": cells, "oracle_calls": sum(r["oracle_calls"] for r in rows),
            "worker_calls": sum(len(arm) for r in rows for arm in r["resources"].values())}


def run(ledger, output):
    bank, digest, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], digest, lock["sha256"][SOURCE], sha(canonical_json(lock)),
                   SEEDS[4], 8, tuple(arms))
    with stage() as root:
        raw, _ = _sandbox_python(["-c", "import importlib.util,sys; sys.path.insert(0,'/solver'); "
                                 "print(all(importlib.util.find_spec(x) is None for x in "
                                 "('e14.e14o_bank','e14.e14o_run','e14.e14g_bank')))"], solver=root)
        verify(raw.strip() == b"True", "worker mount exposes evaluator")
        boundary["checks"]["autonomous_stage_without_evaluator"] = True
        rows = run_arms(ledger, plan, lambda arm: evaluate(root, *arms[arm]))
    report = {"status": "completed", "version": 1, "bank_sha256": digest, "plan_sha256": plan.sha256,
              "boundary": boundary, "rows": rows, "summary": summary(rows)}
    temp = output.with_name(output.name+".tmp")
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
        (REPO/BANK).write_bytes(gzip.compress(canonical_json(build()), mtime=0))
        (REPO/LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True)+"\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
