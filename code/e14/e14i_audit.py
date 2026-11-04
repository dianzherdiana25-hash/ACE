"""Audit E1.4i from exact evaluator-side fits and independently replayed evidence."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from e13.contract import canonical_json
from e13.evaluator.run_ledger import Arm

from .e14g_audit import check_fit, check_prediction, extra_label, fit_counts, predictions, verify
from .e14g_bank import LENGTHS, oracle, sha
from .e14h_route import read
from .e14i_bank import build
from .e14i_run import deterministic, frozen, schedule, summarize


def fingerprint(family, label):
    return tuple(i for i, bit in enumerate(label) if bit) if family == "S" else label


def check_selection(family, counts, pool, selection):
    histograms = {}
    for length, count in counts.items():
        row = selection[length]
        best = check_fit(row, count, 32)
        hists = [Counter(fingerprint(family, oracle(family, word, raw)) for word in best) for raw in pool]
        expected = [sorted(hist.items(), key=lambda item: canonical_json(item[0])) for hist in hists]
        verify(canonical_json(row["histograms"]) == canonical_json(expected)
               and row["prediction_calls"] == len(pool) * len(best), "committee histogram mismatch")
        histograms[length] = hists
    n5, n6 = [selection[length]["candidates"] for length in ("5", "6")]
    den = 2 * n5 * n6
    scores = [sum(abs(Fraction(x[k], n5) - Fraction(y[k], n6)) for k in x.keys() | y.keys()) / 2
              for x, y in zip(histograms["5"], histograms["6"], strict=True)]
    return histograms, scores, [[int(p * den) for p in scores], den]


def check_branch(family, fits, counts, probes, labels, revealed):
    result = {}
    for length, counts_for_length in counts.items():
        row = fits[length]
        exact = check_prediction(row, counts_for_length, family, probes, labels, revealed)
        pred = row["predictions"]
        if family == "G":
            fp = sum(p is not None and label is None for p, label in zip(pred, labels, strict=True))
        else:
            fp = sum(bool(set(fingerprint(family, p)) - set(fingerprint(family, label)))
                     for p, label in zip(pred, labels, strict=True))
        verify(row["false_positive"] == fp, "false-positive mismatch")
        result[int(length)] = (exact, fp, max(counts_for_length.values()) == revealed)
    return result


def measured_outcome(result, fallback, actual, n, forced=None):
    consistent = [length for length, item in result.items() if item[2]]
    diag = forced if forced is not None else consistent[0] if len(consistent) == 1 else None
    exact, false_positive, _ = result[fallback if diag is None else diag]
    return {"diagnosis": diag, "diagnosed_correct": int(diag == actual), "abstained": int(diag is None),
            "exact": exact, "false_positive": false_positive, "labels": n}


def check_world(block, word, pool, row):
    family = block["family"]
    target = tuple(word)
    demos, probes = block["demos"], block["probes"]
    known, queries, gold = (predictions(family, x, target) for x in (demos, pool, probes))
    counts = {str(n): fit_counts(family, n, demos, known) for n in LENGTHS}
    hists, tv, distance = check_selection(family, counts, pool, row["classes"])
    consistent = [l for l in counts if max(counts[l].values()) == 32]
    route = 6 if consistent == ["6"] else 5
    query_h = min(range(8), key=lambda i: sum(n*n for n in hists[str(route)][i].values()))
    query_cross = tv.index(max(tv)) if len(consistent) == 2 and max(tv) > 0 else None
    verify((row["distance"], row["route_h"], row["query_h"], row["query_cross"])
           == (distance, route, query_h, query_cross), "query selection mismatch")
    base = check_branch(family, row["base"], counts, probes, gold, 32)
    branches = []
    for record, raw, label in zip(row["branches"], pool, queries, strict=True):
        updated = {l: extra_label(table, family, raw, label) for l, table in counts.items()}
        branches.append(check_branch(family, record, updated, probes, gold, 33))
    zero = measured_outcome(base, route, len(word), 0)
    one = [measured_outcome(b, route, len(word), 1) for b in branches]
    cross = zero if query_cross is None else one[query_cross]
    old = measured_outcome(branches[query_h], route, len(word), 1, forced=route)
    verify(row["outcomes"] == {"zero": zero, "one_label": one, "cross": cross, "e14h": old}
           and row["correct"] == cross["exact"] and row["total"] == 8 and row["oracle_calls"] == 48
           and row["status"] == "scored", "world outcome mismatch")
    resources = row["resources"]
    verify([r["kind"] for r in resources] == ["selector"] + ["fit"] * 18 and all(
        0 <= r["cpu_us"] <= 1_000_000 and 0 < r["rss_kib"] <= 131_072 and 0 <= r["wall_us"] <= 3_000_000
        for r in resources), "worker resource accounting mismatch")


def audit(bank, report):
    by_arm = schedule(bank)
    for row in report["rows"]:
        arm = Arm(*(row[field] for field in ("family", "regime", "block", "episode", "seed_slot", "policy")))
        check_world(*by_arm.pop(arm), row)
    verify(not by_arm and report["status"] == "completed" and report["version"] == 1
           and report["summary"] == summarize(report["rows"]), "incomplete or inconsistent evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    bank, sha_bank, _ = frozen()
    verify(canonical_json(bank) == canonical_json(build()), "bank cannot be reproduced")
    report, replay = read(args.report), read(args.replay)
    verify(report["bank_sha256"] == sha_bank and deterministic(report) == deterministic(replay), "replay mismatch")
    audit(bank, report)
    print(json.dumps({"status": "completed", "worlds": len(report["rows"]), "one_label_branches": 8 * len(report["rows"]),
                      "replay_match": True, "deterministic_sha256": sha(canonical_json(deterministic(report)))},
                     sort_keys=True))


if __name__ == "__main__":
    main()
