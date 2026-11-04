"""Bounded evaluation of shared-pool ranking, query costs, and selective risk."""

import argparse
import gzip
import json
import os
import shutil
from contextlib import contextmanager
from itertools import chain
from pathlib import Path

from e13.contract import canonical_json, input_value, integer, read_json, require_fields
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms
from e13.isolation import READY_MARKER, _sandbox_python

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, alphabet, oracle, sha, trace
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14j_run import score_prediction
from .e14k_run import frozen as prior_frozen, stage as prior_stage
from .e14l_bank import CONDITIONS, SEEDS, build
from .e14l_worker import CAP, MODES

BANK = "evidence/e14/e14l_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14L_LOCK_v1.json"
WORKER = "code/e14/e14l_worker.py"
BANK_SOURCE = "code/e14/e14l_bank.py"
FILES = (BANK, WORKER, BANK_SOURCE, "design/e1.4/E14K_LOCK_v1.json", "design/e1.4/E14L_PROTOCOL_v1.md",
         "code/e14/e14l_run.py", "code/e14/e14l_audit.py", "code/e14/test_e14l.py")


def manifest():
    return {"version": 1, "sha256": {p: sha((REPO / p).read_bytes()) for p in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4l freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    arms = {}
    for block in bank["blocks"]:
        for word in block["words"]:
            length = len(word)
            arm = Arm(block["family"], "related" if length == 5 else "unrelated",
                      f'{block["condition"]}:{block["slot"]}', str(length), 0, "ranking")
            verify(arm not in arms, "duplicate ranking arm")
            arms[arm] = (block, word)
    verify(len(arms) == 72, "incorrect world count")
    return arms


@contextmanager
def stage():
    with prior_stage() as root:
        shutil.copyfile(REPO / WORKER, root / "e14/e14l_worker.py")
        yield root


def invoke(root, packet):
    command = ("import sys; sys.path.insert(0,'/solver'); from e14.e14l_worker import main; "
               f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw, wall = _sandbox_python(["-c", command], canonical_json(packet), solver=root)
    out = read_json(raw, 24_576)
    require_fields(out, "cpu_us", "rss_kib", "diagnosis", "word", "exact_classes", "offers", "choice",
                   "proposal_attempts", "demo_comparisons", "candidate_checks")
    meter = {"cpu_us": integer(out.pop("cpu_us"), 0, 1_000_000), "rss_kib": integer(out.pop("rss_kib"), 1, 131_072),
             "wall_us": integer(wall, 0, 3_000_000)}
    return out, meter


def selective(family, exact, probes, gold):
    candidates = tuple(tuple(word) for word in chain.from_iterable(exact))
    covered = errors = fp = 0
    if candidates:
        for raw, true in zip(probes, gold, strict=True):
            first = oracle(family, candidates[0], raw)
            if any(oracle(family, word, raw) != first for word in candidates[1:]):
                continue
            covered += 1
            errors += first != true
            fp += (first is not None and true is None if family == "G" else
                   any(p > y for p, y in zip(first, true, strict=True)))
    return {"selective_covered": covered, "selective_errors": errors, "selective_false_positive": fp}


def evaluate(root, block, word):
    family, target = block["family"], tuple(word)
    probes = block["probes"]
    gold = [oracle(family, target, x) for x in probes]
    demos = [{"input": x, "output": oracle(family, target, x)} for x in block["demos"]]
    seen_demo = {trace(family, d["input"]) for d in demos}
    branches, resources = {}, {}
    for mode in MODES:
        known, seen = demos.copy(), seen_demo.copy()
        steps, meters = [], []
        for step in range(3):
            packet = {"family": family, "mode": mode, "demos": known, "seed": (block["seed"]+step) % 2**32}
            row, meter = invoke(root, packet)
            exact = row.pop("exact_classes")
            verify(len(exact) == 2 and all(len(words) <= len(alphabet(family))**l and all(
                len(w) == l and all(type(i) is int and i in alphabet(family) for i in w) for w in words
            ) for l, words in zip(LENGTHS, exact, strict=True)), "invalid typed version space")
            d, pred, offers = (row[k] for k in ("diagnosis", "word", "offers"))
            verify((d is None or type(d) is int and d in LENGTHS) and len(pred) == (d or 5)
                   and all(type(i) is int and i in alphabet(family) for i in pred) and len(offers) <= CAP,
                   "invalid worker response")
            for offer in offers:
                raw = offer["input"]
                input_value(family, raw)
                verify(len(trace(family, raw)) in (5, 6, 12), "invalid query length")
            answer = None
            if row["choice"] is not None:
                verify(step < 2 and d is None, "invalid query round")
                chosen = offers[integer(row["choice"], 0, len(offers)-1)]["input"]
                events = trace(family, chosen)
                verify(events not in seen, "duplicate labeled query")
                seen.add(events)
                answer = {"input": chosen, "output": oracle(family, target, chosen)}
            steps.append({**row, "class_sha256": sha(canonical_json(exact)), "compatible": list(map(len, exact)),
                          **score_prediction(family, pred, probes, gold), **selective(family, exact, probes, gold),
                          "revealed": answer})
            meters.append(meter)
            if answer is None:
                break
            known.append(answer)
        branches[mode], resources[mode] = steps, meters
    return {"status": "scored", "total": 8, "correct": branches["gate"][-1]["exact"],
            "branches": branches, "resources": resources,
            "oracle_calls": 40 + sum(len(x)-1 for x in branches.values())}


def totals(rows, mode, budget):
    fields = ("exact", "false_positive", "selective_covered", "selective_errors", "selective_false_positive")
    other = ("diagnosed", "long_diagnosed", "wrong", "abstained", "labels", "bought_events", "offers",
             "offered_events", "fallback_false_positive", "fallback_probes", "candidate_checks", "proposal_attempts")
    out = dict.fromkeys((*fields, *other), 0)
    for row in rows:
        steps = row["branches"][mode]
        used = min(budget, len(steps)-1)
        end = steps[used]
        truth = int(row["episode"])
        d = end["diagnosis"]
        for field in fields:
            out[field] += end[field]
        out["diagnosed"] += d == truth
        out["long_diagnosed"] += d == truth == 6
        out["wrong"] += d not in (None, truth)
        out["abstained"] += d is None
        if d is None:
            out["fallback_false_positive"] += end["false_positive"]
            out["fallback_probes"] += 8
        out["labels"] += used
        out["bought_events"] += sum(len(trace(row["family"], s["revealed"]["input"])) for s in steps[:used])
        for s in steps[:budget]:
            out["offers"] += len(s["offers"])
            out["offered_events"] += sum(len(trace(row["family"], q["input"])) for q in s["offers"])
            out["candidate_checks"] += s["candidate_checks"]
            out["proposal_attempts"] += s["proposal_attempts"]
    return out


def summary(rows):
    cells, rank, cost, risk = [], [], [], []
    for family in FAMILIES:
        group = [r for r in rows if r["family"] == family]
        for condition in CONDITIONS:
            data = [r for r in group if r["block"].startswith(condition + ":")]
            arms = {mode: {str(n): totals(data, mode, n) for n in range(3)} for mode in MODES}
            cells.append({"family": family, "condition": condition, "worlds": len(data), "arms": arms})
            if condition == "packable":
                rank.append(arms["value"]["1"]["long_diagnosed"] - arms["minimax"]["1"]["long_diagnosed"])
        in_model = [r for r in group if not r["block"].startswith("outside:")]
        base, gate = (totals(in_model, mode, 2) for mode in ("minimax", "gate"))
        cost.append(5*gate["bought_events"] <= 4*base["bought_events"]
                    and 10*gate["diagnosed"] >= 9*base["diagnosed"])
        risk.append(gate["selective_errors"] == 0 and 2*gate["selective_covered"] >= 8*len(in_model))
    no_wrong = all(c["arms"][m]["2"]["wrong"] == 0 for c in cells if c["condition"] != "outside" for m in MODES)
    return {"ranking": "GO" if no_wrong and min(rank) >= 0 and sum(rank) > 0 else "HOLD",
            "budget": "GO" if no_wrong and all(cost) else "HOLD",
            "selective_in_model": "PASS" if all(risk) else "HOLD", "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD",
            "cells": cells, "worlds": len(rows), "oracle_calls": sum(r["oracle_calls"] for r in rows),
            "worker_calls": sum(len(arm) for r in rows for arm in r["resources"].values()),
            "fit_comparisons": sum(s["demo_comparisons"] for r in rows for arm in r["branches"].values() for s in arm)}


def run(ledger, output):
    bank, digest, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], digest, lock["sha256"][BANK_SOURCE],
                   sha(canonical_json(lock)), SEEDS[4], 8, tuple(arms))
    with stage() as root:
        check = ("import importlib.util, sys; sys.path.insert(0,'/solver'); "
                 "print(all(importlib.util.find_spec(m) is None "
                 "for m in ('e14.e14g_bank','e14.e14l_bank','e14.e14l_run')))")
        raw, _ = _sandbox_python(["-c", check], solver=root)
        verify(raw.strip() == b"True", "ranking worker can access evaluator")
        boundary["checks"]["ranking_stage_without_evaluator"] = True
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
    run_parser = sub.add_parser("run")
    run_parser.add_argument("ledger", type=Path)
    run_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "freeze":
        (REPO / BANK).write_bytes(gzip.compress(canonical_json(build()), mtime=0))
        (REPO / LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
