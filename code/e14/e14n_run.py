"""Run frozen conditional representation expansion with held-out probes."""

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
from .e14g_isolation import validate_boundary
from .e14g_run import REPO
from .e14l_run import selective
from .e14m_run import frozen as prior_frozen, stage as prior_stage
from .e14n_bank import CONDITIONS, SEEDS, build
from .e14n_worker import CANDIDATE_CAP, EXPANSION_LENGTHS, LABEL_CAP, MODES

BANK = "evidence/e14/e14n_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14N_LOCK_v1.json"
WORKER = "code/e14/e14n_worker.py"
BANK_SOURCE = "code/e14/e14n_bank.py"
FILES = (BANK, WORKER, BANK_SOURCE, "design/e1.4/E14M_LOCK_v1.json", "design/e1.4/E14N_PROTOCOL_v1.md",
         "code/e14/e14n_run.py", "code/e14/e14n_audit.py", "code/e14/test_e14n.py")


def manifest():
    return {"version": 1, "sha256": {p: sha((REPO / p).read_bytes()) for p in FILES}}


def frozen():
    prior_frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == manifest(), "E1.4n freeze manifest mismatch")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock


def schedule(bank):
    arms = {}
    for block in bank["blocks"]:
        for world in block["worlds"]:
            length = len(world["word"])
            arm = Arm(block["family"], "related" if length == 5 else "unrelated",
                      f'{world["condition"]}:{block["slot"]}', str(length), 0, "expansion")
            verify(arm not in arms, "duplicate world")
            arms[arm] = block, world["word"]
    verify(len(arms) == 72, "incorrect world count")
    return arms


@contextmanager
def stage():
    with prior_stage() as root:
        shutil.copyfile(REPO / WORKER, root / "e14/e14n_worker.py")
        yield root


def invoke(root, packet):
    command = ("import sys; sys.path.insert(0,'/solver'); from e14.e14n_worker import main; "
               f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
    raw, wall = _sandbox_python(["-c", command], canonical_json(packet), solver=root)
    out = read_json(raw, 24_576)
    require_fields(out, "cpu_us", "rss_kib", "base", "anchor", "expansions", "base_comparisons")
    meter = {"cpu_us": integer(out.pop("cpu_us"), 0, 1_000_000), "rss_kib": integer(out.pop("rss_kib"), 1, 131_072),
             "wall_us": integer(wall, 0, 3_000_000)}
    return out, meter


def validate_classes(family, classes, lengths):
    symbols = alphabet(family)
    verify(len(classes) == len(lengths) and all(len(words) <= len(symbols)**l and all(
        len(w) == l and all(type(v) is int and v in symbols for v in w) for w in words
    ) for l, words in zip(lengths, classes, strict=True)), "invalid typed word")


def evaluate(root, block, word):
    family, target = block["family"], tuple(word)
    probes = block["probes"]
    gold = [oracle(family, target, raw) for raw in probes]
    known = [{"input": x, "output": oracle(family, target, x)} for x in block["demos"]]
    observations = block["observations"]
    verify(len(observations) <= LABEL_CAP, "label budget exceeded")
    steps, meters = [], []
    seen = {trace(family, x) for x in block["demos"]}
    for index in range(len(observations)+1):
        answer = None
        if index:
            raw = observations[index-1]
            events = trace(family, raw)
            verify(events not in seen, "repeated labeled trace")
            seen.add(events)
            answer = {"input": raw, "output": oracle(family, target, raw)}
            known.append(answer)
        out, meter = invoke(root, {"family": family, "demos": known})
        base, expansions = out["base"], out["expansions"]
        validate_classes(family, base, LENGTHS)
        anchor = out["anchor"]
        verify(set(expansions) == (set(MODES[1:]) if anchor is not None else set()) and
               (anchor is None or not any(base) and type(anchor) is int and 0 <= anchor < len(known)),
               "invalid expansion trigger")
        arms, branch_cpu = {}, {}
        for mode in MODES:
            if mode in expansions:
                record = expansions[mode]
                require_fields(record, "classes", "attempted", "comparisons", "anchor_checks", "cpu_us")
                classes = record.pop("classes")
                validate_classes(family, classes, EXPANSION_LENGTHS)
                integer(record["attempted"], 0, CANDIDATE_CAP)
                integer(record["comparisons"], 0, CANDIDATE_CAP*len(known))
                integer(record["anchor_checks"], 0, 3*64)
                branch_cpu[mode] = integer(record.pop("cpu_us"), 0, 1_000_000)
            else:
                classes = base
                record = {"attempted": 0, "comparisons": 0, "anchor_checks": 0}
            arms[mode] = {**record, "class_sha256": sha(canonical_json(classes)), "survivors": sum(map(len, classes)),
                          **selective(family, classes, probes, gold)}
        steps.append({"base_counts": list(map(len, base)), "base_sha256": sha(canonical_json(base)),
                      "anchor": anchor, "base_comparisons": out["base_comparisons"], "revealed": answer,
                      "arms": arms})
        meters.append({**meter, "expansion_cpu_us": branch_cpu})
    final = steps[-1]["arms"]["directed"]
    return {"status": "scored", "total": 8, "correct": final["selective_covered"]-final["selective_errors"],
            "steps": steps, "resources": meters, "oracle_calls": 40+len(observations)}


def totals(rows, mode):
    out = dict.fromkeys(("solved", "full_probe_success", "selective_covered", "selective_errors",
                         "selective_false_positive", "candidate_fits", "comparison_calls", "anchor_checks"), 0)
    for r in rows:
        final = r["steps"][-1]["arms"][mode]
        out["solved"] += final["survivors"] > 0
        out["full_probe_success"] += final["selective_covered"] == 8 and final["selective_errors"] == 0
        for key in ("selective_covered", "selective_errors", "selective_false_positive"):
            out[key] += final[key]
        for step in r["steps"]:
            arm = step["arms"][mode]
            out["candidate_fits"] += arm["attempted"]
            out["comparison_calls"] += arm["comparisons"]
            out["anchor_checks"] += arm["anchor_checks"]
    return out


def summary(rows):
    cells = []
    for family in FAMILIES:
        for condition in CONDITIONS:
            group = [r for r in rows if r["family"] == family and r["block"].startswith(condition+":")]
            cells.append({"family": family, "condition": condition, "worlds": len(group),
                          "contradictions": sum(any(not any(s["base_counts"]) for s in r["steps"]) for r in group),
                          "expanded_worlds": sum(any(s["anchor"] is not None for s in r["steps"]) for r in group),
                          "arms": {m: totals(group, m) for m in MODES}})
    equal = all(s["arms"]["directed"]["class_sha256"] == s["arms"]["enumerate"]["class_sha256"]
                for r in rows for s in r["steps"])
    in_model_safe = all(c["expanded_worlds"] == 0 for c in cells
                        if c["condition"] in ("natural", "matched", "no_trigger"))
    outside_safe = all(c["arms"]["directed"]["selective_covered"] == 0 for c in cells if c["condition"] == "outside")
    repairs = [c["arms"] for c in cells if c["condition"] == "repair"]
    threshold = all(a["directed"]["full_probe_success"] >= 8
                    and a["directed"]["full_probe_success"] > a["fixed7"]["full_probe_success"]
                    and 20*a["directed"]["candidate_fits"] <= a["enumerate"]["candidate_fits"]
                    for a in repairs)
    return {"repair": "GO" if equal and in_model_safe and outside_safe and threshold else "HOLD",
            "directed_equals_enumeration": equal, "trigger_control_pass": in_model_safe,
            "outside_abstention_pass": outside_safe, "rare_decision": "RARE_HOLD_CARRIED_FORWARD",
            "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD", "worlds": len(rows), "cells": cells,
            "oracle_calls": sum(r["oracle_calls"] for r in rows), "worker_calls": sum(len(r["resources"]) for r in rows),
            "base_comparisons": sum(s["base_comparisons"] for r in rows for s in r["steps"])}


def deterministic(report):
    return {**report, "rows": [{k: v for k, v in r.items() if k != "resources"} for r in report["rows"]]}


def run(ledger, output):
    bank, digest, lock = frozen()
    boundary = validate_boundary()
    arms = schedule(bank)
    plan = RunPlan(lock["sha256"][WORKER], digest, lock["sha256"][BANK_SOURCE],
                   sha(canonical_json(lock)), SEEDS[3], 8, tuple(arms))
    with stage() as root:
        check = ("import importlib.util,sys; sys.path.insert(0,'/solver'); "
                 "print(all(importlib.util.find_spec(m) is None "
                 "for m in ('e14.e14g_bank','e14.e14n_bank','e14.e14n_run')))")
        raw, _ = _sandbox_python(["-c", check], solver=root)
        verify(raw.strip() == b"True", "worker mount exposes evaluator")
        boundary["checks"]["expansion_stage_without_evaluator"] = True
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
        (REPO / LOCK).write_text(json.dumps(manifest(), indent=2, sort_keys=True)+"\n")
    else:
        run(args.ledger, args.output)


if __name__ == "__main__":
    main()
