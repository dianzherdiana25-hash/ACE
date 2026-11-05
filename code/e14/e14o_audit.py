"""Independently recompute version spaces, bought labels, ranking and probe outcomes."""

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
from .e14l_audit import fp
from .e14m_audit import blank
from .e14m_worker import offer
from .e14n_audit import reference
from .e14n_worker import EXPANSION_LENGTHS
from .e14o_bank import build
from .e14o_run import deterministic, frozen, schedule, summary
from .e14o_worker import CAP, LABEL_CAP, MODES, recovery_offers


def check_step(row, block, target, inputs, labels, gold, mode, index):
    f = block["family"]
    exact = {l: [w for w, n in fit_counts(f, l, inputs, labels).items() if n == len(inputs)] for l in LENGTHS}
    triggered = not any(exact.values())
    anchor_checks = expanded = 0
    classes = list(exact.values())
    if triggered:
        anchor = next((i for i, y in enumerate(labels) if not blank(f, y)), None)
        if anchor is None:
            classes = [[], [], []]
        else:
            windows_found, proposed, survivors, _ = reference(f, inputs, labels, anchor)
            anchor_checks, expanded = sum(map(len, windows_found.values())), sum(map(len, proposed.values()))
            classes = list(survivors.values())
    words = [w for group in classes for w in group]
    sets = [{key(oracle(f, w, x)) for w in words} for x in block["probes"]]
    released = [(next(iter(s)), key(y)) for s, y in zip(sets, gold, strict=True) if len(s) == 1]
    verify((row["trigger"], row["class_sha256"], row["survivors"], row["expansion_fits"], row["anchor_checks"],
            row["base_comparisons"], row["selective_covered"], row["selective_errors"], row["selective_false_positive"])
           == (triggered, sha(canonical_json(classes)), len(words), expanded, anchor_checks,
               len(inputs)*sum(len(alphabet(f))**l for l in LENGTHS), len(released),
               sum(p != y for p,y in released), sum(fp(f,p,y) for p,y in released)), "fit, cost or probe mismatch")
    seed = (block["seed"]+index) % 2**32
    seen = {trace(f, x) for x in inputs}
    attempts, expected, past = 0, [], set()
    if index < LABEL_CAP and triggered:
        expected = recovery_offers(mode, words, alphabet(f), seed, seen)
        attempts = len(expected)
    elif index < LABEL_CAP:
        known = [{"input":x,"output":y} for x,y in zip(inputs, labels, strict=True)]
        expected, attempts, past = offer(f, "falsify", known, exact, alphabet(f), seed)
    offers = row["offers"]
    verify([trace(f,q["input"]) for q in offers] == expected and len(expected) <= CAP
           and row["offer_attempts"] == attempts and row["model_checks"] == len(words)*len(offers),
           "offer budget mismatch")
    ranks = []
    for i, q in enumerate(offers):
        raw = q["input"]
        input_value(f, raw)
        events = trace(f, raw)
        verify(events not in seen and len(events) in (EXPANSION_LENGTHS if triggered else (9,)), "invalid question")
        seen.add(events)
        votes = Counter(key(oracle(f,w,raw)) for w in words)
        if triggered:
            collision = sum(n*n for n in votes.values())
            verify(q["collision"] == collision, "partition mismatch")
            if mode == "random" or collision < len(words)**2:
                ranks.append((0 if mode == "random" else collision, i))
        else:
            common = len(votes) == 1 and blank(f, next(iter(votes)))
            worst = expected_merit(f,raw,exact)[0] if all(exact.values()) else Fraction(max(votes.values()),len(words))
            novel = len(windows(events,7)-past)
            verify((q["blank_consensus"], Fraction(*q["worst"]), q["novel_sevens"]) == (common,worst,novel),
                   "falsification merit mismatch")
            if common and novel:
                ranks.append((-novel,i))
    choice = min(ranks)[-1] if ranks else None
    verify(row["choice"] == choice, "choice mismatch")
    if choice is None:
        verify(row["revealed"] is None, "unexpected purchased label")
        return None
    raw = offers[choice]["input"]
    y = oracle(f, target, raw)
    verify(row["revealed"] == {"input":raw,"output":y}, "label mismatch")
    return raw,y


def audit(bank, report):
    arms = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[k] for k in ("family","regime","block","episode","seed_slot","policy")))
        block, target = arms.pop(arm)
        f, demos = block["family"], block["demos"]
        gold = predictions(f, block["probes"], target)
        initial = predictions(f, demos, target)
        paths = set(row["branches"])
        verify(paths == set(row["resources"]) == set(MODES), "missing strategy")
        buys = 0
        for mode, steps in row["branches"].items():
            inputs, labels = demos.copy(), initial.copy()
            meters = row["resources"][mode]
            verify(1 <= len(steps) == len(meters) <= LABEL_CAP+1, "step cap mismatch")
            for i, (step, meter) in enumerate(zip(steps, meters, strict=True)):
                purchase = check_step(step,block,target,inputs,labels,gold,mode,i)
                verify((purchase is None) == (i == len(steps)-1) and 0 <= meter["cpu_us"] <= 1_000_000
                       and 0 < meter["rss_kib"] <= 131_072 and 0 <= meter["wall_us"] <= 3_000_000,
                       "terminal or resource mismatch")
                if purchase:
                    inputs.append(purchase[0])
                    labels.append(purchase[1])
                    buys += 1
        end = row["branches"]["active"][-1]
        verify(row["oracle_calls"] == 40+buys and row["correct"] == end["selective_covered"]-end["selective_errors"]
               and row["total"] == 8 and row["status"] == "scored", "world accounting mismatch")
    verify(not arms and report["summary"] == summary(report["rows"]) and report["status"] == "completed",
           "incomplete report or summary mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score",type=Path)
    parser.add_argument("replay",type=Path)
    args = parser.parse_args()
    bank,digest,_ = frozen()
    score,replay = read(args.score),read(args.replay)
    verify(canonical_json(bank) == canonical_json(build()), "bank reconstruction mismatch")
    verify(score["bank_sha256"] == digest and deterministic(score) == deterministic(replay), "replay mismatch")
    audit(bank,score)
    print(json.dumps({"status":"COMPLETE","worlds":len(score["rows"]),"replay_match":True,
                      "deterministic_sha256":sha(canonical_json(deterministic(score)))},sort_keys=True))


if __name__ == "__main__":
    main()
