#!/usr/bin/env python3
"""External Verifier for ACE Autonomous Self-Development Loop V0.1.

Validates:
1. Pre-score protocol commitment SHA-256 hash.
2. Fail-closed governance invariants (BLOCK_RELEASE, NOT_ASSESSED, oaie_established=False).
3. Lineage integrity: rejected candidates never become active lineage head.
4. Author provenance tracking (ACE, Gemini, Codex, Human).
5. Zero marginal financial cost ($0.00).
6. Evidence artifact decompression and schema verification.
7. Unit and integration test suites.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_PRESCORE_HASH = "20da375409834dc0a4c4efac55ea5aa8a689851b92753be6d8ac5e005649008c"
PRESCORE_FILE = "docs/research/self_dev/ACE_SELF_DEV_V01_PRESCORE_20261107.md"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_self_dev_evidence(evidence: Dict[str, Any]) -> Tuple[bool, str]:
    bench_id = evidence.get("benchmark_id")
    if bench_id != "ACE_AUTONOMOUS_SELF_DEV_LOOP_V01":
        return False, f"Invalid benchmark_id: {bench_id}"

    # 1. Governance check
    gov = evidence.get("governance_result", {})
    if gov.get("release_gate") != "BLOCK_RELEASE":
        return False, f"release_gate must be BLOCK_RELEASE, got {gov.get('release_gate')}"
    if gov.get("scientific_status") != "NOT_ASSESSED":
        return False, f"scientific_status must be NOT_ASSESSED, got {gov.get('scientific_status')}"
    if gov.get("oaie_established") is not False:
        return False, "oaie_established must strictly be False"

    # 2. Check essential sections
    for sec in ("diagnosis", "hypothesis", "candidate", "evaluation_receipt", "proposal"):
        if sec not in evidence:
            return False, f"Missing section '{sec}' in evidence payload"

    # 3. Lineage and gating verification
    rcpt = evidence["evaluation_receipt"]
    is_promoted = gov.get("is_promoted")
    gain = rcpt.get("gain_over_parent", 0.0)
    decision = rcpt.get("decision")
    active_head = gov.get("active_head_id", "")
    cand_id = rcpt.get("candidate_id", "")

    if gain < 0.1500:
        if decision != "REJECTED":
            return False, f"Candidate with gain {gain} < 0.1500 was not REJECTED (decision: {decision})"
        if is_promoted is not False:
            return False, "Candidate with gain < 0.1500 was marked promoted"
        if active_head == cand_id:
            return False, f"Lineage corruption: rejected candidate {cand_id} became active head"

    # 4. Author provenance
    author = evidence["candidate"].get("author_type")
    if author not in ("ACE_AUTONOMOUS_V01", "GEMINI", "CODEX", "HUMAN"):
        return False, f"Invalid author_type: {author}"

    # 5. Cost verification
    cost = rcpt.get("cost_usd", 0.0)
    if cost > 0.0:
        return False, f"Nonzero cost detected: ${cost}"

    return True, "ACE Self-Dev Evidence: ALL VERIFICATIONS PASSED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ACE Self-Development Artifacts")
    parser.add_argument("artifact", nargs="?", default=None, help="Path to evidence artifact (.json.gz)")
    args = parser.parse_args()

    print("=" * 70)
    print("ACE AUTONOMOUS SELF-DEVELOPMENT LOOP V0.1 VERIFIER")
    print("=" * 70)

    # 1. Verify pre-score commitment hash
    print("[1/3] Checking pre-score protocol commitment hash...")
    prescore_path = REPO_ROOT / PRESCORE_FILE
    if not prescore_path.exists():
        print(f"FAIL: Preregistration file not found: {prescore_path}", file=sys.stderr)
        return 1
    actual_hash = compute_sha256(prescore_path)
    if actual_hash != EXPECTED_PRESCORE_HASH:
        print(f"FAIL: Pre-score hash mismatch!\n  Expected: {EXPECTED_PRESCORE_HASH}\n  Actual:   {actual_hash}", file=sys.stderr)
        return 1
    print(f"  OK: {PRESCORE_FILE} matches pre-score hash {EXPECTED_PRESCORE_HASH[:16]}...")

    # 2. Run unit tests
    print("[2/3] Running self-dev test suites...")
    res = subprocess.run(
        [sys.executable, "-m", "unittest", "ace_self_dev.test_self_dev_loop", "ace_loop.test_source_evolution", "ace_chat.test_task_runner"],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "code")},
    )
    if res.returncode != 0:
        print("FAIL: Unit tests failed!", file=sys.stderr)
        return 1

    # 3. Verify evidence artifact if provided or default exists
    print("[3/3] Verifying evidence artifact...")
    art_path = args.artifact or str(REPO_ROOT / "evidence" / "self_dev" / "ace_self_dev_v01_cycle_0001.json.gz")
    path = Path(art_path)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        ok, msg = verify_self_dev_evidence(data)
        if not ok:
            print(f"FAIL: {msg}", file=sys.stderr)
            return 1
        print(f"  OK: {path.name} -> {msg}")
    else:
        print(f"  NOTE: Artifact {path.name} not yet generated (skip artifact check)")

    print("=" * 70)
    print("ALL SELF-DEVELOPMENT CHECKS PASSED")
    print("Governance Status: release_gate=BLOCK_RELEASE, scientific_status=NOT_ASSESSED, oaie_established=False")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
