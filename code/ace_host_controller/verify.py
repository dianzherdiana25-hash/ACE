"""Independent verification harness for ACE Host Controller governance artifacts.

Verifies schema, fail-closed release gates, lineage integrity, and exposure ledger digests.
Accepts both positional and --artifact arguments, supporting gzip decompression.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


def verify_governance_report(report: dict[str, Any]) -> tuple[bool, str]:
    """Verify cryptographic invariants and fail-closed gates in host controller report."""
    if report.get("schema") != "ace.host_controller_governance.v1":
        return False, f"Invalid schema: {report.get('schema')}"

    # Fail-closed invariants
    if report.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {report.get('release_gate')}"
    if report.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {report.get('scientific_status')}"
    if report.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # Lineage verification
    lineage = report.get("lineage")
    if not isinstance(lineage, dict):
        return False, "Missing lineage dictionary"
    nodes = lineage.get("nodes", {})
    recorded_lineage_digest = lineage.get("lineage_digest")
    recomputed_lineage_digest = hashlib.sha256(
        json.dumps(nodes, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    if recorded_lineage_digest != recomputed_lineage_digest:
        return False, f"Lineage digest mismatch: {recorded_lineage_digest} != {recomputed_lineage_digest}"

    # Exposure ledger verification
    ledger = report.get("exposure_ledger")
    if not isinstance(ledger, dict):
        return False, "Missing exposure_ledger dictionary"
    records = ledger.get("records", [])
    recorded_ledger_digest = ledger.get("ledger_digest")
    recomputed_ledger_digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    if recorded_ledger_digest != recomputed_ledger_digest:
        return False, f"Exposure ledger digest mismatch: {recorded_ledger_digest} != {recomputed_ledger_digest}"

    # Evaluator manifest verification
    manifest = report.get("manifest")
    if not isinstance(manifest, dict):
        return False, "Missing manifest dictionary"
    if "manifest_digest" not in manifest or "holdout_bank_hashes" not in manifest:
        return False, "Incomplete evaluator manifest"

    return True, "All host controller governance invariants verified successfully"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ACE Host Controller governance report")
    parser.add_argument("report", nargs="?", default=None, help="Path to report JSON (.json or .json.gz)")
    parser.add_argument("--artifact", dest="artifact", default=None, help="Path to report JSON (.json or .json.gz)")
    args = parser.parse_args(argv)

    target_path = args.artifact or args.report
    if not target_path:
        print("ERROR: Must provide either report path or --artifact <path>", file=sys.stderr)
        return 1

    path = Path(target_path)
    if not path.is_file():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return 1

    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                report = json.load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                report = json.load(f)
    except Exception as exc:
        print(f"ERROR: Failed to read/parse {path}: {exc}", file=sys.stderr)
        return 1

    passed, msg = verify_governance_report(report)
    if not passed:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1

    print(f"PASS: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
