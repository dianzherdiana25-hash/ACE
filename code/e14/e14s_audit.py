"""Verify E1.4s totals using a separate calculation of receipt-language sizes."""

import argparse
import json
from itertools import product
from pathlib import Path

from .e14g_audit import verify
from .e14g_bank import sha
from .e14h_route import read


def witnesses(word, short_words):
    prefix, suffix = word[:-1], word[1:]
    return ({w for w in short_words if w in prefix}, {w for w in short_words if w in suffix})


def expected(length):
    shorter = tuple("".join(word) for n in range(5, length) for word in product("12", repeat=n))
    total = (2 ** length) * sum(2 ** n for n in range(5, 10))
    mapped = 3 * (2 ** length)
    aliases = 0
    queries = {mode: {2: 0, 3: 0} for mode in ("fixed", "active")}
    correct = {mode: 0 for mode in queries}
    for word in map("".join, product("12", repeat=length)):
        flip = {"1": "2", "2": "1"}
        interpretations = word, word[:-1] + flip[word[-1]], word[:-2] + flip[word[-2]] + word[-1]
        lower = set()
        for interpretation in interpretations:
            left, right = (match - lower for match in witnesses(interpretation, shorter))
            ambiguity = left | right
            lower |= ambiguity
            aliases += len(ambiguity)
            chosen = {"fixed": left or right, "active": left if len(left) >= len(right) else right}
            for mode, hits in chosen.items():
                if ambiguity:
                    queries[mode][2] += len(ambiguity) + 1
                unresolved = ambiguity - hits
                correct[mode] += not unresolved
                if unresolved:
                    queries[mode][3] += len(unresolved) + 1

    policies = {"receipt-1": {"correct": mapped, "wrong": aliases, "abstain": total - mapped - aliases,
                              "labels": total}}
    for mode, counts in queries.items():
        for budget in (2, 3):
            extras = counts[2] + (counts[3] if budget == 3 else 0)
            accepted = correct[mode] if budget == 2 else mapped
            policies[f"{mode}-{budget}"] = {
                "correct": accepted, "wrong": 0, "abstain": total - accepted, "labels": total + extras,
                "followup_nodes": (length + 1) * extras, "followup_edges": length * extras,
            }
    return {"pairs": total, "mapped": mapped, "shorter_aliases": aliases,
            "null_receipts": total - mapped - aliases, "policies": policies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    score = read(args.score)
    verify(args.score.read_bytes() == args.replay.read_bytes(), "enumeration did not replay byte-for-byte")
    verify(sorted(row["source_length"] for row in score["rows"]) == [7, 8, 9], "missing domain lengths")
    for row in score["rows"]:
        reference = expected(row["source_length"])
        verify(all(row[k] == v for k, v in reference.items()), "receipt-language calculation differs")
    print(json.dumps({"status": "COMPLETE", "lengths": [7, 8, 9], "cases": 888832, "replay_match": True,
                      "compressed_sha256": sha(args.score.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
