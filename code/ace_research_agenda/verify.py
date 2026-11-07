"""Verifier for ACE Fase 9 Autonomous Research Agenda Evidence."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from .coordinator import run_autonomous_research_campaign


def verify_agenda_artifact(
    artifact_path: Path,
    repo_root: Path | None = None,
    *,
    replay: bool = True,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    raw = gzip.decompress(artifact_path.read_bytes())
    sha = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw.decode("utf-8"))

    if doc.get("schema") != "ace.research_agenda.v1":
        raise ValueError("unexpected agenda schema")
    if doc.get("scientific_status") != "NOT_ASSESSED":
        raise ValueError("scientific_status must remain NOT_ASSESSED")
    if doc.get("oaie_established") is not False:
        raise ValueError("oaie_established must be False")
    if (
        doc.get("consciousness_taxonomy", {}).get("PHENOMENAL_CONSCIOUSNESS")
        != "PHENOMENAL_CONSCIOUSNESS_UNKNOWN"
    ):
        raise ValueError("phenomenal consciousness flag violated")

    arch = doc["archive_summary"]
    if arch["supported_bounded"] < 3:
        raise ValueError("expected >=3 supported bounded hypotheses")
    if arch["refuted_negative_archived"] < 1:
        raise ValueError("expected >=1 archived negative result")
    if arch["abstained_unidentifiable"] < 1:
        raise ValueError("expected >=1 abstained unidentifiable hypothesis")
    if not arch["metacognitive_post_refutation_abstention_verified"]:
        raise ValueError("post-refutation metacognitive abstention not verified")

    if replay:
        fresh = run_autonomous_research_campaign(root)
        fresh_raw = (json.dumps(fresh, sort_keys=True, indent=2) + "\n").encode("utf-8")
        fresh_sha = hashlib.sha256(fresh_raw).hexdigest()
        if fresh_sha != sha:
            raise ValueError(f"agenda replay SHA mismatch: {fresh_sha} != {sha}")

    return {
        "verified": True,
        "uncompressed_sha256": sha,
        "archive_summary": arch,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ACE Fase 9 agenda artifact.")
    parser.add_argument("--artifact", default="evidence/agenda/ace_research_agenda_v1.json.gz")
    parser.add_argument("--replay", action="store_true", help="Re-run campaign replay")
    parser.add_argument("--no-replay", action="store_true", help="Deprecated alias")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    replay = bool(args.replay and not args.no_replay)
    print(json.dumps(verify_agenda_artifact(root / args.artifact, root, replay=replay), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
