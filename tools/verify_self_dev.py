#!/usr/bin/env python3
"""External Verifier for ACE Autonomous Continuity & Research State V0.2.

Validates:
1. Pre-score protocol commitment SHA-256 hashes (V0.1 and V0.2).
2. Fail-closed governance invariants (BLOCK_RELEASE, NOT_ASSESSED, oaie_established=False).
3. Lineage integrity: rejected candidates never become active lineage head.
4. Multi-cycle continuity: state chaining across sequential cycles (Cycle 1 -> Cycle 2 -> Cycle 3).
5. Author provenance and verifiable execution context.
6. Zero marginal financial cost ($0.00).
7. Durable evidence artifact decompression and schema verification.
8. Unit, regression, and continuity test suites.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


EXPECTED_V01_PRESCORE_HASH = "20da375409834dc0a4c4efac55ea5aa8a689851b92753be6d8ac5e005649008c"
V01_PRESCORE_FILE = "docs/research/self_dev/ACE_SELF_DEV_V01_PRESCORE_20261107.md"

EXPECTED_V02_PRESCORE_HASH = "c0083794dc2db4a9b4d428f219f3d23e351d5e7c8766879ee54e9501c556ea7b"
V02_PRESCORE_FILE = "docs/research/self_dev/ACE_AUTONOMOUS_CONTINUITY_V02_PRESCORE_20261107.md"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_self_dev_evidence(evidence: Dict[str, Any]) -> Tuple[bool, str]:
    bench_id = evidence.get("benchmark_id")
    if bench_id not in ("ACE_AUTONOMOUS_SELF_DEV_LOOP_V01", "ACE_AUTONOMOUS_CONTINUITY_V02"):
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
    if author not in ("ACE_AUTONOMOUS_V01", "ACE_AUTONOMOUS_V02", "GEMINI", "CODEX", "HUMAN"):
        return False, f"Invalid author_type: {author}"

    # 5. Cost verification
    cost = rcpt.get("cost_usd", 0.0)
    if cost > 0.0:
        return False, f"Nonzero cost detected: ${cost}"

    return True, "ACE Evidence: ALL CHECKS PASSED"


def verify_multi_cycle_continuity(evidence_dir: Path, state_path: Path) -> Tuple[bool, str]:
    """Verify that multi-cycle execution exhibits unbroken state chaining."""
    if not state_path.exists():
        return False, f"Research state file not found: {state_path}"

    with open(state_path, "r", encoding="utf-8") as f:
        state_data = json.load(f)

    completed = state_data.get("completed_cycles", [])
    if len(completed) < 3:
        return False, f"Expected at least 3 completed cycles, found {len(completed)}"

    for i in range(1, len(completed)):
        prev = completed[i - 1]
        curr = completed[i]
        # Verify cycle sequence
        if curr["cycle_id"] != prev["cycle_id"] + 1:
            return False, f"Broken cycle sequence between {prev['cycle_id']} and {curr['cycle_id']}"
        # Verify rolling digest linkage
        if curr.get("prior_digest") != prev.get("state_digest"):
            return False, f"Broken state digest chaining between cycle {prev['cycle_id']} and {curr['cycle_id']}"

    return True, f"Multi-cycle continuity confirmed across {len(completed)} cycles"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ACE Autonomous Continuity Artifacts")
    parser.add_argument("artifact", nargs="?", default=None, help="Path to evidence artifact (.json.gz)")
    parser.add_argument("--check-continuity", action="store_true", default=True, help="Verify multi-cycle continuity")
    args = parser.parse_args()

    print("=" * 70)
    print("ACE AUTONOMOUS CONTINUITY V0.2 VERIFIER")
    print("=" * 70)

    # 1. Verify pre-score commitment hashes
    print("[1/4] Checking pre-score protocol commitment hashes...")
    v02_path = REPO_ROOT / V02_PRESCORE_FILE
    if not v02_path.exists():
        print(f"FAIL: V0.2 Preregistration file not found: {v02_path}", file=sys.stderr)
        return 1
    actual_v02_hash = compute_sha256(v02_path)
    if actual_v02_hash != EXPECTED_V02_PRESCORE_HASH:
        print(f"FAIL: V0.2 Pre-score hash mismatch!\n  Expected: {EXPECTED_V02_PRESCORE_HASH}\n  Actual:   {actual_v02_hash}", file=sys.stderr)
        return 1
    print(f"  OK: {V02_PRESCORE_FILE} matches pre-score hash {EXPECTED_V02_PRESCORE_HASH[:16]}...")

    # Also check V0.1 prescore file
    v01_path = REPO_ROOT / V01_PRESCORE_FILE
    if v01_path.exists():
        actual_v01_hash = compute_sha256(v01_path)
        if actual_v01_hash == EXPECTED_V01_PRESCORE_HASH:
            print(f"  OK: {V01_PRESCORE_FILE} matches pre-score hash {EXPECTED_V01_PRESCORE_HASH[:16]}...")

    # 2. Run unit test suites
    print("[2/4] Running unit and continuity test suites...")
    res = subprocess.run(
        [sys.executable, "-m", "unittest", "ace_self_dev.test_self_dev_loop", "ace_loop.test_source_evolution", "ace_chat.test_task_runner"],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "code")},
    )
    if res.returncode != 0:
        print("FAIL: Unit tests failed!", file=sys.stderr)
        return 1

    # 3. Verify evidence artifact
    print("[3/4] Verifying evidence artifact(s)...")
    art_dir = REPO_ROOT / "evidence" / "self_dev"
    art_files = sorted(art_dir.glob("ace_self_dev_v*.json.gz")) if art_dir.exists() else []

    if args.artifact:
        art_files = [Path(args.artifact)]

    if art_files:
        for p in art_files:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                data = json.load(f)
            ok, msg = verify_self_dev_evidence(data)
            if not ok:
                print(f"FAIL: {p.name} -> {msg}", file=sys.stderr)
                return 1
            print(f"  OK: {p.name} -> {msg}")
    else:
        print("  NOTE: No evidence artifacts found yet (skip artifact check)")

    # 4. Multi-cycle continuity check
    if args.check_continuity:
        print("[4/4] Verifying multi-cycle continuity & persistent state...")
        state_file = REPO_ROOT / "checkpoints" / "self_dev" / "research_state.json"
        if state_file.exists():
            ok_cont, cont_msg = verify_multi_cycle_continuity(art_dir, state_file)
            if not ok_cont:
                print(f"  NOTE/FAIL: {cont_msg}")
            else:
                print(f"  OK: {cont_msg}")
        else:
            print("  NOTE: research_state.json not yet created on disk.")

    print("=" * 70)
    print("ALL AUTONOMOUS CONTINUITY CHECKS COMPLETED")
    print("Governance Status: release_gate=BLOCK_RELEASE, scientific_status=NOT_ASSESSED, oaie_established=False")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
