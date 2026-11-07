"""Independent Verifier for ACE Active Epistemic Capability Evidence Artifact."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict

from . import (
    ACE_RUNTIME_ROLE,
    GEMINI_ROLE,
    OAIE_ESTABLISHED,
    RELEASE_GATE,
    SCHEMA_VERSION,
    SCIENTIFIC_STATUS,
)
from .harness import run_active_epistemic_benchmark


def verify_active_epistemic_artifact(
    artifact_path: Path,
    *,
    replay: bool = False,
) -> Dict[str, Any]:
    raw_gz = artifact_path.read_bytes()
    gz_sha256 = hashlib.sha256(raw_gz).hexdigest()
    raw_json = gzip.decompress(raw_gz)
    uncompressed_sha256 = hashlib.sha256(raw_json).hexdigest()

    data = json.loads(raw_json.decode("utf-8"))

    if data.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"Schema mismatch: expected {SCHEMA_VERSION}, got {data.get('schema')}")
    if data.get("scientific_status") != SCIENTIFIC_STATUS:
        raise ValueError(f"scientific_status must be {SCIENTIFIC_STATUS}")
    if data.get("release_gate") != RELEASE_GATE:
        raise ValueError(f"release_gate must be {RELEASE_GATE}")
    if data.get("oaie_established") is not OAIE_ESTABLISHED:
        raise ValueError("oaie_established must be False")

    attribution = data.get("attribution", {})
    if attribution.get("gemini_role") != GEMINI_ROLE:
        raise ValueError(f"Attribution mismatch for gemini_role: {attribution.get('gemini_role')}")
    if attribution.get("ace_runtime_role") != ACE_RUNTIME_ROLE:
        raise ValueError(f"Attribution mismatch for ace_runtime_role: {attribution.get('ace_runtime_role')}")

    hypotheses = data.get("hypotheses", {})
    if not hypotheses.get("all_gates_pass"):
        raise ValueError("Hypothesis gates failed in artifact")

    arms = data.get("arms", {})
    required_arms = {"M1_passive_supervised", "M2_random_query_fuzzing", "M3_active_epistemic_probing", "M4_resource_bounded_probing"}
    if set(arms.keys()) != required_arms:
        raise ValueError(f"Arm mismatch: expected {required_arms}, got {set(arms.keys())}")

    if replay:
        fresh = run_active_epistemic_benchmark()
        if not fresh["hypotheses"]["all_gates_pass"]:
            raise ValueError("Replay evaluation failed hypothesis gates")

    return {
        "status": "PASS",
        "schema": SCHEMA_VERSION,
        "gz_sha256": gz_sha256,
        "uncompressed_sha256": uncompressed_sha256,
        "all_gates_pass": hypotheses["all_gates_pass"],
        "active_rejection_rate": hypotheses["H2_active_superiority"]["active_rejection_rate"],
        "random_rejection_rate": hypotheses["H2_active_superiority"]["random_rejection_rate"],
        "passive_false_admission_rate": hypotheses["H1_passive_drift_blindness"]["observed_false_admission_rate"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path("evidence/capability/ace_active_epistemic_v1.json.gz"))
    parser.add_argument("--replay", action="store_true", help="Re-run benchmark evaluation")
    args = parser.parse_args(argv)

    try:
        rec = verify_active_epistemic_artifact(args.artifact, replay=args.replay)
        print("=== ACE Active Epistemic Evidence Verification: PASS ===")
        print(f"Artifact: {args.artifact}")
        print(f"Uncompressed SHA-256: {rec['uncompressed_sha256']}")
        print(f"H1 Passive False Admission Rate: {rec['passive_false_admission_rate']:.2f}")
        print(f"H2 Active vs Random Rejection: {rec['active_rejection_rate']:.2f} vs {rec['random_rejection_rate']:.2f}")
        print(f"All Gates Pass: {rec['all_gates_pass']}")
        return 0
    except Exception as e:
        print(f"=== ACE Active Epistemic Evidence Verification: FAIL ({e}) ===", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
