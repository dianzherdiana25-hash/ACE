"""Reconstruct weighted receipt outcomes using the evaluator path oracle."""

import argparse
import json
from pathlib import Path

from e13.contract import canonical_json, input_value

from .e14g_audit import verify
from .e14g_bank import sha
from .e14h_route import read
from .e14p_graph import minimum, paths
from .e14p_run import deterministic
from .e14r_run import CELLS, build, frozen, summary
from .e14r_worker import MODES


def check_block(block, row):
    artifact = block["artifact"]
    verify(row["artifact_sha256"] == sha(canonical_json(artifact)), "wrong lineage")
    original = tuple(artifact["word"])
    last = (*original[:-1], 3 - original[-1])
    penultimate = (*original[:-2], 3 - original[-2], original[-1])
    mapped = original, last, penultimate
    actual = (*mapped, tuple(3 - event for event in original), original[:-1])
    verify(len(row["resources"]) == 18 and set(row["modes"]) == set(MODES), "incomplete arm set")
    for meter in row["resources"]:
        verify(0 <= meter["cpu_us"] <= 1_000_000 and 0 < meter["rss_kib"] <= 131_072
               and 0 <= meter["wall_us"] <= 3_000_000, "worker resource cap exceeded")
    for mode, record in row["modes"].items():
        graph = record["graph"]
        input_value("G", graph)
        verify(graph["nodes"] <= 16 and len(graph["edges"]) <= 16, "graph over budget")
        routes = paths(graph)
        if mode == "passive":
            verify(graph == block["calibration"] and all(minimum(routes, word) is None for word in actual),
                   "passive query is not shared neutral calibration")
        else:
            expected = mapped if mode == "packed" else mapped[:1]
            costs = [len(original) + 1 + 4 * i for i in range(len(expected))]
            verify(dict(routes) == dict(zip(expected, costs, strict=True)) and len(routes) == len(expected),
                   "diagnostic graph does not implement declared receipts")
        for name, word in zip(CELLS, actual, strict=True):
            label = minimum(routes, word)
            if mode == "passive":
                accepted = [original] if label is None else []
            else:
                compatible = [w for w in mapped if label is not None and minimum(routes, w) == label]
                accepted = compatible if len(compatible) == 1 else []
            verify(len(accepted) <= 1, "ambiguous receipt")
            evaluations = [(minimum(paths(raw), accepted[0]), minimum(paths(raw), word))
                           for raw in block["probes"]] if accepted else []
            expected = {"label": label, "selected": [list(w) for w in accepted],
                        "covered": len(evaluations), "errors": sum(x != y for x, y in evaluations),
                        "false_positive": sum(x is not None and y is None for x, y in evaluations)}
            verify(record["outcomes"][name] == expected, "incorrect prediction or receipt")
    main = row["modes"]["packed"]["outcomes"]["identity"]
    verify(row["total"] == len(block["probes"]) and row["correct"] == main["covered"] - main["errors"]
           and row["status"] == "scored", "incorrect ledger summary")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score", type=Path)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    bank, digest, _ = frozen()
    score, replay = read(args.score), read(args.replay)
    verify(canonical_json(bank) == canonical_json(build()), "bank or artifact reconstruction mismatch")
    verify(score["bank_sha256"] == digest and deterministic(score) == deterministic(replay), "replay mismatch")
    pending = {str(block["index"]): block for block in bank["blocks"]}
    for row in score["rows"]:
        check_block(pending.pop(row["episode"]), row)
    verify(not pending and score["status"] == "completed" and score["summary"] == summary(score["rows"]),
           "incomplete or inconsistent report")
    print(json.dumps({"status": "COMPLETE", "lineages": len(bank["blocks"]), "replay_match": True,
                      "deterministic_sha256": sha(canonical_json(deterministic(score)))}, sort_keys=True))


if __name__ == "__main__":
    main()
