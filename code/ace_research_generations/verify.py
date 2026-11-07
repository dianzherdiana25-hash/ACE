"""Independent Verifier for ACE Fase 7 (G0 -> G1 -> G2) Evidence Artifact."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from .immutable_guard import verify_ast_evaluator_isolation
from .runner import run_generations_benchmark


def verify_generations_artifact(
    artifact_path: Path,
    repo_root: Path | None = None,
    *,
    replay: bool = True,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    raw = gzip.decompress(artifact_path.read_bytes())
    sha = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw.decode("utf-8"))

    if doc.get("schema") != "ace.generations.g0_g2.v1":
        raise ValueError("unexpected schema")
    if doc.get("scientific_status") != "NOT_ASSESSED":
        raise ValueError("scientific_status must remain NOT_ASSESSED without external sealed eval")
    if doc.get("oaie_established") is not False:
        raise ValueError("oaie_established must be False")
    flags = doc.get("evidence_flags", {})
    if flags.get("PASSIVE_SEMANTIC_DRIFT_DETECTABLE") is not False:
        raise ValueError("must not claim passive semantic drift detectability")
    if not flags.get("ACE_BASE_RUNTIME_EXECUTED"):
        raise ValueError("ACE_BASE_RUNTIME_EXECUTED must be True")
    if not flags.get("NEW_CAPABILITY_INTEGRATED_AND_EXECUTED"):
        raise ValueError("NEW_CAPABILITY_INTEGRATED_AND_EXECUTED must be True")

    ast_iso = verify_ast_evaluator_isolation()
    if not ast_iso["isolated"]:
        raise ValueError(f"AST isolation failed: {ast_iso['violations']}")

    if len(doc.get("unit_records", [])) != 75:
        raise ValueError("expected 75 unit records (65 nominal + 10 drift)")

    # Verify all staged batches reached STAGED_FOR_REVIEW and never auto-deployed
    for trans_key in ("G0_to_G1", "G1_to_G2"):
        batches = doc["lineage_transitions"][trans_key]["autonomy_staging"]
        if not batches or any(b["status"] != "STAGED_FOR_REVIEW" for b in batches):
            raise ValueError(f"{trans_key} missing STAGED_FOR_REVIEW receipts")

    if not doc["hypotheses"]["all_gates_pass"]:
        raise ValueError(f"hypothesis gates did not all pass: {doc['hypotheses']}")

    if replay:
        fresh = run_generations_benchmark(root)
        fresh_raw = (json.dumps(fresh, sort_keys=True, indent=2) + "\n").encode("utf-8")
        fresh_sha = hashlib.sha256(fresh_raw).hexdigest()
        if fresh_sha != sha:
            raise ValueError(f"deterministic replay SHA mismatch: {fresh_sha} != {sha}")

    return {
        "verified": True,
        "uncompressed_sha256": sha,
        "all_gates_pass": doc["hypotheses"]["all_gates_pass"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ACE Fase 7 evidence artifact.")
    parser.add_argument(
        "--artifact",
        default="evidence/generations/ace_g0_g2_v1.json.gz",
    )
    parser.add_argument("--no-replay", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    res = verify_generations_artifact(root / args.artifact, root, replay=not args.no_replay)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
