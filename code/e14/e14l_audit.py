"""Reconstruct E1.4l fits, choices, costs, selective predictions and replay."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from e13.contract import canonical_json, input_value
from e13.evaluator.run_ledger import Arm

from .e14g_audit import fit_counts, key, predictions, verify
from .e14g_bank import LENGTHS, alphabet, oracle, sha, trace
from .e14h_route import read
from .e14j_audit import expected_merit
from .e14k_run import deterministic
from .e14l_bank import build
from .e14l_run import frozen, schedule, summary
from .e14l_worker import CAP, FLOOR, LABEL_COST, MODES, proposals


def fp(family, pred, gold):
    if family == "G":
        return pred is not None and gold is None
    return any(pv and not yv for pv, yv in zip(pred, gold, strict=True))


def verify_step(row, block, target, known, gold, mode, step):
    family, probes = block["family"], block["probes"]
    inputs, labels = zip(*known, strict=True)
    scores = {l: fit_counts(family, l, inputs, labels) for l in LENGTHS}
    exact = {l: [w for w, n in tab.items() if n == len(known)] for l, tab in scores.items()}
    live = [l for l in LENGTHS if exact[l]]
    diagnosis = live[0] if len(live) == 1 else None
    table = scores[diagnosis or 5]
    word = min(table, key=lambda w: (-table[w], w))
    pred = predictions(family, probes, word)
    verify((row["diagnosis"], tuple(row["word"]), row["exact"], row["false_positive"])
           == (diagnosis, word, sum(p == y for p, y in zip(pred, gold, strict=True)),
               sum(fp(family, p, y) for p, y in zip(pred, gold, strict=True))), "fallback result mismatch")
    cells = [exact[l] for l in LENGTHS]
    verify(row["class_sha256"] == sha(canonical_json(cells)) and row["compatible"] == list(map(len, cells))
           and row["demo_comparisons"] == len(known)*sum(map(len, scores.values())), "fit or class digest mismatch")
    candidates = [w for cell in cells for w in cell]
    distributions = [{key(oracle(family, w, raw)) for w in candidates} for raw in probes]
    accepted = [(next(iter(outputs)), key(y)) for outputs, y in zip(distributions, gold, strict=True)
                if len(outputs) == 1]
    verify((row["selective_covered"], row["selective_errors"], row["selective_false_positive"])
           == (len(accepted), sum(p != y for p, y in accepted), sum(fp(family, p, y) for p, y in accepted)),
           "selective prediction mismatch")
    seen = {trace(family, raw) for raw in inputs}
    seed = (block["seed"]+step) % 2**32
    expected, attempts = proposals(family, exact, alphabet(family), seed, seen) if len(live) == 2 and step < 2 else ([], 0)
    verify([q["input"] for q in row["offers"]] == expected and len(expected) <= CAP
           and row["proposal_attempts"] == attempts and row["candidate_checks"] == len(expected)*len(candidates),
           "proposal budget or reproducibility mismatch")
    ranking = []
    for i, q in enumerate(row["offers"]):
        raw = q["input"]
        input_value(family, raw)
        events = trace(family, raw)
        length = len(events)
        verify(length in (5, 6, 12) and events not in seen, "invalid or repeated question")
        seen.add(events)
        worst, exclusive = expected_merit(family, raw, exact)
        verify(Fraction(*q["worst"]) == worst and Fraction(*q["exclusive"]) == exclusive, "merit mismatch")
        utility = exclusive / (LABEL_COST+length)
        if worst != 1 and (mode != "gate" or utility >= FLOOR):
            ranking.append((worst, length, -exclusive, i) if mode == "minimax" else (-utility, worst, length, i))
    choice = min(ranking)[-1] if ranking else None
    verify(row["choice"] == choice, "choice mismatch")
    if choice is None:
        verify(row["revealed"] is None, "abstention acquired a label")
        return None
    raw = expected[choice]
    answer = oracle(family, target, raw)
    verify(row["revealed"] == {"input": raw, "output": answer}, "incorrect purchased label")
    return raw, answer


def audit(bank, report):
    arms = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[k] for k in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        block, target = arms.pop(arm)
        target = tuple(target)
        family = block["family"]
        demos = block["demos"]
        gold = predictions(family, block["probes"], target)
        initial = list(zip(demos, predictions(family, demos, target), strict=True))
        verify(set(row["branches"]) == set(MODES) == set(row["resources"]), "missing arm")
        # Shared offers and fits are equal until policies observe different labels.
        matched = {}
        purchases = 0
        for mode, steps in row["branches"].items():
            known = initial.copy()
            meters = row["resources"][mode]
            verify(1 <= len(steps) <= 3 and len(meters) == len(steps), "label cap mismatch")
            for i, (step, meter) in enumerate(zip(steps, meters, strict=True)):
                digest = sha(canonical_json(known))
                common = (step["class_sha256"], step["offers"])
                verify(matched.setdefault(digest, common) == common, "generator differs across matching policy state")
                purchased = verify_step(step, block, target, known, gold, mode, i)
                verify((purchased is None) == (i == len(steps)-1), "terminal state mismatch")
                verify(0 <= meter["cpu_us"] <= 1_000_000 and 0 < meter["rss_kib"] <= 131_072
                       and 0 <= meter["wall_us"] <= 3_000_000, "sandbox resource budget mismatch")
                if purchased is not None:
                    known.append(purchased)
                    purchases += 1
        verify(row["correct"] == row["branches"]["gate"][-1]["exact"] and row["total"] == 8
               and row["status"] == "scored" and row["oracle_calls"] == 40+purchases, "world accounting mismatch")
    verify(not arms and report["status"] == "completed" and report["version"] == 1
           and report["summary"] == summary(report["rows"]), "incomplete report or summary mismatch")


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
