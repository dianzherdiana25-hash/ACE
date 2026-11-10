"""Generate a new public engineering repair receipt without touching frozen v1.

Use in a clean GitHub Actions worktree. The generated evidence has no scientific
acceptance or deployment authority. The old v1 evidence is only custody-checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ace_research_repair.corpus import canonical_json, sha256_digest
from ace_research_repair.runner import run_benchmark, compress_deterministic_gzip
from ace_research_repair.verify import (
    _first_difference_paths, verify_report_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
V1_BLOB = "5ae098a6f28ba0269d3d650b0704c588ef8f9783"


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def generate(output: Path) -> dict:
    old_path = ROOT / "evidence" / "repair" / "ace_repair_v1.json.gz"
    old = old_path.read_bytes()
    if git_blob(old) != V1_BLOB:
        raise ValueError("frozen historical repair v1 blob changed")

    old_receipt = verify_report_bytes(old, repo_root=ROOT, replay=False)
    from ace_research_repair.runner import decompress_gzip
    historical = json.loads(decompress_gzip(old).decode("utf-8"))

    report = run_benchmark()
    raw_json = canonical_json(report)
    gzip_bytes = compress_deterministic_gzip(raw_json)
    new_receipt = verify_report_bytes(gzip_bytes, repo_root=ROOT, replay=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip_bytes)

    return {
        "schema": "ace.repair.v2.public-candidate",
        "historical_v1_git_blob": V1_BLOB,
        "historical_v1_canonical_sha256": old_receipt["canonical_json_sha256"],
        "historical_v1_replay_matches_current": raw_json == canonical_json(historical),
        "changed_json_pointers_sample": _first_difference_paths(historical, report, limit=20),
        "candidate_v2_sha256": sha256_digest(gzip_bytes),
        "candidate_v2_canonical_sha256": sha256_digest(raw_json),
        "candidate_v2_gzip_bytes": len(gzip_bytes),
        "candidate_v2_canonical_bytes": len(raw_json),
        "candidate_v2_runtime_implementation_sha256": report["final_ace_state"]["runtime_implementation_sha256"],
        "candidate_v2_nominal_verified": {
            arm: report["arm_summaries"][arm]["nominal_terminal_verified"]
            for arm in report["arms"]
        },
        "candidate_v2_hypotheses": {
            k: v["passed"] for k, v in report["hypotheses"].items()
        },
        "candidate_v2_scientific_validation": report["evidence_flags"]["SCIENTIFIC_CAPABILITY_VALIDATED"],
        "scientific_decision": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE",
        "candidate_deployed": False,
        "public_engineering_receipt_only": True,
        "historical_v1_structure_verified": old_receipt["status"],
        "candidate_v2_structure_verified": new_receipt["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = generate(args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, "HALT_REPAIR_V2_DIAGNOSTIC: " + str(exc) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
