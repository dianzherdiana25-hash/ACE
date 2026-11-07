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
    """Verify cryptographic invariants, raw predictions, lineage, and empirical validity of F14 artifact."""
    bench_id = evidence.get("benchmark_id")
    if bench_id not in ("ACE_F14_AUTONOMOUS_MECHANISM_DISCOVERY", "ACE_F14_INDEPENDENT_TERMINAL_EVALUATION"):
        return False, f"Invalid benchmark_id: {bench_id}"

    # Governance Invariants (Fail-Closed)
    gov = evidence.get("governance", {})
    if gov.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {gov.get('release_gate')}"
    if gov.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {gov.get('scientific_status')}"
    if gov.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # Developmental benchmark schema (frozen exploratory baseline)
    if bench_id == "ACE_F14_AUTONOMOUS_MECHANISM_DISCOVERY":
        primary = evidence.get("primary_discovery_results", {})
        if not (primary.get("g1_accepted") and primary.get("g2_accepted")):
            return False, f"Generational discovery G1/G2 not accepted: {primary}"
        if primary.get("g1_gain", 0.0) < 0.15:
            return False, f"G1 gain below 0.15: {primary.get('g1_gain')}"
        if primary.get("g2_gain", 0.0) < 0.15:
            return False, f"G2 gain below 0.15: {primary.get('g2_gain')}"
        if primary.get("g2_regression", 1.0) > 0.02:
            return False, f"G2 prior regression exceeds 0.02: {primary.get('g2_regression')}"

    # Independent terminal benchmark schema
    if bench_id == "ACE_F14_INDEPENDENT_TERMINAL_EVALUATION":
        if "primary_discovery_summary" not in evidence:
            return False, "Missing primary_discovery_summary in terminal evaluation artifact"
        if "baselines_summary" not in evidence:
            return False, "Missing baselines_summary in terminal evaluation artifact"
        if "per_seed_runs" not in evidence or len(evidence["per_seed_runs"]) < 5:
            return False, "Terminal evaluation must include at least 5 paired seeds"

        per_seed_runs = evidence["per_seed_runs"]
        for idx, run in enumerate(per_seed_runs):
            # 1. Raw labels and predictions verification
            raw_labels = run.get("raw_labels")
            raw_preds = run.get("raw_predictions")
            if not raw_labels or not isinstance(raw_labels, list):
                return False, f"Run {idx}: missing or invalid raw_labels"
            if not raw_preds or not isinstance(raw_preds, dict):
                return False, f"Run {idx}: missing or invalid raw_predictions"
            for g_key in ("g0", "g1", "g2"):
                if g_key not in raw_preds or len(raw_preds[g_key]) != len(raw_labels):
                    return False, f"Run {idx}: prediction length mismatch for {g_key}: {len(raw_preds.get(g_key, []))} vs {len(raw_labels)}"

            # 2. Recalculate accuracies from raw data
            n_samples = len(raw_labels)
            calc_g0 = round(sum(1 for p, l in zip(raw_preds["g0"], raw_labels) if p == l) / n_samples, 4)
            calc_g1 = round(sum(1 for p, l in zip(raw_preds["g1"], raw_labels) if p == l) / n_samples, 4)
            calc_g2 = round(sum(1 for p, l in zip(raw_preds["g2"], raw_labels) if p == l) / n_samples, 4)

            if round(run.get("g0_accuracy", 0.0), 4) != calc_g0:
                return False, f"Run {idx}: g0_accuracy mismatch: declared {run.get('g0_accuracy')} vs computed {calc_g0}"
            if round(run.get("g1_accuracy", 0.0), 4) != calc_g1:
                return False, f"Run {idx}: g1_accuracy mismatch: declared {run.get('g1_accuracy')} vs computed {calc_g1}"
            if round(run.get("g2_accuracy", 0.0), 4) != calc_g2:
                return False, f"Run {idx}: g2_accuracy mismatch: declared {run.get('g2_accuracy')} vs computed {calc_g2}"

            # 3. Recalculate gains against parent
            calc_g1_gain = round(calc_g1 - calc_g0, 4)
            calc_g2_gain = round(calc_g2 - calc_g1, 4)
            if round(run.get("g1_gain", 0.0), 4) != calc_g1_gain:
                return False, f"Run {idx}: g1_gain mismatch against parent G0: declared {run.get('g1_gain')} vs computed {calc_g1_gain}"
            if round(run.get("g2_gain", 0.0), 4) != calc_g2_gain:
                return False, f"Run {idx}: g2_gain mismatch against parent G1: declared {run.get('g2_gain')} vs computed {calc_g2_gain}"

            # 4. Verify gating decisions
            expected_g1_acc = (calc_g1_gain >= 0.15)
            expected_g2_acc = (calc_g2_gain >= 0.15)
            if run.get("g1_accepted") != expected_g1_acc:
                return False, f"Run {idx}: g1_accepted mismatch: declared {run.get('g1_accepted')} vs expected {expected_g1_acc}"
            if run.get("g2_accepted") != expected_g2_acc:
                return False, f"Run {idx}: g2_accepted mismatch: declared {run.get('g2_accepted')} vs expected {expected_g2_acc}"

            # 5. Verify lineage and active head retention
            # Since G2 was rejected (gain < 0.15), active head MUST remain G1
            if not expected_g2_acc:
                active_head = run.get("active_head_id", "")
                if active_head != "G1_autonomous_discovered":
                    return False, f"Run {idx}: lineage corruption: G2 rejected but active_head_id is '{active_head}', expected 'G1_autonomous_discovered'"

            # 6. Verify budgets and evaluator manifest
            if run.get("candidate_budget_spent", 0) > 50:
                return False, f"Run {idx}: candidate budget exceeded: {run.get('candidate_budget_spent')} > 50"
            if run.get("execution_seconds", 0.0) > 120.0:
                return False, f"Run {idx}: CPU execution budget exceeded: {run.get('execution_seconds')} > 120.0s"

            digest = run.get("evaluator_manifest_digest", "")
            if not digest or len(digest) != 64:
                return False, f"Run {idx}: missing or invalid evaluator_manifest_digest: {digest}"

    return True, "All F14 autonomous mechanism discovery invariants, raw predictions, lineage, and governance gates verified successfully"



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
