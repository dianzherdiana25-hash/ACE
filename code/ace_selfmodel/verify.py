"""Independent verifier for Fase 4 Self-Model & Metacognition report."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

from .core import PHENOMENAL_CONSCIOUSNESS_STATUS
from .metacognition import compute_calibration_metrics


def verify_report(data: dict) -> None:
    if data.get("schema") != "ace.selfmodel.v1":
        raise ValueError("invalid schema")
    if data.get("scientific_decision") != "NOT_ASSESSED":
        raise ValueError("scientific_decision must be NOT_ASSESSED")
    if data.get("oaie_established") is not False:
        raise ValueError("oaie_established must be False")
    ep = data.get("epistemic_statuses", {})
    if ep.get("PHENOMENAL_CONSCIOUSNESS") != PHENOMENAL_CONSCIOUSNESS_STATUS:
        raise ValueError("phenomenal consciousness must remain PHENOMENAL_CONSCIOUSNESS_UNKNOWN")

    trials = data.get("trials")
    if not isinstance(trials, list) or len(trials) != 60:
        raise ValueError("expected 60 trials")

    # Recompute calibration metrics directly from raw trial records
    rec_self = [
        (t["m_selfmodel"]["p_success"], t["actual_success"], t["m_selfmodel"]["recommendation"] == "EXECUTE")
        for t in trials
    ]
    recomp = compute_calibration_metrics(rec_self)
    if recomp != data["calibration_comparison"]["M_selfmodel"]:
        raise ValueError("M_selfmodel calibration metrics do not match raw trials")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path", type=Path)
    args = parser.parse_args(argv)
    raw = args.report_path.read_bytes()
    if args.report_path.suffix == ".gz":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8"))
    try:
        verify_report(data)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: Fase 4 verifier ok. all_gates_pass={data['all_gates_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
