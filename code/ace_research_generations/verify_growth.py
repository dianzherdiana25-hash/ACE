"""Independent Verifier for ACE P4 Generations Growth Evidence Artifact."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from .growth import run_generations_growth_benchmark
from .immutable_guard import verify_ast_evaluator_isolation


def verify_generations_growth_artifact(
    artifact_path: Path,
    repo_root: Path | None = None,
    *,
    replay: bool = True,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    raw = gzip.decompress(artifact_path.read_bytes())
    sha = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw.decode("utf-8"))

    if doc.get("schema") != "ace.generations.growth.v1":
        raise ValueError("unexpected schema")
    if doc.get("scientific_status") != "NOT_ASSESSED":
        raise ValueError("scientific_status must remain NOT_ASSESSED")
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

    if len(doc.get("unit_records", [])) != 40:
        raise ValueError(f"expected 40 unit records (30 growth + 10 drift), got {len(doc.get('unit_records', []))}")

    if not doc["hypotheses"]["all_gates_pass"]:
        raise ValueError(f"growth hypothesis gates did not all pass: {doc['hypotheses']}")

    if replay:
        fresh = run_generations_growth_benchmark(root)
        fresh_raw = (json.dumps(fresh, sort_keys=True, indent=2) + "\n").encode("utf-8")
        fresh_sha = hashlib.sha256(fresh_raw).hexdigest()
        if fresh_sha != sha:
            raise ValueError(f"deterministic replay SHA mismatch: {fresh_sha} != {sha}")

    return {
        "verified": True,
        "uncompressed_sha256": sha,
        "all_gates_pass": doc["hypotheses"]["all_gates_pass"],
        "hypotheses": doc["hypotheses"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ACE P4 generations growth evidence artifact.")
    parser.add_argument(
        "--artifact",
        default="evidence/generations/ace_generations_growth_v1.json.gz",
    )
    parser.add_argument("--no-replay", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    res = verify_generations_growth_artifact(root / args.artifact, root, replay=not args.no_replay)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
