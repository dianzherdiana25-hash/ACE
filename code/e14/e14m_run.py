"""Run the frozen public counterexample bank under isolated workers."""

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
from .e14g_bank import FAMILIES, LENGTHS, alphabet, oracle, sha, trace
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14l_run import frozen as prior_frozen, selective, stage as prior_stage
from .e14m_bank import CONDITIONS, SEEDS, build
from .e14m_worker import CAP, LABEL_CAP, MODES, QUERY_LENGTH

BANK = "evidence/e14/e14m_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14M_LOCK_v1.json"
WORKER = "code/e14/e14m_worker.py"
BANK_SOURCE = "code/e14/e14m_bank.py"
FILES = (BANK, WORKER, BANK_SOURCE, "design/e1.4/E14L_LOCK_v1.json", "design/e1.4/E14M_PROTOCOL_v1.md",
         "code/e14/e14m_run.py", "code/e14/e14m_audit.py", "code/e14/test_e14m.py")


def manifest():
    return {"version": 1, "sha256": {p: sha((REPO / p).read_bytes()) for p in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4m freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    arms = {}
    for b in bank["blocks"]:
        for world in b["worlds"]:
            length = len(world["word"])
            arm = Arm(b["family"], "related" if length == 5 else "unrelated",
                      f'{world["condition"]}:{b["slot"]}', str(length), 0, "adequacy")
            verify(arm not in arms, "duplicate world")
            arms[arm] = (b, world["word"])
    verify(len(arms) == 72, "wrong world count")
    return arms


@contextmanager
def stage():
    with prior_stage() as root:
        shutil.copyfile(REPO / WORKER, root / "e14/e14m_worker.py")
        yield root


def invoke(root, packet):
    command = ("import sys; sys.path.insert(0,'/solver'); from e14.e14m_worker import main; "
               f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw, wall = _sandbox_python(["-c", command], canonical_json(packet), solver=root)
    out = read_json(raw, 24_576)
    require_fields(out, "cpu_us", "rss_kib", "exact_classes", "offers", "choice", "proposal_attempts",
                   "demo_comparisons", "candidate_checks")
    meter = {"cpu_us": integer(out.pop("cpu_us"), 0, 1_000_000),
             "rss_kib": integer(out.pop("rss_kib"), 1, 131_072),
             "wall_us": integer(wall, 0, 3_000_000)}
    return out, meter


def evaluate(root, block, word):
    family, target = block["family"], tuple(word)
    probes = block["probes"]
    gold = [oracle(family, target, raw) for raw in probes]
    demos = [{"input": x, "output": oracle(family, target, x)} for x in block["demos"]]
    seen_demo = {trace(family, row["input"]) for row in demos}
    branches, resources = {}, {}
    for mode in MODES:
        known, seen = demos.copy(), seen_demo.copy()
        steps, meters = [], []
        for t in range(LABEL_CAP+1):
            row, meter = invoke(root, {"family": family, "mode": mode, "demos": known,
                                      "seed": (block["seed"]+t) % 2**32})
            exact = row.pop("exact_classes")
            verify(len(exact) == 2 and all(len(words) <= len(alphabet(family))**l and all(
                len(w) == l and all(type(v) is int and v in alphabet(family) for v in w) for w in words
            ) for l, words in zip(LENGTHS, exact, strict=True)), "invalid typed version space")
            offers = row["offers"]
            verify(len(offers) <= CAP, "candidate cap exceeded")
            for offered in offers:
                q = offered["input"]
                input_value(family, q)
                verify(len(trace(family, q)) == QUERY_LENGTH, "wrong query length")
            answer = None
            if row["choice"] is not None:
                verify(any(exact) and t < LABEL_CAP, "inadmissible label purchase")
                raw = offers[integer(row["choice"], 0, len(offers)-1)]["input"]
                events = trace(family, raw)
                verify(events not in seen, "repeated labeled query")
                seen.add(events)
                answer = {"input": raw, "output": oracle(family, target, raw)}
            steps.append({**row, "class_sha256": sha(canonical_json(exact)), "compatible": list(map(len, exact)),
                          "rejected": not any(exact), **selective(family, exact, probes, gold), "revealed": answer})
            meters.append(meter)
            if answer is None:
                break
            known.append(answer)
        branches[mode], resources[mode] = steps, meters
    end = branches["falsify"][-1]
    return {"status": "scored", "total": 8, "correct": end["selective_covered"]-end["selective_errors"],
            "branches": branches, "resources": resources,
            "oracle_calls": 40+sum(len(steps)-1 for steps in branches.values())}


def totals(rows, mode, cap):
    keys = ("rejected", "selective_covered", "selective_errors", "selective_false_positive",
            "labels", "bought_events", "offers", "proposal_attempts", "candidate_checks", "oracle_activations")
    out = dict.fromkeys(keys, 0)
    for row in rows:
        steps = row["branches"][mode]
        purchases = min(cap, len(steps)-1)
        end = steps[purchases]
        for field in keys[:4]:
            out[field] += end[field]
        out["labels"] += purchases
        for step in steps[:purchases]:
            answer = step["revealed"]
            out["bought_events"] += len(trace(row["family"], answer["input"]))
            y = answer["output"]
            out["oracle_activations"] += any(y) if row["family"] == "S" else y is not None
        for step in steps[:cap]:
            out["offers"] += len(step["offers"])
            out["proposal_attempts"] += step["proposal_attempts"]
            out["candidate_checks"] += step["candidate_checks"]
    return out


def summary(rows):
    cells, reachable, rare = [], [], []
    for family in FAMILIES:
        for condition in CONDITIONS:
            group = [r for r in rows if r["family"] == family and r["block"].startswith(condition+":")]
            arms = {m: {str(n): totals(group, m, n) for n in (0, 1, 2, 4)} for m in MODES}
            cells.append({"family": family, "condition": condition, "worlds": len(group), "arms": arms})
            if condition in ("reachable", "rare"):
                hits = arms["falsify"]["4"]["rejected"]
                better = hits > max(arms[m]["4"]["rejected"] for m in ("adjudicate", "random"))
                (reachable if condition == "reachable" else rare).append(better and hits >= (5 if condition == "reachable" else 4))
    false_rejects = sum(c["arms"][m]["4"]["rejected"] for c in cells
                        if c["condition"] in ("natural", "matched") for m in MODES)
    return {"reachable": "GO" if all(reachable) and not false_rejects else "HOLD",
            "rare": "GO" if all(rare) and not false_rejects else "HOLD", "false_rejects": false_rejects,
            "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD", "worlds": len(rows), "cells": cells,
            "oracle_calls": sum(r["oracle_calls"] for r in rows),
            "worker_calls": sum(len(x) for r in rows for x in r["resources"].values()),
            "fit_comparisons": sum(s["demo_comparisons"] for r in rows for steps in r["branches"].values() for s in steps)}


def run(ledger, output):
    bank, digest, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], digest, lock["sha256"][BANK_SOURCE],
                   sha(canonical_json(lock)), SEEDS[4], 8, tuple(arms))
    with stage() as root:
        check = ("import importlib.util,sys; sys.path.insert(0,'/solver'); "
                 "print(all(importlib.util.find_spec(m) is None "
                 "for m in ('e14.e14g_bank','e14.e14m_bank','e14.e14m_run')))")
        raw, _ = _sandbox_python(["-c", check], solver=root)
        verify(raw.strip() == b"True", "worker mount exposes evaluator")
        boundary["checks"]["counterexample_stage_without_evaluator"] = True
        rows = run_arms(ledger, plan, lambda arm: evaluate(root, *arms[arm]))
    report = {"version": 1, "status": "completed", "bank_sha256": digest, "plan_sha256": plan.sha256,
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
        (REPO / BANK).write_bytes(gzip.compress(canonical_json(build()), mtime=0))
        (REPO / LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
