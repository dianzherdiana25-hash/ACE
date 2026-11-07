"""Runner and evidence artifact generator for F10 Hypothesis Synthesis."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
import tempfile

from .evaluator import run_full_comparative_benchmark


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/hypgen/f10_hypothesis_synthesis_v1.json.gz"))
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="ace_hypgen_") as tmp_dir:
        workspace = Path(tmp_dir)
        summary = run_full_comparative_benchmark(workspace=workspace, seed=args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw_json = json.dumps(summary, sort_keys=True, indent=2).encode("utf-8")
    with gzip.open(args.output, "wb") as f:
        f.write(raw_json)

    print(f"PASS: F10 comparative benchmark evidence generated at {args.output}")
    print(f"Decision: {summary['f10_decision']} (delta_vs_random: {summary['delta_vs_random']}, threshold_passed: {summary['threshold_passed']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
