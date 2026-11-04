"""Audit fit, legal proposals, rankings, purchased answers and replay independently."""

import argparse
import json
from pathlib import Path

from e13.contract import canonical_json, input_value
from e13.evaluator.run_ledger import Arm

from .e14g_audit import fit_counts, predictions, verify
from .e14g_bank import LENGTHS, alphabet, oracle, sha, trace, windows
from .e14h_route import read
from .e14j_audit import expected_merit
from .e14k_bank import build
from .e14k_run import deterministic, frozen, schedule, summary
from .e14k_worker import CAP, LONG, MODES, propose


def verify_step(step, block, target, mode, known, probe_gold, round_index):
    family, probes = block["family"], block["probes"]
    inputs, labels = zip(*known, strict=True)
    tables = {l: fit_counts(family, l, inputs, labels) for l in LENGTHS}
    exact = {l: [w for w, count in t.items() if count == len(known)] for l, t in tables.items()}
    live = [l for l, candidates in exact.items() if candidates]
    diagnosis = live[0] if len(live) == 1 else None
    table = tables[diagnosis or 5]
    word = min(table, key=lambda w: (-table[w], w))
    outputs = predictions(family, probes, word)
    correct = sum(x == y for x, y in zip(outputs, probe_gold, strict=True))
    if family == "G":
        fp = sum(x is not None and y is None for x, y in zip(outputs, probe_gold, strict=True))
    else:
        fp = sum(bool(set(i for i, bit in enumerate(x) if bit) - set(i for i, bit in enumerate(y) if bit))
                 for x, y in zip(outputs, probe_gold, strict=True))
    verify((step["diagnosis"], tuple(step["word"]), step["exact"], step["false_positive"])
           == (diagnosis, word, correct, fp), "diagnosis or score mismatch")
    sizes = list(map(len, exact.values()))
    verify(step["compatible"] == sizes and step["demo_comparisons"] == len(known) * sum(map(len, tables.values())),
           "fit comparison mismatch")
    seen = {trace(family, raw) for raw in inputs}
    if len(live) == 2 and round_index < 2:
        raw, attempts = propose(family, mode, exact, alphabet(family), (block["seed"] + round_index) % 2**32, seen)
    else:
        raw, attempts = [], 0
    offers = step["offers"]
    verify([q["input"] for q in offers] == raw and len(raw) <= CAP and step["proposal_attempts"] == attempts
           and step["candidate_checks"] == len(raw) * sum(sizes), "proposal budget mismatch")
    ranking = []
    for i, q in enumerate(offers):
        raw_input = q["input"]
        input_value(family, raw_input)
        events = trace(family, raw_input)
        verify(events not in seen and len(events) in (LENGTHS if mode == "short" else (LONG,)),
               "illegal or repeated query")
        seen.add(events)
        worst, exclusive = expected_merit(family, raw_input, exact)
        covered = [sum(w in windows(events, l) for w in exact[l]) for l in LENGTHS]
        verify((q["worst"], q["exclusive"], q["covered"])
               == ([worst.numerator, worst.denominator], [exclusive.numerator, exclusive.denominator], covered),
               "query rank or coverage mismatch")
        if worst < 1:
            ranking.append((worst, len(events), -exclusive, i))
    choice = min(ranking)[-1] if ranking else None
    verify(step["choice"] == choice, "selected input mismatch")
    if choice is None:
        verify(step["revealed"] is None, "abstained arm acquired a label")
        return None
    chosen = offers[choice]["input"]
    answer = oracle(family, target, chosen)
    verify(step["revealed"] == {"input": chosen, "output": answer}, "purchased label mismatch")
    return chosen, answer


def audit(bank, report):
    arms = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[key] for key in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        block, target = arms.pop(arm)
        family = block["family"]
        target = tuple(target)
        demos, probes = block["demos"], block["probes"]
        known = list(zip(demos, predictions(family, demos, target), strict=True))
        gold = predictions(family, probes, target)
        purchases = 0
        verify(set(row["branches"]) == set(MODES) == set(row["resources"]), "missing policy arm")
        for mode, steps in row["branches"].items():
            revealed = known.copy()
            metrics = row["resources"][mode]
            verify(1 <= len(steps) <= 3 and len(metrics) == len(steps), "label budget mismatch")
            for i, (step, meter) in enumerate(zip(steps, metrics, strict=True)):
                result = verify_step(step, block, target, mode, revealed, gold, i)
                verify((result is None) == (i == len(steps)-1), "terminal step mismatch")
                verify(0 <= meter["cpu_us"] <= 1_000_000 and 0 < meter["rss_kib"] <= 131_072
                       and 0 <= meter["wall_us"] <= 3_000_000, "worker resource budget mismatch")
                if result is not None:
                    revealed.append(result)
                    purchases += 1
        verify(row["oracle_calls"] == 40 + purchases and row["correct"] == row["branches"]["compound"][-1]["exact"]
               and row["status"] == "scored" and row["total"] == 8, "world accounting mismatch")
    verify(not arms and report["status"] == "completed" and report["version"] == 1
           and report["summary"] == summary(report["rows"]), "incomplete report or aggregate mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    bank, digest, _ = frozen()
    verify(canonical_json(bank) == canonical_json(build()), "bank regeneration mismatch")
    report, replay = read(args.result), read(args.replay)
    verify(report["bank_sha256"] == digest and deterministic(report) == deterministic(replay), "replay mismatch")
    audit(bank, report)
    print(json.dumps({"status": "completed", "worlds": len(report["rows"]), "replay_match": True,
                      "deterministic_sha256": sha(canonical_json(deterministic(report)))}, sort_keys=True))


if __name__ == "__main__":
    main()
