#!/usr/bin/env python3
"""Unified External Verifier for ACE F13 & F14 Research Evidence.

Validates:
1. Upstream source pins (tools/verify_sources.py offline integrity check).
2. Pre-score commitment SHA-256 hashes for F13 and F14.
3. Raw evidence artifact SHA-256 checksums and schema decompression.
4. Independent verifier modules (ace_research_f13.verify and ace_research_f14.verify).
5. Unit test suites for F13 and F14.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_PRESCORE_HASHES = {
    "docs/research/f13/ACE_F13_CAUSAL_MEMORY_PRESCORE_20261107.md": "0948f00b273be45a408d7c758cd45c2b5a67c15c215b86e9600f2940decf34f3",
    "docs/research/f14/ACE_F14_INDEPENDENT_EVALUATION_PRESCORE_20261107.md": "08baed13793977b7a056e262d984dde074e243edf0aa00a5c45b486f0c249659",
}

EXPECTED_EVIDENCE_HASHES = {
    "evidence/f13/ace_f13_causal_memory_v1.json.gz": "efa00a78db2d6ab43f1635f6402adaa7049c82be59146268f91e29266324dd03",
    "evidence/f14/ace_f14_mechanism_discovery_v1.json.gz": "4cc363b9ff0fb17f84bc960bc4e94573c10ba038e525d2f7f5fcfd86141a3062",
}



def compute_sha256(rel_path: str) -> str:
    path = REPO_ROOT / rel_path
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print("=" * 70)
    print("ACE F13 & F14 UNIFIED EXTERNAL VERIFIER")
    print("=" * 70)

    # 1. Verify upstream source pins
    print("[1/5] Checking upstream source pins...")
    res = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "verify_sources.py")], cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print("FAIL: Upstream source pins compromised!", file=sys.stderr)
        return 1

    # 2. Verify pre-score commitment hashes
    print("[2/5] Checking pre-score commitment hashes...")
    for rel_path, expected_hash in EXPECTED_PRESCORE_HASHES.items():
        actual_hash = compute_sha256(rel_path)
        if actual_hash != expected_hash:
            print(f"FAIL: Pre-score hash mismatch for {rel_path}!\n  Expected: {expected_hash}\n  Actual:   {actual_hash}", file=sys.stderr)
            return 1
        print(f"  OK: {rel_path} matches pre-score hash {expected_hash[:16]}...")

    # 3. Verify evidence artifact hashes
    print("[3/5] Checking evidence artifact hashes...")
    for rel_path, expected_hash in EXPECTED_EVIDENCE_HASHES.items():
        actual_hash = compute_sha256(rel_path)
        if actual_hash != expected_hash:
            print(f"FAIL: Evidence hash mismatch for {rel_path}!\n  Expected: {expected_hash}\n  Actual:   {actual_hash}", file=sys.stderr)
            return 1
        print(f"  OK: {rel_path} matches evidence hash {expected_hash[:16]}...")

    # 4. Run independent research verifiers
    print("[4/5] Running research verifier CLI modules...")
    run_env = dict(os.environ) if "os" in dir() else {}
    run_env["PYTHONPATH"] = str(REPO_ROOT / "code")

    res_f13 = subprocess.run(
        [sys.executable, "-m", "ace_research_f13.verify", "--artifact", "evidence/f13/ace_f13_causal_memory_v1.json.gz"],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "code"), "PATH": str(Path(sys.executable).parent)},
    )
    if res_f13.returncode != 0:
        print("FAIL: ace_research_f13.verify failed!", file=sys.stderr)
        return 1

    res_f14 = subprocess.run(
        [sys.executable, "-m", "ace_research_f14.verify", "--artifact", "evidence/f14/ace_f14_mechanism_discovery_v1.json.gz"],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "code"), "PATH": str(Path(sys.executable).parent)},
    )
    if res_f14.returncode != 0:
        print("FAIL: ace_research_f14.verify failed!", file=sys.stderr)
        return 1

    # 5. Run test suites
    print("[5/5] Running unit test suites...")
    res_tests = subprocess.run(
        [sys.executable, "-m", "unittest", "ace_research_f13.test_f13_memory", "ace_research_f14.test_f14_discovery"],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "code"), "PATH": str(Path(sys.executable).parent)},
    )
    if res_tests.returncode != 0:
        print("FAIL: Unit test suite failed!", file=sys.stderr)
        return 1

    print("=" * 70)
    print("ALL F13 & F14 EXTERNAL VERIFICATIONS PASSED SUCCESSFULLY")
    print("Governance Status: release_gate=BLOCK_RELEASE, scientific_status=NOT_ASSESSED, oaie_established=False")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
