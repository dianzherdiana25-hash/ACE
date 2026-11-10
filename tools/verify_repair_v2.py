"""Fail-closed versioned repair v2 public replay receipt verification.

V1 remains immutable historical evidence; only v2 may be compared to current
runtime. A public engineering receipt is NOT an independent scientific evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ace_research_repair.corpus import sha256_digest
from ace_research_repair.runner import decompress_gzip
from ace_research_repair.verify import verify_report_bytes

ROOT = Path(__file__).resolve().parents[1]
V1_BLOB = "5ae098a6f28ba0269d3d650b0704c588ef8f9783"
V2_GZIP_SHA256 = "a0fac38f0ad20ba4e0b64548e17588b5d55b3609b585fd012b04b76f14418456"
V2_CANONICAL_SHA256 = "57a8342870e0b9c40dddd4c5c535fd069eb1e8ba081d810e7233cc871f6fbddb"
V2_BYTES = 62731
V2_CANONICAL_BYTES = 491811
RUNTIME_IMPLEMENTATION = "068be383bf08ea7301a1425c7ab4c71070744a2f5db11a3136737c9bbf4cb5d5"


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


class RepairV2ReceiptError(ValueError):
    """Receipt does not match its custody, structural or engineering replay contract."""


def verify_manifest(manifest: dict) -> None:
    if type(manifest) is not dict:
        raise RepairV2ReceiptError("invalid v2 provenance root")
    if (manifest.get("schema") != "ace.repair.public-engineering.v2.provenance"
            or manifest.get("scientific_status") != "NOT_ASSESSED"
            or manifest.get("release_gate") != "BLOCK_RELEASE"
            or manifest.get("status") != "PASS_PUBLIC_REPLAY_NOT_SCIENTIFIC_GO"
            or manifest.get("candidate_deployed") is not False
            or manifest.get("open_world_safe") is not False
            or manifest.get("oaie_established") is not False):
        raise RepairV2ReceiptError("manifest falsely claims scientific or release authority")
    old = manifest.get("v1_historical")
    new = manifest.get("v2_candidate")
    if type(old) is not dict or type(new) is not dict:
        raise RepairV2ReceiptError("missing versioned receipt custody")
    if (old.get("git_blob_sha1") != V1_BLOB
            or old.get("canonical_sha256") != "0eb98aa4eb967fb1207589cb28a3d595278557af033ce309c83922d684b04929"
            or old.get("replay_matches_v2") is not False):
        raise RepairV2ReceiptError("historical v1 provenance altered or misrepresented")
    if (new.get("gzip_sha256") != V2_GZIP_SHA256
            or type(new.get("gzip_bytes")) is not int or new["gzip_bytes"] != V2_BYTES
            or new.get("canonical_sha256") != V2_CANONICAL_SHA256
            or type(new.get("canonical_bytes")) is not int
            or new["canonical_bytes"] != V2_CANONICAL_BYTES
            or new.get("runtime_implementation_sha256") != RUNTIME_IMPLEMENTATION
            or new.get("scientific_capability_validated") is not False
            or new.get("byte_identical_two_clean_runs") is not True
            or new.get("nominal_verified") != {
                "R_ace": 12, "R_fixed": 12, "R_fresh": 12, "R_rule": 11
            }
            or new.get("hypotheses") != {
                "H1_nominal_accuracy_and_coverage": False,
                "H2_efficiency_or_accuracy_vs_fresh": True,
                "H3_anti_overfit_and_ood_abstention": True,
                "H4_cross_restart_persistence": True,
            }):
        raise RepairV2ReceiptError("v2 provenance does not match independently logged candidate")


def verify(candidate: Path, manifest_path: Path | None = None) -> dict:
    manifest_path = manifest_path or ROOT / "evidence" / "repair" / "v2-provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_manifest(manifest)

    historical = (ROOT / "evidence" / "repair" / "ace_repair_v1.json.gz").read_bytes()
    if git_blob(historical) != V1_BLOB:
        raise RepairV2ReceiptError("historical v1 artifact bytes changed")
    old_receipt = verify_report_bytes(historical, repo_root=ROOT, replay=False)
    if old_receipt["canonical_json_sha256"] != manifest["v1_historical"]["canonical_sha256"]:
        raise RepairV2ReceiptError("historical v1 canonical payload changed")

    data = candidate.read_bytes()
    if len(data) != V2_BYTES or sha256_digest(data) != V2_GZIP_SHA256:
        raise RepairV2ReceiptError("candidate does not match pinned reproducible v2 byte digest")
    new_receipt = verify_report_bytes(data, repo_root=ROOT, replay=False)
    raw = decompress_gzip(data)
    if len(raw) != V2_CANONICAL_BYTES or sha256_digest(raw) != V2_CANONICAL_SHA256:
        raise RepairV2ReceiptError("v2 canonical JSON differs from pinned receipt")
    report = json.loads(raw)
    if (report.get("final_ace_state", {}).get("runtime_implementation_sha256")
            != RUNTIME_IMPLEMENTATION):
        raise RepairV2ReceiptError("candidate runtime implementation drifted")
    if (report.get("release_gate") != "BLOCK_RELEASE"
            or report.get("scientific_decision") != "NOT_ASSESSED"
            or report.get("candidate_deployed") is not False
            or report.get("oaie_established") is not False
            or report.get("open_world_safe") is not False
            or report.get("evidence_flags", {}).get("SCIENTIFIC_CAPABILITY_VALIDATED") is not False):
        raise RepairV2ReceiptError("candidate claims unverified scientific promotion")
    summary = report.get("arm_summaries", {})
    for arm, count in manifest["v2_candidate"]["nominal_verified"].items():
        if summary.get(arm, {}).get("nominal_terminal_verified") != count:
            raise RepairV2ReceiptError("candidate arm score differs from replay")
    for hypothesis, expected in manifest["v2_candidate"]["hypotheses"].items():
        if report.get("hypotheses", {}).get(hypothesis, {}).get("passed") is not expected:
            raise RepairV2ReceiptError("candidate hypothesis result differs from replay")

    return {
        "status": "PASS_PUBLIC_REPAIR_V2_REPLAY_NOT_SCIENTIFIC_GO",
        "historical_v1_custody": old_receipt["status"],
        "current_v2_structural_custody": new_receipt["status"],
        "current_v2_gzip_sha256": V2_GZIP_SHA256,
        "scientific_status": "NOT_ASSESSED",
        "release_gate": "BLOCK_RELEASE",
        "candidate_deployed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.candidate, args.manifest)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, "HALT_INVALID_REPAIR_V2_RECEIPT: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
