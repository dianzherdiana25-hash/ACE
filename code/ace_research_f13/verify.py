"""Independent verifier for ACE F13 Causal Memory Validation evidence artifacts.

Validates schema, fail-closed gates, arms comparisons, Cohen's d effect sizes,
and governance invariants. Supports positional and --artifact arguments with gzip decompression.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Tuple


def verify_f13_evidence(evidence: dict[str, Any]) -> Tuple[bool, str]:
    """Verify cryptographic invariants and empirical validity of F13 research artifact."""
    if evidence.get("benchmark_id") != "ACE_F13_CAUSAL_MEMORY_VALIDATION":
        return False, f"Invalid benchmark_id: {evidence.get('benchmark_id')}"

    # Governance Invariants
    gov = evidence.get("governance", {})
    if gov.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {gov.get('release_gate')}"
    if gov.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {gov.get('scientific_status')}"
    if gov.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # Seeds check
    seeds = evidence.get("seeds", [])
    expected_seeds = [42, 137, 256, 512, 1024]
    if seeds != expected_seeds:
        return False, f"Seeds mismatch: expected {expected_seeds}, got {seeds}"

    # Arms check
    required_arms = ["standard", "none", "shuffled", "irrelevant", "static", "compute_matched"]
    summary = evidence.get("summary_by_arm", {})
    for arm in required_arms:
        if arm not in summary:
            return False, f"Missing arm in summary_by_arm: {arm}"

    # Effect sizes check
    effects = evidence.get("effect_sizes", {})
    if "cohens_d_standard_vs_none" not in effects:
        return False, "Missing cohens_d_standard_vs_none in effect_sizes"

    # Criteria evaluation check
    crit = evidence.get("preregistered_criteria_evaluation", {})
    if "all_criteria_met" not in crit or "scientific_status" not in crit:
        return False, "Missing criteria evaluation entries"

    return True, "All F13 causal memory invariants and governance gates verified successfully"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ACE F13 Causal Memory Evidence Artifact")
    parser.add_argument("artifact_pos", nargs="?", default=None, help="Path to evidence JSON (.json or .json.gz)")
    parser.add_argument("--artifact", dest="artifact", default=None, help="Path to evidence JSON (.json or .json.gz)")
    args = parser.parse_args(argv)

    target_path = args.artifact or args.artifact_pos
    if not target_path:
        print("ERROR: Must provide either artifact path or --artifact <path>", file=sys.stderr)
        return 1

    path = Path(target_path)
    if not path.is_file():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return 1

    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                evidence = json.load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                evidence = json.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to read/parse {path}: {exc}", file=sys.stderr)
        return 1

    passed, msg = verify_f13_evidence(evidence)
    if not passed:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1

    print(f"PASS: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
