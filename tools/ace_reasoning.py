#!/usr/bin/env python3
"""Opt-in offline reasoning CLI, using a separate workspace; does not start ACE daemon."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_cognition.reasoning import Problem, ReasoningMemory, solve


def read_bounded(path):
    data = Path(path).read_bytes()
    if len(data) > 65536:
        raise ValueError("input JSON exceeds 64 KiB")
    return json.loads(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--problem", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--advice", help="JSON list of <=4 closed IR trees; never Python code")
    args = p.parse_args()
    try:
        problem = Problem.from_data(read_bounded(args.problem))
        advice = read_bounded(args.advice) if args.advice else []
        with ReasoningMemory(args.workspace) as memory:
            result = solve(problem, memory=memory, advice=advice)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"status": "INVALID_INPUT_OR_WORKSPACE", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
