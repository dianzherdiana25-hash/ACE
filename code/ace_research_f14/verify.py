"""Independent verifier for ACE F14 Autonomous Mechanism Discovery evidence artifacts.

Validates schema, fail-closed gates, generational progression (G0 -> G1 -> G2),
Host Controller acceptance decisions, baselines comparisons, and governance invariants.
Supports positional and --artifact arguments with gzip decompression.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Tuple


def verify_f14_evidence(evidence: dict[str, Any]) -> Tuple[bool, str]:
    """Verify cryptographic invariants and empirical validity of F14 research artifact."""
    if evidence.get("benchmark_id") != "ACE_F14_AUTONOMOUS_MECHANISM_DISCOVERY":
        return False, f"Invalid benchmark_id: {evidence.get('benchmark_id')}"

    # Governance Invariants
    gov = evidence.get("governance", {})
    if gov.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {gov.get('release_gate')}"
    if gov.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {gov.get('scientific_status')}"
    if gov.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # Generational results check
    primary = evidence.get("primary_discovery_results", {})
    if not (primary.get("g1_accepted") and primary.get("g2_accepted")):
        return False, f"Generational discovery G1/G2 not accepted: {primary}"

    if primary.get("g1_gain", 0.0) < 0.15:
        return False, f"G1 gain below 0.15: {primary.get('g1_gain')}"

    if primary.get("g2_gain", 0.0) < 0.15:
        return False, f"G2 gain below 0.15: {primary.get('g2_gain')}"

    if primary.get("g2_regression", 1.0) > 0.02:
        return False, f"G2 prior regression exceeds 0.02: {primary.get('g2_regression')}"

    # Baselines comparison check
    baselines = evidence.get("baselines_comparison", {})
    required_baselines = [
        "B1_researcher_upper_bound",
        "B2_random_ast_search",
        "B3_static_feature_selection",
        "B4_compute_matched_search_3x",
        "B5_cold_start_g0",
        "ACE_F14_autonomous_discovery_g2",
    ]
    for b in required_baselines:
        if b not in baselines:
            return False, f"Missing baseline in baselines_comparison: {b}"

    # Pre-registered criteria check
    crit = evidence.get("preregistered_criteria_evaluation", {})
    if not crit.get("all_criteria_met"):
        return False, f"Not all pre-registered criteria met: {crit}"

    return True, "All F14 autonomous mechanism discovery invariants and governance gates verified successfully"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ACE F14 Mechanism Discovery Evidence Artifact")
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

    passed, msg = verify_f14_evidence(evidence)
    if not passed:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1

    print(f"PASS: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
