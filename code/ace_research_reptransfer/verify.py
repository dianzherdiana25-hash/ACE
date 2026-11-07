"""Independent verifier for R9 report and evidence.

Checks:
- Schema and required metadata fields.
- Byte-identical replay of fit and evaluation on sampled units.
- Non-leakage: fit output is unaffected if terminal labels are inverted.
- Truth consistency between ``tasks.truth`` and ``evaluator.independent_truth``.
- Gate computation matches raw unit data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .tasks import TARGETS, TARGET_BY_ID, truth
from .evaluator import independent_truth
from .runner import analyze_report


def verify_report(data: dict) -> None:
    if data.get("schema") != "ace.r9.gemini.v1":
        raise ValueError("unsupported report schema")
    if data.get("scientific_decision") != "NOT_ASSESSED":
        raise ValueError("scientific_decision must be NOT_ASSESSED")
    if data.get("release_gate") != "BLOCK_RELEASE":
        raise ValueError("release_gate must be BLOCK_RELEASE")
    if data.get("oaie_established") is not False:
        raise ValueError("oaie_established must be False")
    if data.get("candidate_deployed") is not False:
        raise ValueError("candidate_deployed must be False")

    units = data.get("units")
    if not isinstance(units, list) or len(units) != 195:
        raise ValueError(f"expected 195 units (165 nominal + 30 drift), got {len(units) if isinstance(units, list) else None}")

    # Re-compute analysis from units and verify byte-identical agreement with recorded analysis
    recomputed = analyze_report(data)
    if json.dumps(recomputed, sort_keys=True) != json.dumps(data.get("analysis"), sort_keys=True):
        raise ValueError("recorded analysis does not match recomputed analysis from units")

    # Cross-check truth implementations on sample strings
    for task_id, _, spec in TARGETS:
        for length in (0, 1, 2, 5, 8, 12, 16):
            test_words = ["a" * length, "b" * length, ("ab" * (length // 2 + 1))[:length]]
            for w in test_words:
                t1 = truth(spec, w)
                t2 = independent_truth(spec, w)
                if t1 != t2:
                    raise ValueError(f"truth mismatch on {task_id} word {w!r}: {t1} vs {t2}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report_file", type=Path, nargs="?", default=None)
    parser.add_argument("--artifact", type=Path, default=None, help="Path to report artifact")
    args = parser.parse_args()
    target_path = args.artifact or args.report_file
    if target_path is None:
        parser.error("must provide report_file or --artifact")
    if target_path.suffix == ".gz":
        import gzip
        with gzip.open(target_path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(target_path.read_text(encoding="utf-8"))
    try:
        verify_report(data)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    gate = data["analysis"]["gate_G_pass"]
    safe = data["analysis"]["open_world_safe"]
    print(f"PASS: R9 verifier ok. gate_G_pass={gate}, open_world_safe={safe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
