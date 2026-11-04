"""Recompute predictions, fits, selection, label accounting, and gates from a frozen bank."""

import argparse
import gzip
import json
from collections import Counter
from itertools import product
from pathlib import Path

from e13.contract import canonical_json

from .e14g_bank import alphabet, build, oracle, sha, trace
from .e14g_run import HISTORY, REPO, deterministic, frozen


def verify(condition, message):
    if not condition:
        raise ValueError(message)


def predictions(family, inputs, word):
    return [oracle(family, word, raw) for raw in inputs]


def key(output):
    return tuple(output) if isinstance(output, list) else output


def fit_counts(family, length, inputs, gold):
    """Compute matches without using the worker or its output."""
    counts = dict.fromkeys(product(alphabet(family), repeat=length), 0)
    for raw, target in zip(inputs, gold, strict=True):
        events = trace(family, raw)
        hits = {}
        for stop in range(length, len(events) + 1):
            hits.setdefault(events[stop-length:stop], []).append(stop - 1)
        target = key(target)
        blank = (0,) * len(events) if family == "S" else None
        if target == blank:
            counts = {word: n + (word not in hits) for word, n in counts.items()}
        else:
            for word in hits:
                counts[word] += key(oracle(family, word, raw)) == target
    return counts


def check_fit(record, counts, demos):
    best = max(counts.values())
    candidates = [word for word, value in counts.items() if value == best]
    verify((record["fit_matches"], record["candidates"], record["fit_comparisons"])
           == (best, len(candidates), len(counts) * demos), "fit counters disagree")
    return candidates


def check_selection(record, counts, family, pool):
    candidates = check_fit(record, counts, 32)
    parts = [sorted(Counter(key(oracle(family, word, raw)) for word in candidates).values())
             for raw in pool]
    verify(record["partitions"] == parts and record["prediction_calls"] == 8 * len(candidates),
           "committee partition mismatch")
    return {
        "gini": min(range(8), key=lambda i: sum(x*x for x in parts[i])),
        "minimax": min(range(8), key=lambda i: (max(parts[i]), -len(parts[i]))),
        "static": max(range(8), key=lambda i: len(trace(family, pool[i]))),
    }


def check_prediction(record, counts, family, probes, gold, demos):
    candidates = check_fit(record, counts, demos)
    word = min(candidates)
    expected = predictions(family, probes, word)
    count = sum(p == y for p, y in zip(expected, gold, strict=True))
    verify(tuple(record["word"]) == word and record["predictions"] == expected
           and record["correct"] == count and record["prediction_calls"] == 8,
           "prediction or probe-score mismatch")
    return count


def extra_label(counts, family, raw, target):
    return {word: n + (oracle(family, word, raw) == target) for word, n in counts.items()}


def audit_world(block, world, row):
    family, length = block["family"], block["length"]
    pool, demos, probes = (block[role] for role in ("pool", "demos", "probes"))
    true_word = tuple(block["words"][world])
    known, queries, gold = (predictions(family, inputs, true_word) for inputs in (demos, pool, probes))
    counts = fit_counts(family, 5, demos, known)
    chosen = check_selection(row["selection"], counts, family, pool)
    verify(row["chosen"] == chosen, "policy selected a different question")
    baseline = check_prediction(row["no_label"], counts, family, probes, gold, 32)
    branches = [check_prediction(branch, extra_label(counts, family, raw, target), family, probes, gold, 33)
                for branch, raw, target in zip(row["branches"], pool, queries, strict=True)]
    informed_counts = counts if length == 5 else fit_counts(family, length, demos, known)
    informed_query = check_selection(row["informed_selection"], informed_counts, family, pool)["gini"]
    verify(row["informed_query"] == informed_query, "informed selection mismatch")
    informed = check_prediction(row["informed"],
                                extra_label(informed_counts, family, pool[informed_query], queries[informed_query]),
                                family, probes, gold, 33)
    values = {"no_label": baseline * 8, **{name: branches[i] * 8 for name, i in chosen.items()},
              "random": sum(branches), "hindsight": max(branches) * 8, "informed": informed * 8}
    verify(row["score_x8"] == values and row["correct"] == baseline and row["total"] == 8
           and row["status"] == "scored" and row["oracle_calls"] == 48, "world accounting mismatch")
    operations = ["select"] + ["predict"] * 9 + ["select", "predict"]
    verify([item["operation"] for item in row["resources"]] == operations
           and all(0 <= r["cpu_us"] <= 1_000_000 and 0 < r["rss_kib"] <= 131_072
                   and 0 <= r["wall_us"] <= 3_000_000 for r in row["resources"]),
           "worker resource accounting mismatch")
    return values


def audit(bank, report):
    verify(report["status"] == "completed" and report["version"] == 1, "incomplete report")
    index = {(b["distribution"], b["family"], b["length"], b["block"]): b for b in bank["blocks"]}
    groups = {}
    scores = {}
    for row in report["rows"]:
        distribution, slot = row["block"].split(":")
        length = {"related": 5, "unrelated": 6}[row["regime"]]
        cell_key = (distribution, row["family"], length)
        block_key = (*cell_key, int(slot))
        world = int(row["episode"])
        world_key = (*block_key, world)
        verify(world_key not in scores and row["seed_slot"] == 0 and row["policy"] == "world",
               "unexpected world key")
        scores[world_key] = audit_world(index[block_key], world, row)
        groups.setdefault(cell_key, []).append((block_key, row))
    verify(len(index) == 48 and len(scores) == 72
           and set(scores) == {(*b, world) for b, data in index.items() for world in range(len(data["words"]))},
           "bank/world cardinality mismatch")
    verify(len(groups) == 8 and len(report["summary"]["cells"]) == 8, "cell coverage mismatch")
    engineering_checks, natural_checks = [], []
    cell_checks = set()
    for cell in report["summary"]["cells"]:
        k = (cell["distribution"], cell["family"], cell["length"])
        verify(k not in cell_checks, "duplicate aggregate")
        cell_checks.add(k)
        worlds = groups[k]
        paired = {}
        for block_key, row in worlds:
            pair = paired.setdefault(block_key, Counter())
            pair.update(scores[(*block_key, int(row["episode"]))])
        totals = {name: sum(pair[name] for pair in paired.values()) for name in
                  ("no_label", "gini", "minimax", "static", "random", "hindsight", "informed")}
        positives = {name: sum(pair[a] > pair[b] for pair in paired.values())
                     for name in ("hindsight_gt_no_label", "gini_gt_no_label", "gini_gt_random",
                                  "minimax_gt_random", "informed_gt_hindsight")
                     for a, b in [name.split("_gt_")]}
        verify(totals == cell["score_x8"] and positives == cell["positive_blocks"]
               and len(positives) == 5 and len(worlds) == cell["worlds"]
               and len(paired) == cell["blocks"] == 6 and 8 * len(worlds) == cell["probe_total"]
               and cell["oracle_calls"] == 48 * len(worlds)
               and cell["gini_harm_worlds"] == sum(r["score_x8"]["gini"] < r["score_x8"]["no_label"]
                                                  for _, r in worlds)
               and cell["unanimous_pools"] == sum(not any(len(p) > 1 for p in r["selection"]["partitions"])
                                                   for _, r in worlds), "cell aggregate mismatch")
        if k[0] == "opportunity":
            if k[2] == 5:
                engineering_checks.append(min(positives["hindsight_gt_no_label"], positives["gini_gt_random"],
                                              positives["minimax_gt_random"]) >= 5
                                          and min(totals["gini"], totals["minimax"])
                                          > max(totals["static"], totals["no_label"]))
            else:
                engineering_checks.append(totals["hindsight"] <= 32 * len(worlds)
                                          and positives["informed_gt_hindsight"] >= 5)
        elif k[2] == 5:
            natural_checks.append(positives["hindsight_gt_no_label"] >= 3
                                  and positives["gini_gt_no_label"] >= 2 and totals["gini"] > totals["random"])
    summary = report["summary"]
    engineering, natural = all(engineering_checks), all(natural_checks)
    verify(len(engineering_checks) == 4 and len(natural_checks) == 2
           and summary["engineered_gate"] == engineering and summary["natural_gate"] == natural
           and summary["blocks"] == len(index) and summary["worlds"] == len(scores)
           and summary["oracle_calls"] == 48 * len(scores) and summary["worker_calls"] == 12 * len(scores)
           and summary["decision"] == ("BENCHMARK_DEVELOPMENT_GO" if engineering else "BENCHMARK_HOLD_REDESIGN")
           and summary["natural_decision"] == ("NATURAL_DEVELOPMENT_GO" if natural else "NATURAL_HOLD"),
           "decision or totals mismatch")
    return {"audited_worlds": len(scores), "audited_cells": len(groups), "audited_one_label_branches": 8 * len(scores)}


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    bank, bank_sha, _ = frozen()
    history = load(REPO / HISTORY)
    verify(canonical_json(build(history)) == canonical_json(bank), "bank regeneration mismatch")
    report, replay = load(args.result), load(args.replay)
    verify(report["bank_sha256"] == bank_sha and deterministic(report) == deterministic(replay),
           "replay or bank digest mismatch")
    print(json.dumps({"status": "completed", "replay_match": True, **audit(bank, report),
                      "deterministic_sha256": sha(canonical_json(deterministic(report)))}, sort_keys=True))


if __name__ == "__main__":
    main()
