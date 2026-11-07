"""Independent verifier for ACE F12 Causal Autonomous Research evidence artifacts.

Validates schema, fail-closed gates, arms comparisons, generational growth,
Host Controller governance receipts, and runtime implementation digests.
Supports positional and --artifact arguments with gzip decompression.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any

from ace_host_controller.verify import verify_governance_report


def verify_f12_evidence(evidence: dict[str, Any]) -> tuple[bool, str]:
    """Verify cryptographic invariants and empirical validity of F12 research artifact."""
    if evidence.get("schema") != "ace.f12_causal_research.v1":
        return False, f"Invalid schema: {evidence.get('schema')}"

    # Invariants
    if evidence.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {evidence.get('release_gate')}"
    if evidence.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {evidence.get('scientific_status')}"
    if evidence.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # Runtime audit check
    runtime_audit = evidence.get("runtime_audit", {})
    if not runtime_audit.get("runtime_implementation_digest"):
        return False, "Missing runtime_implementation_digest in runtime_audit"

    # Arms comparison check
    arms = evidence.get("arms_comparison", {})
    required_arms = [
        "arm1_fixed",
        "arm2_random",
        "arm3_passive",
        "arm4_active_f12",
        "arm5_extra_compute",
        "arm6a_no_memory",
        "arm6b_shuffled_memory",
    ]
    for arm in required_arms:
        if arm not in arms:
            return False, f"Missing required arm in arms_comparison: {arm}"

    # Generational growth check
    gen = evidence.get("generational_growth", {})
    summary = gen.get("summary", {})
    if not (summary.get("g1_accepted") and summary.get("g2_accepted")):
        return False, f"Generational growth G1/G2 not accepted: {summary}"

    # Verify nested host controller governance report
    gov_report = gen.get("governance_report")
    if not isinstance(gov_report, dict):
        return False, "Missing governance_report in generational_growth"

    gov_ok, gov_msg = verify_governance_report(gov_report)
    if not gov_ok:
        return False, f"Nested Host Controller governance verification failed: {gov_msg}"

    return True, "All F12 causal research invariants and governance gates verified successfully"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ACE F12 Causal Research Evidence Artifact")
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

    passed, msg = verify_f12_evidence(evidence)
    if not passed:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1

    print(f"PASS: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
