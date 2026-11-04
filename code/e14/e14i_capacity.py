"""Post-score, label-blind lower bound on guaranteed natural length diagnosis."""

import argparse
import json
from pathlib import Path

from e13.contract import MAX_TOKENS

from .e14h_route import read
from .e14i_run import histogram

MAX_EVENTS = {"S": MAX_TOKENS - 1, "G": 14}  # A 16-node single chain has 14 adjacent-edge events.


def inspect(report):
    cases = []
    for row in report["rows"]:
        if not row["block"].startswith("natural:") or any(c["fit_matches"] != 32 for c in row["classes"].values()):
            continue
        classes = row["classes"]
        cap = MAX_EVENTS[row["family"]]
        counts = {length: c["candidates"] for length, c in classes.items()}
        max_windows = {length: cap - int(length) + 1 for length in classes}
        # Along the all-blank answer path, each query eliminates at most this
        # many words per class. Guaranteed diagnosis must exhaust one class.
        lower_bound = min((n + max_windows[length] - 1) // max_windows[length]
                          for length, n in counts.items())
        supports = [(histogram(a).keys(), histogram(b).keys())
                    for a, b in zip(classes["5"]["histograms"], classes["6"]["histograms"], strict=True)]
        bought = row["query_cross"]
        cases.append({"family": row["family"], "length": int(row["episode"]), "block": row["block"],
                      "demo_candidates": counts, "max_windows_per_input": max_windows,
                      "queries_required_for_guarantee_at_least": lower_bound,
                      "pool_has_disjoint_support": any(not (a & b) for a, b in supports),
                      "queried_disjoint_support": bought is not None and not (supports[bought][0] & supports[bought][1])})
    cases.sort(key=lambda row: (row["family"], row["length"], row["block"]))
    return {"natural_ambiguous_worlds": len(cases),
            "single_label_guarantee_impossible": sum(row["queries_required_for_guarantee_at_least"] > 1 for row in cases),
            "pool_has_disjoint_support": sum(row["pool_has_disjoint_support"] for row in cases),
            "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(read(args.result)), sort_keys=True))


if __name__ == "__main__":
    main()
