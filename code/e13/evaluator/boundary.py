"""Public representation diagnostics, separate from pilot and selection."""

import json
from itertools import combinations, pairwise

from ..contract import canonical_json
from ..dsl import Fuel, compile_ast, predict
from .bank import _chain


def _periodic_descent(values):
    descents = 0
    output = []
    for left, right in pairwise(values):
        event = left > right
        descents += event
        output.append(int(event and descents % 5 == 0))
    return tuple(output)


def _exact_five_edges(chain):
    return 5 if len(chain["edges"]) == 5 else None


def _symbol_cases():
    for left, right in combinations(range(5), 2):
        continuation = list(range(9, 9 - (5 - right), -1))
        # All prefixes end with the same symbol, so the suffix events coincide.
        inputs = [list(range(10 + prefix, 9, -1)) + continuation
                  for prefix in (left, right)]
        yield {"prefix_counts": [left, right], "suffix_length": len(continuation),
               "inputs": inputs, "expected": [_periodic_descent(value) for value in inputs]}


def _graph_cases():
    for left, right in combinations(range(1, 6), 2):
        suffix_length = 5 - right
        # All nonempty prefixes use the same previous label. Every prefix
        # reaches acceptance with a continuation, so rejection cannot store it.
        inputs = [_chain([0] * (prefix + suffix_length)) for prefix in (left, right)]
        yield {"prefix_counts": [left, right], "suffix_length": suffix_length,
               "inputs": inputs, "expected": [_exact_five_edges(value) for value in inputs]}


def boundary_report():
    programs = (
        ("S", {"op": "symbol_extension", "table": [
            [(state, 0), (state, 0), ((state + 1) % 5, int(state == 4))]
            for state in range(5)
        ]}, _symbol_cases()),
        ("G", {"op": "graph_extension",
               "table": [[state + 1] * 3 for state in range(5)] + [[-1] * 3],
               "accept": [0, 0, 0, 0, 0, 1]}, _graph_cases()),
    )
    reports = []
    for family, ast, cases in programs:
        program = compile_ast(canonical_json({"family": family, "ast": ast}), allow_extension=True)
        witnesses = []
        for case in cases:
            left, right = case["expected"]
            size = case["suffix_length"]
            distinguished = left[-size:] != right[-size:] if family == "S" else (left is None) != (right is None)
            predictions = [predict(program.ast, canonical_json(value), Fuel(2_000),
                                   allow_extension=True) for value in case["inputs"]]
            if not distinguished or predictions != case["expected"]:
                raise ValueError("diagnostic witness failed")
            witnesses.append(case)
        reports.append({"family": family, "closed_state_cap": 4, "distinct_live_prefixes": 5,
                        "extension_states": len(program.table), "ast_sha256": program.sha256,
                        "ast": json.loads(program.ast), "witnesses": witnesses})
    return {"mode": "development", "purpose": "hand-authored representation diagnostic",
            "families": reports}


def main():
    print(json.dumps(boundary_report(), separators=(",", ":")))


if __name__ == "__main__":
    main()
