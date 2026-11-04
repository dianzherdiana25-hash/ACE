"""E1.4h: infer the grammar length from demo consistency before querying."""

import argparse
import gzip
import json
import os
import random
from itertools import product
from pathlib import Path

from e13.contract import canonical_json
from e13.evaluator.run_ledger import Arm, RunPlan, run_arms

from .e14g_audit import check_prediction, check_selection, extra_label, fit_counts, predictions, verify
from .e14g_bank import FAMILIES, LENGTHS, _enriched, _pairs, alphabet, natural_inputs, oracle, sha
from .e14g_isolation import invoke, validate_boundary, worker_mount
from .e14g_run import HISTORY, METRICS, REPO, check_worker, frozen, pick

BANK = "evidence/e14/e14h_public_bank_v1.json.gz"
LOCK = "design/e1.4/E14H_LOCK_v1.json"
PROTOCOL = "design/e1.4/E14H_PROTOCOL_v1.md"
FILES = (BANK, PROTOCOL, "code/e14/e14h_route.py", "code/e14/test_e14h.py", "design/e1.4/E14G_LOCK_v1.json")
SEEDS = (142201, 142202, 142203, 142204)
SLOTS = range(6)


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def inputs(block):
    return (raw for role in ("demos", "pool", "probes") for raw in block[role])


def prior_index(previous, history):
    used = {family: set(history[family]) for family in FAMILIES}
    for block in previous["blocks"]:
        used[block["family"]].update(sha(canonical_json(raw)) for raw in inputs(block))
    return used


def build(previous, history):
    used = prior_index(previous, history)
    natural, motifs, enriched = map(random.Random, SEEDS[:3])
    coords = [(family, length, slot) for family in FAMILIES for length in LENGTHS for slot in SLOTS]
    raw = {(family, length, slot): natural_inputs(family, natural, used[family])
           for family, length, slot in coords}
    blocks = []
    for family in FAMILIES:
        for length in LENGTHS:
            old_words = {tuple(w) for b in previous["blocks"] if b["family"] == family and b["length"] == length
                         for w in b["words"]}
            natural_words = motifs.sample([w for w in product(alphabet(family), repeat=length)
                                           if w not in old_words], len(SLOTS))
            for slot, word in enumerate(natural_words):
                blocks.append({"distribution": "natural", "family": family, "length": length,
                               "slot": slot, "words": [word], **raw[family, length, slot]})
            for slot, (twins, witnesses) in enumerate(_pairs(family, length, natural_words, motifs)):
                trials = _enriched(family, length, twins, witnesses, enriched, used[family])
                blocks.append({"distribution": "opportunity", "family": family, "length": length,
                               "slot": slot, "words": twins, **trials})
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}


def choose_grammar(short_matches, long_matches):
    return 6 if short_matches < 32 and long_matches == 32 else 5


def freeze_manifest():
    return {"version": 1, "sha256": {name: sha((REPO / name).read_bytes()) for name in FILES}}


def load_bank():
    _, _, upstream = frozen()
    lock = json.loads((REPO / LOCK).read_bytes())
    verify(lock == freeze_manifest(), "E1.4h frozen source or bank changed")
    raw = gzip.decompress((REPO / BANK).read_bytes())
    return json.loads(raw), sha(raw), lock, upstream


def evaluate(root, block, world):
    family = block["family"]
    pool, probes = block["pool"], block["probes"]
    truth = tuple(block["words"][world])

    def label(raw):
        return {"input": raw, "output": oracle(family, truth, raw)}

    demos = [label(raw) for raw in block["demos"]]
    gold = predictions(family, probes, truth)
    resources = []

    def worker(operation, known, unlabeled, length):
        row = invoke(root, family, operation, known, unlabeled, length=length)
        check_worker(row, family, length, known, unlabeled, operation)
        resources.append({**{name: row.pop(name) for name in METRICS}, "operation": operation})
        return row

    def fit(known, length):
        row = worker("predict", known, probes, length)
        row["correct"] = sum(a == b for a, b in zip(row["predictions"], gold, strict=True))
        return row

    select = {str(length): worker("select", demos, pool, length) for length in LENGTHS}
    chosen = choose_grammar(select["5"]["fit_matches"], select["6"]["fit_matches"])
    queries = {length: pick(row["partitions"], pool, family)["gini"] for length, row in select.items()}
    labels = {i: label(pool[i]) for i in sorted(set(queries.values()))}
    baseline = fit(demos, chosen)
    fits = {length: fit([*demos, labels[i]], int(length)) for length, i in queries.items()}
    score = {"fixed5": fits["5"]["correct"], "fixed6": fits["6"]["correct"],
             "adaptive": fits[str(chosen)]["correct"], "adaptive_no_label": baseline["correct"],
             "informed": fits[str(block["length"])]["correct"]}
    return {"status": "scored", "correct": score["adaptive"], "total": 8, "score": score,
            "selection": select, "route": chosen, "queries": queries, "fits": fits,
            "baseline": baseline, "resources": resources, "oracle_calls": 40 + len(labels)}


def schedule(bank):
    rows = {}
    for b in bank["blocks"]:
        for i in range(len(b["words"])):
            arm = Arm(b["family"], "related" if b["length"] == 5 else "unrelated",
                      f'{b["distribution"]}:{b["slot"]}', str(i), 0, "route")
            verify(arm not in rows, "duplicate planned arm")
            rows[arm] = b
    return rows


def summarize(rows):
    cells = []
    for distribution in ("natural", "opportunity"):
        for family in FAMILIES:
            for length in LENGTHS:
                regime = "related" if length == 5 else "unrelated"
                worlds = [r for r in rows if r["family"] == family and r["regime"] == regime
                          and r["block"].startswith(distribution + ":")]
                blocks = [[r for r in worlds if r["block"] == f"{distribution}:{i}"] for i in SLOTS]
                totals = {name: sum(r["score"][name] for r in worlds) for name in
                          ("fixed5", "fixed6", "adaptive", "adaptive_no_label", "informed")}
                cells.append({"distribution": distribution, "family": family, "length": length,
                              "probe_total": 8 * len(worlds), "score": totals,
                              "routed_blocks": sum(all(r["route"] == length for r in pair) for pair in blocks),
                              "improved_over_fixed5": sum(sum(r["score"]["adaptive"] for r in pair)
                                                          > sum(r["score"]["fixed5"] for r in pair) for pair in blocks),
                              "harm_worlds": sum(r["score"]["adaptive"] < r["score"]["fixed5"] for r in worlds),
                              "neither_perfect": sum(max(r["selection"][l]["fit_matches"] for l in ("5", "6")) < 32
                                                     for r in worlds)})
    opportunity = [c for c in cells if c["distribution"] == "opportunity"]
    passed = all(c["routed_blocks"] >= 5 and (
        c["harm_worlds"] == 0 if c["length"] == 5 else
        c["improved_over_fixed5"] >= 5 and c["score"]["adaptive"] >= c["score"]["informed"] - 8
    ) for c in opportunity)
    for family in FAMILIES:
        both = [c["score"] for c in opportunity if c["family"] == family]
        passed &= sum(s["adaptive"] for s in both) > max(sum(s[n] for s in both) for n in ("fixed5", "fixed6"))
    return {"decision": "ROUTING_DEVELOPMENT_GO" if passed else "ROUTING_HOLD",
            "natural_decision": "NATURAL_HOLD_CARRIED_FORWARD", "worlds": len(rows), "cells": cells,
            "oracle_calls": sum(r["oracle_calls"] for r in rows),
            "worker_calls": sum(len(r["resources"]) for r in rows)}


def deterministic(report):
    return {**report, "rows": [{k: v for k, v in row.items() if k != "resources"} for row in report["rows"]]}


def audit(bank, report):
    blocks = {arm.key: block for arm, block in schedule(bank).items()}
    for row in report["rows"]:
        arm = Arm(*(row[field] for field in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        b = blocks.pop(arm.key)
        family, length = b["family"], b["length"]
        word = tuple(b["words"][int(arm.episode)])
        demos, pool, probes = (b[role] for role in ("demos", "pool", "probes"))
        known, gold = predictions(family, demos, word), predictions(family, probes, word)
        counts = {str(l): fit_counts(family, l, demos, known) for l in LENGTHS}
        queries = {l: check_selection(row["selection"][l], fit, family, pool)["gini"] for l, fit in counts.items()}
        short, long = [max(counts[l].values()) for l in ("5", "6")]
        route = "6" if short != 32 and long == 32 else "5"
        verify(row["route"] == int(route) and row["queries"] == queries, "route or query mismatch")
        base = check_prediction(row["baseline"], counts[route], family, probes, gold, 32)
        expected = {}
        for l, i in queries.items():
            expected[l] = check_prediction(row["fits"][l], extra_label(counts[l], family, pool[i],
                                                                       oracle(family, word, pool[i])),
                                           family, probes, gold, 33)
        score = {"fixed5": expected["5"], "fixed6": expected["6"], "adaptive": expected[route],
                 "adaptive_no_label": base, "informed": expected[str(length)]}
        verify(row["score"] == score and row["correct"] == score["adaptive"] and row["total"] == 8
               and row["oracle_calls"] == 40 + len(set(queries.values())) and len(row["resources"]) == 5
               and row["status"] == "scored", "score or cost mismatch")
    verify(not blocks and len(report["rows"]) == 72 and report["status"] == "completed"
           and report["summary"] == summarize(report["rows"]), "incomplete E1.4h evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "run", "audit"))
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    if args.mode == "freeze":
        previous, _, _ = frozen()
        bank = build(previous, read(REPO / HISTORY))
        (REPO / BANK).write_bytes(gzip.compress(canonical_json(bank), mtime=0))
        (REPO / LOCK).write_text(json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n")
        return
    bank, bank_sha, lock, upstream = load_bank()
    if args.mode == "run":
        ledger, output = args.paths
        boundary = validate_boundary()
        arms = schedule(bank)
        plan = RunPlan(upstream["sha256"]["code/e14/e14g_worker.py"], bank_sha,
                       upstream["sha256"]["code/e14/e14g_bank.py"], sha(canonical_json(lock)),
                       SEEDS[3], 8, tuple(arms))
        with worker_mount() as root:
            rows = run_arms(ledger, plan, lambda arm: evaluate(root, arms[arm], int(arm.episode)))
        report = {"version": 1, "status": "completed", "bank_sha256": bank_sha, "plan_sha256": plan.sha256,
                  "boundary": boundary, "rows": rows, "summary": summarize(rows)}
        temp = output.with_name(output.name + ".tmp")
        temp.write_bytes(gzip.compress(canonical_json(report), mtime=0))
        os.replace(temp, output)
        print(json.dumps(report["summary"], sort_keys=True))
    else:
        report, replay = map(read, args.paths)
        previous, _, _ = frozen()
        verify(canonical_json(bank) == canonical_json(build(previous, read(REPO / HISTORY))),
               "E1.4h bank regeneration mismatch")
        verify(report["bank_sha256"] == bank_sha and deterministic(report) == deterministic(replay), "replay mismatch")
        audit(bank, report)
        print(json.dumps({"status": "completed", "worlds": len(report["rows"]), "replay_match": True,
                          "deterministic_sha256": sha(canonical_json(deterministic(report)))}, sort_keys=True))


if __name__ == "__main__":
    main()
