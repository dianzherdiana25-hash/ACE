"""Recompute E1.4m version spaces, counterexamples, risks and costs."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from e13.contract import canonical_json, input_value
from e13.evaluator.run_ledger import Arm

from .e14g_audit import fit_counts, key, predictions, verify
from .e14g_bank import LENGTHS, alphabet, oracle, sha, trace, windows
from .e14h_route import read
from .e14j_audit import expected_merit
from .e14k_run import deterministic
from .e14l_audit import fp
from .e14m_bank import build
from .e14m_run import frozen, schedule, summary
from .e14m_worker import CAP, LABEL_CAP, MODES, QUERY_LENGTH, offer


def blank(family, output):
    return not any(output) if family == "S" else output is None


def verify_step(row, block, target, known, gold, mode, index):
    family, probes = block["family"], block["probes"]
    inputs, labels = zip(*known, strict=True)
    scores = {l: fit_counts(family, l, inputs, labels) for l in LENGTHS}
    exact = {l: [word for word, n in tab.items() if n == len(known)] for l, tab in scores.items()}
    classes = [exact[l] for l in LENGTHS]
    candidates = [w for group in classes for w in group]
    verify((row["class_sha256"], row["compatible"], row["rejected"], row["demo_comparisons"])
           == (sha(canonical_json(classes)), list(map(len, classes)), not candidates,
               len(known)*sum(map(len, scores.values()))), "invalid version space")
    groups = [{key(oracle(family, w, probe)) for w in candidates} for probe in probes]
    accepted = [(next(iter(values)), key(y)) for values, y in zip(groups, gold, strict=True) if len(values) == 1]
    verify((row["selective_covered"], row["selective_errors"], row["selective_false_positive"])
           == (len(accepted), sum(p != y for p, y in accepted), sum(fp(family, p, y) for p, y in accepted)),
           "selective prediction mismatch")
    observed_blank = [trace(family, raw) for raw, y in known if blank(family, y)]
    past7 = set().union(*(windows(x, 7) for x in observed_blank))
    past6 = set().union(*(windows(x, 6) for x in observed_blank))
    seen = {trace(family, raw) for raw in inputs}
    if candidates and index < LABEL_CAP:
        demos = [{"input": raw, "output": y} for raw, y in known]
        expected, attempts, _ = offer(family, mode, demos, exact, alphabet(family), (block["seed"]+index) % 2**32)
    else:
        expected, attempts = [], 0
    verify([trace(family, q["input"]) for q in row["offers"]] == expected and len(expected) <= CAP
           and row["proposal_attempts"] == attempts and row["candidate_checks"] == len(expected)*len(candidates),
           "proposal accounting mismatch")
    ranking = []
    for i, q in enumerate(row["offers"]):
        raw = q["input"]
        input_value(family, raw)
        events = trace(family, raw)
        verify(len(events) == QUERY_LENGTH and events not in seen, "invalid or repeated query")
        seen.add(events)
        counts = Counter(key(oracle(family, w, raw)) for w in candidates)
        common_blank = len(counts) == 1 and blank(family, next(iter(counts)))
        worst = (expected_merit(family, raw, exact)[0] if all(classes)
                 else Fraction(max(counts.values()), len(candidates)))
        novel = len(windows(events, 7)-past7)
        verify((q["blank_consensus"], Fraction(*q["worst"]), q["novel_sevens"]) == (common_blank, worst, novel),
               "query score mismatch")
        if mode == "adjudicate" and worst < 1:
            ranking.append((worst, i))
        if mode == "falsify" and common_blank and novel:
            verify(windows(events, 6) <= past6, "falsification without a negative-window certificate")
            ranking.append((-novel, i))
    choice = (0 if expected else None) if mode == "random" else min(ranking)[-1] if ranking else None
    verify(row["choice"] == choice, "choice mismatch")
    if choice is None:
        verify(row["revealed"] is None, "label purchased without choice")
        return None
    raw = row["offers"][choice]["input"]
    y = oracle(family, target, raw)
    verify(row["revealed"] == {"input": raw, "output": y}, "purchased label mismatch")
    return raw, y


def audit(bank, report):
    arms = schedule(bank)
    shared = {}
    for row in report["rows"]:
        arm = Arm(*(row[k] for k in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        block, target = arms.pop(arm)
        target = tuple(target)
        family = block["family"]
        demos = block["demos"]
        gold = predictions(family, block["probes"], target)
        initial = list(zip(demos, predictions(family, demos, target), strict=True))
        verify(set(row["branches"]) == set(MODES) == set(row["resources"]), "missing arm")
        purchases = 0
        for mode, steps in row["branches"].items():
            known = initial.copy()
            meters = row["resources"][mode]
            verify(1 <= len(steps) <= LABEL_CAP+1 and len(steps) == len(meters), "label cap mismatch")
            for i, (step, meter) in enumerate(zip(steps, meters, strict=True)):
                signature = (family, (block["seed"]+i) % 2**32, sha(canonical_json(known)), mode == "random")
                common = (step["class_sha256"], step["offers"])
                verify(shared.setdefault(signature, common) == common, "generator differs at matched state")
                purchased = verify_step(step, block, target, known, gold, mode, i)
                verify((purchased is None) == (i == len(steps)-1), "terminal step mismatch")
                verify(0 <= meter["cpu_us"] <= 1_000_000 and 0 < meter["rss_kib"] <= 131_072
                       and 0 <= meter["wall_us"] <= 3_000_000, "sandbox resource budget mismatch")
                if purchased is not None:
                    known.append(purchased)
                    purchases += 1
        end = row["branches"]["falsify"][-1]
        verify(row["correct"] == end["selective_covered"]-end["selective_errors"] and row["total"] == 8
               and row["status"] == "scored" and row["oracle_calls"] == 40+purchases, "world accounting mismatch")
    verify(not arms and report["status"] == "completed" and report["version"] == 1
           and report["summary"] == summary(report["rows"]), "incomplete or inconsistent report")


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
