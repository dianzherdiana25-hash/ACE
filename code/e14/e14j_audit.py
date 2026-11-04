"""Audit E1.4j query admissibility, fit, exact ranking, scores, and replay."""

import argparse
import json
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path

from e13.contract import canonical_json, input_value
from e13.evaluator.run_ledger import Arm

from .e14g_audit import fit_counts, key, predictions, verify
from .e14g_bank import LENGTHS, alphabet, oracle, sha, trace
from .e14h_route import read
from .e14j_bank import build
from .e14j_run import deterministic, frozen, schedule, summary
from .e14j_worker import CAP, MODES


def expected_events(mode, pool, seen, exact, family, seed):
    if mode == "fixed":
        stream = [trace(family, raw) for raw in pool]
    else:
        rng = random.Random(seed)
        if mode == "guided":
            short, long = [rng.sample(exact[length], min(CAP, len(exact[length]))) for length in LENGTHS]
            stream = [items[i] for i in range(CAP) for items in (short, long) if i < len(items)]
        else:
            lengths = [rng.choice(LENGTHS) for _ in range(CAP * 8)]
            stream = [tuple(rng.choice(alphabet(family)) for _ in range(n)) for n in lengths]
    return list(dict.fromkeys(events for events in stream if events not in seen))[:CAP], len(stream)


def expected_merit(family, raw, exact):
    a, b = [Counter(key(oracle(family, word, raw)) for word in exact[length]) for length in LENGTHS]
    m, n = map(lambda table: sum(table.values()), (a, b))
    worst = Fraction(max(min(n * a[y], m * b[y]) for y in a.keys() | b.keys()), m * n)
    exclusive = Fraction(sum(n * a[y] for y in a.keys() - b.keys()) +
                         sum(m * b[y] for y in b.keys() - a.keys()), 2 * m * n)
    return worst, exclusive


def validate_step(step, mode, demos, probe_gold, block, true_word, round_index):
    family, probes = block["family"], block["probes"]
    inputs, labels = zip(*demos, strict=True)
    tables = {length: fit_counts(family, length, inputs, labels) for length in LENGTHS}
    exact = {length: [word for word, score in table.items() if score == len(demos)]
             for length, table in tables.items()}
    compatible = [length for length in LENGTHS if exact[length]]
    diagnosis = compatible[0] if len(compatible) == 1 else None
    table = tables[diagnosis or 5]
    word = min(table, key=lambda word: (-table[word], word))
    pred = predictions(family, probes, word)
    exact_score = sum(p == y for p, y in zip(pred, probe_gold, strict=True))
    fp = sum(p is not None and y is None for p, y in zip(pred, probe_gold, strict=True)) if family == "G" else sum(
        any(pv == 1 and yv == 0 for pv, yv in zip(p, y, strict=True)) for p, y in zip(pred, probe_gold, strict=True)
    )
    verify(step["diagnosis"] == diagnosis and tuple(step["word"]) == word and step["exact"] == exact_score
           and step["false_positive"] == fp and step["compatible"] == [len(exact[l]) for l in LENGTHS]
           and step["demo_comparisons"] == len(demos) * sum(map(len, tables.values())), "fit or score mismatch")
    questions = step["offers"]
    seen = {trace(family, raw) for raw in inputs}
    if len(compatible) == 2 and round_index < 2:
        proposed, attempts = expected_events(mode, block["pool"], seen, exact, family,
                                             (block["seed"] + round_index) % 2**32)
    else:
        proposed, attempts = [], 0
    verify([trace(family, q["input"]) for q in questions] == proposed and step["proposal_attempts"] == attempts
           and step["candidate_checks"] == len(proposed) * sum(map(len, exact.values())), "query budget mismatch")
    ranking = []
    for index, question in enumerate(questions):
        raw = question["input"]
        input_value(family, raw)
        if mode == "fixed":
            verify(raw in block["pool"], "fixed policy synthesized a query")
        worst, exclusive = expected_merit(family, raw, exact)
        verify(question["worst"] == [worst.numerator, worst.denominator]
               and question["exclusive"] == [exclusive.numerator, exclusive.denominator], "query merit mismatch")
        if worst != 1:
            ranking.append((worst, len(proposed[index]), -exclusive, index))
    chosen = min(ranking)[-1] if ranking else None
    verify(step["choice"] == chosen, "chosen query mismatch")
    if chosen is None:
        verify(step["revealed"] is None, "stop acquired a label")
        return None
    query = questions[chosen]["input"]
    output = oracle(family, true_word, query)
    verify(step["revealed"] == {"input": query, "output": output}, "revealed label mismatch")
    return query, output


def audit(bank, report):
    arms = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[field] for field in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        block, word = arms.pop(arm)
        family = block["family"]
        true_word = tuple(word)
        original = block["demos"]
        gold = predictions(family, block["probes"], true_word)
        initial = list(zip(original, predictions(family, original, true_word), strict=True))
        verify(set(row["branches"]) == set(MODES) == set(row["resources"]), "policy coverage mismatch")
        acquired = 0
        for mode, steps in row["branches"].items():
            demos = initial.copy()
            metrics = row["resources"][mode]
            verify(len(steps) == len(metrics) and 1 <= len(steps) <= 3, "round budget mismatch")
            for index, (step, usage) in enumerate(zip(steps, metrics, strict=True)):
                answer = validate_step(step, mode, demos, gold, block, true_word, index)
                verify((answer is None) == (index == len(steps)-1), "policy did not stop at its terminal round")
                verify(0 <= usage["cpu_us"] <= 1_000_000 and 0 <= usage["wall_us"] <= 3_000_000
                       and 0 < usage["rss_kib"] <= 131_072, "worker limits not met")
                if answer is not None:
                    demos.append(answer)
                    acquired += 1
        verify(row["status"] == "scored" and row["correct"] == row["branches"]["guided"][-1]["exact"]
               and row["total"] == 8 and row["oracle_calls"] == 40 + acquired, "result accounting mismatch")
    verify(not arms and report["status"] == "completed" and report["version"] == 1
           and report["summary"] == summary(report["rows"]), "report incomplete or inconsistent")


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
