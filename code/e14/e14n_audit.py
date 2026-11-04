"""Audit exact recovery and candidate costs with the evaluator's oracle."""

import argparse
import json
from pathlib import Path

from e13.contract import canonical_json
from e13.evaluator.run_ledger import Arm

from .e14g_audit import fit_counts, key, predictions, verify
from .e14g_bank import LENGTHS, alphabet, oracle, sha, trace, windows
from .e14h_route import read
from .e14l_audit import fp
from .e14m_audit import blank
from .e14n_bank import build
from .e14n_run import deterministic, frozen, schedule, summary
from .e14n_worker import EXPANSION_LENGTHS, LABEL_CAP, MODES


def reference(family, inputs, labels, anchor):
    x, y = inputs[anchor], labels[anchor]
    words = {length: sorted(windows(trace(family, x), length)) for length in EXPANSION_LENGTHS}
    candidates = {l: [w for w in group if oracle(family, w, x) == y] for l, group in words.items()}
    suffix_checks, accepted = {}, {}
    remaining = [(raw, label) for i, (raw, label) in enumerate(zip(inputs, labels, strict=True)) if i != anchor]
    for length, group in candidates.items():
        checked = 0
        survivors = []
        for word in group:
            for raw, expected in remaining:
                checked += 1
                if oracle(family, word, raw) != expected:
                    break
            else:
                survivors.append(word)
        suffix_checks[length] = checked
        accepted[length] = survivors
    return words, candidates, accepted, suffix_checks


def audit_step(step, family, inputs, labels, probes, gold):
    tables = {l: fit_counts(family, l, inputs, labels) for l in LENGTHS}
    base = [[w for w, n in table.items() if n == len(inputs)] for table in tables.values()]
    anchor = next((i for i, y in enumerate(labels) if not blank(family, y)), None) if not any(base) else None
    verify((step["base_counts"], step["base_sha256"], step["anchor"], step["base_comparisons"])
           == (list(map(len, base)), sha(canonical_json(base)), anchor,
               len(inputs)*sum(map(len, tables.values()))), "base version space or trigger mismatch")
    verify(set(step["arms"]) == set(MODES), "missing expansion comparison")
    if anchor is not None:
        all_words, proposed, accepted, costs = reference(family, inputs, labels, anchor)
    for mode in MODES:
        classes, attempted, comparisons, anchor_checks = base, 0, 0, 0
        if anchor is not None and mode != "hold":
            lengths = (7,) if mode == "fixed7" else EXPANSION_LENGTHS
            classes = [accepted[l] if l in lengths else [] for l in EXPANSION_LENGTHS]
            if mode == "directed":
                attempted = sum(map(len, proposed.values()))
                anchor_checks = sum(map(len, all_words.values()))
            else:
                attempted = sum(len(alphabet(family))**l for l in lengths)
            comparisons = attempted + sum(costs[l] for l in lengths)
        survivors = [w for group in classes for w in group]
        possible = [{key(oracle(family, w, raw)) for w in survivors} for raw in probes]
        released = [(next(iter(values)), key(y)) for values, y in zip(possible, gold, strict=True) if len(values) == 1]
        expected = {"attempted": attempted, "comparisons": comparisons, "anchor_checks": anchor_checks,
                    "class_sha256": sha(canonical_json(classes)), "survivors": len(survivors),
                    "selective_covered": len(released), "selective_errors": sum(p != y for p, y in released),
                    "selective_false_positive": sum(fp(family, p, y) for p, y in released)}
        verify(step["arms"][mode] == expected, "expansion, cost or held-out prediction mismatch")


def audit(bank, report):
    arms = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[k] for k in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        block, target = arms.pop(arm)
        target = tuple(target)
        family = block["family"]
        probes, observations = (block[k] for k in ("probes", "observations"))
        inputs = block["demos"].copy()
        labels, gold = (predictions(family, x, target) for x in (inputs, probes))
        steps, meters = (row[k] for k in ("steps", "resources"))
        verify(len(steps) == len(meters) == len(observations)+1 <= LABEL_CAP+1, "step or label cap mismatch")
        for i, (step, meter) in enumerate(zip(steps, meters, strict=True)):
            expected = None
            if i:
                x = observations[i-1]
                y = oracle(family, target, x)
                inputs.append(x)
                labels.append(y)
                expected = {"input": x, "output": y}
            verify(step["revealed"] == expected, "observation mismatch")
            audit_step(step, family, inputs, labels, probes, gold)
            branches = meter["expansion_cpu_us"]
            verify(0 <= meter["cpu_us"] <= 1_000_000 and 0 < meter["rss_kib"] <= 131_072
                   and 0 <= meter["wall_us"] <= 3_000_000
                   and set(branches) == (set(MODES[1:]) if step["anchor"] is not None else set())
                   and all(0 <= us <= 1_000_000 for us in branches.values()), "worker budget mismatch")
        final = steps[-1]["arms"]["directed"]
        verify(row["correct"] == final["selective_covered"]-final["selective_errors"]
               and row["status"] == "scored" and row["total"] == 8
               and row["oracle_calls"] == 40+len(observations), "world score mismatch")
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
