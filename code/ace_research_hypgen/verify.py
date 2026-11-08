"""Independent integrity, schema, and falsification verifier for F10 evidence."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from . import OAIE_ESTABLISHED, RELEASE_GATE, SCHEMA_VERSION, SCIENTIFIC_STATUS


def verify_hypgen_artifact(artifact_path: Path) -> dict[str, Any]:
    raw_gz = artifact_path.read_bytes()
    gz_sha256 = hashlib.sha256(raw_gz).hexdigest()
    raw_json = gzip.decompress(raw_gz)
    uncompressed_sha256 = hashlib.sha256(raw_json).hexdigest()

    data = json.loads(raw_json.decode("utf-8"))

    if data.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"schema mismatch: expected {SCHEMA_VERSION}, got {data.get('schema')}")
    if data.get("scientific_status") != SCIENTIFIC_STATUS:
        raise ValueError(f"scientific_status must remain {SCIENTIFIC_STATUS}")
    if data.get("release_gate") != RELEASE_GATE:
        raise ValueError(f"release_gate must remain {RELEASE_GATE}")
    if data.get("oaie_established") is not OAIE_ESTABLISHED:
        raise ValueError("oaie_established must remain False")

    arms = data.get("arms", {})
    required_arms = {"M1_fixed_catalog", "M2_random_grammar", "M3_novelty_only", "M4_extra_compute", "M5_f10_structural"}
    if set(arms.keys()) != required_arms:
        raise ValueError(f"missing benchmark arms: expected {required_arms}, got {set(arms.keys())}")

    for arm_name, arm_data in arms.items():
        if arm_data.get("falsifiable_rate") != 1.0:
            raise ValueError(f"arm {arm_name} has non-falsifiable hypotheses ({arm_data.get('falsifiable_rate')})")
        if not arm_data.get("runtime_receipts"):
            raise ValueError(f"arm {arm_name} lacks real ACE runtime receipts")

    return {
        "status": "PASS",
        "schema": SCHEMA_VERSION,
        "gz_sha256": gz_sha256,
        "uncompressed_sha256": uncompressed_sha256,
        "f10_decision": data.get("f10_decision"),
        "threshold_passed": data.get("threshold_passed"),
        "delta_vs_random": data.get("delta_vs_random"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, default=Path("evidence/hypgen/f10_hypothesis_synthesis_v1.json.gz"), nargs="?")
    parser.add_argument("--artifact", type=Path, default=None, dest="artifact_opt", help="Optional artifact path alias")
    args = parser.parse_args(argv)

    target_path = args.artifact_opt or args.artifact
    try:
        res = verify_hypgen_artifact(target_path)
        print(f"PASS: F10 verifier ok. Decision={res['f10_decision']} (delta={res['delta_vs_random']})")
        return 0
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
