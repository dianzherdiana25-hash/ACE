#!/usr/bin/env python3
"""Separate reference replay of public reasoning cells, not independent scientific custody."""
from __future__ import annotations

import argparse
import json
import operator
from pathlib import Path


def interpret(tree, env):
    if "var" in tree:
        return env[tree["var"]]
    if "const" in tree:
        return tree["const"]
    fn = {"add": operator.add, "sub": operator.sub, "mul": operator.mul,
          "eq": operator.eq, "lt": operator.lt}[tree["op"]]
    return fn(*(interpret(c, env) for c in tree["args"]))


def truth(family, env):
    x, y = env["x"], env["y"]
    return {"add": lambda: sum((x, y)), "subtract": lambda: x + (-y),
            "multiply": lambda: x * y, "double_sum": lambda: x + y + x + y,
            "square_shift": lambda: y + x ** 2, "equality": lambda: x - y == 0,
            "less": lambda: y - x > 0, "sum_equals_two": lambda: x + y - 2 == 0}[family]()


def same(a, b):
    return type(a) is type(b) and a == b


def audit(data):
    assert len(data["cells"]) == 24
    total = {k: 0 for k in ("A_internal", "F_same_fresh_solver", "B_SYNTHETIC_FIXTURE")}
    score_cells = 0
    for cell in data["cells"]:
        assert [len(cell[k]) for k in ("train", "validation", "terminal")] == [12, 12, 24]
        keys = [tuple(sorted(row["inputs"].items())) for k in ("train", "validation", "terminal") for row in cell[k]]
        assert len(keys) == len(set(keys))
        for split in ("train", "validation", "terminal"):
            for row in cell[split]:
                assert same(row["output"], truth(cell["family"], row["inputs"]))
        for arm in total:
            record = cell[arm]
            decision = record["decision"]
            program = decision["program"]
            score = record["terminal"]
            if program is None:
                assert decision["status"] == "ABSTAIN"
                assert score["predictions"] == [] and score["correct"] == 0 and score["abstained"] == 24
            else:
                assert decision["status"] == "STAGED_EMPIRICAL"
                for row in cell["train"] + cell["validation"]:
                    assert same(interpret(program, row["inputs"]), row["output"])
                preds = [interpret(program, row["inputs"]) for row in cell["terminal"]]
                assert all(same(a, b) for a, b in zip(preds, score["predictions"]))
                assert len(score["predictions"]) == 24
                assert score["correct"] == sum(same(p, r["output"]) for p, r in zip(preds, cell["terminal"]))
            total[arm] += score["correct"]
            score_cells += 1
    assert total["A_internal"] == data["summary"]["A_correct"]
    assert total["F_same_fresh_solver"] == data["summary"]["F_correct"]
    assert total["B_SYNTHETIC_FIXTURE"] == data["summary"]["B_fixture_correct"]
    assert data["summary"]["external_model_calls"] == 0
    assert data["summary"]["scientific_status"] == "NOT_ASSESSED"
    assert data["summary"]["release_gate"] == "BLOCK_RELEASE"
    assert data["hidden_shift"]["false_admission"]
    assert data["hidden_shift"]["terminal"]["correct"] == 0
    return {"status": "REFERENCE_REPLAY_PASS_PUBLIC_ONLY", "score_cells": score_cells,
            "correct_by_arm": total, "independent_scientific_validation": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("artifact")
    args = p.parse_args()
    print(json.dumps(audit(json.loads(Path(args.artifact).read_text())), indent=2))


if __name__ == "__main__":
    main()
