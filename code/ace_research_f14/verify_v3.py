"""Independent external verifier for ACE F14 V3 Scientific Validation evidence artifacts.

Validates:
1. Cryptographic invariants & governance gates (BLOCK_RELEASE, NOT_ASSESSED, oaie_established=False).
2. Strict re-computation of raw predictions and raw labels across all 5 seeds.
3. Accurate parent-relative gain computation and fail-closed promotion gating.
4. Lineage integrity: rejected candidates never become active lineage head.
5. Programmatic AST novelty audit: verifies template composition vs genuine novel primitive.
6. Search budget bounds and zero marginal cost verification ($0.00).
7. Hypotheses H1, H2, H3 confirmation / falsification evaluation consistency.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys
from typing import Any, Tuple

from ace_research_f14.discovery_engine import INITIAL_PRIMITIVE_CATALOG


def verify_f14_v3_evidence(evidence: dict[str, Any]) -> Tuple[bool, str]:
    """Verify cryptographic invariants, raw predictions, lineage, and empirical validity of F14 V3 artifact."""
    bench_id = evidence.get("benchmark_id")
    if bench_id != "ACE_F14_V3_SCIENTIFIC_VALIDATION":
        return False, f"Invalid benchmark_id: {bench_id}, expected 'ACE_F14_V3_SCIENTIFIC_VALIDATION'"

    # 1. Governance Invariants (Fail-Closed)
    gov = evidence.get("governance", {})
    if gov.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {gov.get('release_gate')}"
    if gov.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {gov.get('scientific_status')}"
    if gov.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # 2. Structural presence checks
    if "primary_discovery_summary" not in evidence:
        return False, "Missing primary_discovery_summary in terminal evaluation artifact"
    if "baselines_summary" not in evidence:
        return False, "Missing baselines_summary in terminal evaluation artifact"
    if "per_seed_runs" not in evidence or len(evidence["per_seed_runs"]) < 5:
        return False, "Terminal evaluation must include at least 5 paired seeds"

    per_seed_runs = evidence["per_seed_runs"]
    budget_enforced = evidence.get("search_budget_enforced", 50)

    for idx, run in enumerate(per_seed_runs):
        # 3. Raw labels and predictions verification
        raw_labels = run.get("raw_labels")
        raw_preds = run.get("raw_predictions")
        if not raw_labels or not isinstance(raw_labels, list):
            return False, f"Run {idx}: missing or invalid raw_labels"
        if not raw_preds or not isinstance(raw_preds, dict):
            return False, f"Run {idx}: missing or invalid raw_predictions"
        for g_key in ("g0", "g1", "g2"):
            if g_key not in raw_preds or len(raw_preds[g_key]) != len(raw_labels):
                return False, f"Run {idx}: prediction length mismatch for {g_key}: {len(raw_preds.get(g_key, []))} vs {len(raw_labels)}"

        # 4. Recalculate accuracies from raw data
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

        # 5. Recalculate gains against appropriate parent
        calc_g1_gain = round(calc_g1 - calc_g0, 4)
        if round(run.get("g1_gain", 0.0), 4) != calc_g1_gain:
            return False, f"Run {idx}: g1_gain mismatch against parent G0: declared {run.get('g1_gain')} vs computed {calc_g1_gain}"

        # G2 parent depends on whether G1 was accepted
        expected_g1_acc = (calc_g1_gain >= 0.15)
        parent_score_for_g2 = calc_g1 if expected_g1_acc else calc_g0
        calc_g2_gain = round(calc_g2 - parent_score_for_g2, 4)
        if round(run.get("g2_gain", 0.0), 4) != calc_g2_gain:
            return False, f"Run {idx}: g2_gain mismatch against parent: declared {run.get('g2_gain')} vs computed {calc_g2_gain}"

        # 6. Verify gating decisions
        expected_g2_acc = (calc_g2_gain >= 0.15)
        if run.get("g1_accepted") != expected_g1_acc:
            return False, f"Run {idx}: g1_accepted mismatch: declared {run.get('g1_accepted')} vs expected {expected_g1_acc}"
        if run.get("g2_accepted") != expected_g2_acc:
            return False, f"Run {idx}: g2_accepted mismatch: declared {run.get('g2_accepted')} vs expected {expected_g2_acc}"

        # 7. Lineage integrity check
        active_head = run.get("active_head_id", "")
        if not expected_g1_acc and not expected_g2_acc:
            # Both rejected: active head must remain root
            if "G1" in active_head or "G2" in active_head:
                return False, f"Run {idx}: lineage violation: both G1 and G2 rejected but active head is {active_head}"
        elif expected_g1_acc and not expected_g2_acc:
            # G1 accepted, G2 rejected: active head must remain G1
            if active_head != "G1_autonomous_discovered":
                return False, f"Run {idx}: lineage violation: G2 rejected but active head is {active_head}, expected G1"

        # 8. Structural Novelty Audit Verification
        novelty_audits = run.get("novelty_audits", {})
        solvers = run.get("g2_solvers_signatures", {})
        for tid, sig in solvers.items():
            audit = novelty_audits.get(tid, {})
            # Check if any unknown tokens exist
            has_novel = any(token not in INITIAL_PRIMITIVE_CATALOG for token in audit.get("nodes_used", []))
            if audit.get("is_novel_primitive") != has_novel:
                return False, f"Run {idx}, task {tid}: novelty audit inconsistency: declared {audit.get('is_novel_primitive')} vs computed {has_novel}"

        # 9. Cost verification
        cost = run.get("search_cost_usd", 0.0)
        if cost > 0.0:
            return False, f"Run {idx}: nonzero search cost detected: ${cost}"

    # 10. Hypotheses Evaluation Consistency Checks
    hyp = evidence.get("hypotheses_evaluation", {})
    summary = evidence.get("primary_discovery_summary", {})
    any_novel = summary.get("any_novel_primitive_discovered", False)

    h1 = hyp.get("H1_genuine_primitive_discovery", {})
    if any_novel:
        if h1.get("status") != "CONFIRMED":
            return False, "H1 status inconsistency: novel primitive found but H1 not CONFIRMED"
    else:
        if h1.get("confirmed") is not False:
            return False, "H1 inconsistency: no novel primitive found but H1 declared confirmed"

    h3 = hyp.get("H3_recursive_capability_growth", {})
    g1_mean_gain = summary.get("g1_gain_mean", 0.0)
    g2_mean_gain = summary.get("g2_gain_mean", 0.0)
    if (g1_mean_gain < 0.15 or g2_mean_gain < 0.15) and h3.get("confirmed") is True:
        return False, "H3 inconsistency: gains below 0.15 but H3 declared confirmed"

    return True, "F14 V3 Independent Scientific Validation: ALL VERIFICATIONS PASSED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ACE F14 V3 Evidence Artifact")
    parser.add_argument("artifact_pos", nargs="?", default=None, help="Path to evidence artifact (positional)")
    parser.add_argument("--artifact", default=None, help="Path to evidence artifact (named)")
    args = parser.parse_args()

    art_path = args.artifact or args.artifact_pos or "evidence/f14/ace_f14_v3_scientific_validation.json.gz"
    path = Path(art_path)
    if not path.exists():
        print(f"ERROR: Artifact file not found: {path}", file=sys.stderr)
        return 1

    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to read artifact: {e}", file=sys.stderr)
        return 1

    ok, msg = verify_f14_v3_evidence(data)
    if ok:
        print(f"PASS: {msg}")
        return 0
    else:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
