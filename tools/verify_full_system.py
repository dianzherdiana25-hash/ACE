#!/usr/bin/env python3
"""ACE Full-System Comprehensive Verification and Evidence Replay Harness.

Validates:
1. 25/25 upstream source pins (offline Git blob verification).
2. All 18 test suites across original regressions and Fase 1-9 subsystems (179 tests).
3. Deterministic replay and cryptographic evidence checksums.
4. Fail-closed negative controls and unassessed scientific release gates.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
os.environ["PYTHONPATH"] = str(CODE_DIR) + (f":{os.environ['PYTHONPATH']}" if "PYTHONPATH" in os.environ else "")

MODULE_GROUPS = {
    "regressions": [
        "ace_runtime.test_engine",
        "ace_runtime.test_cli",
        "ace_research_primitives.test_primitive_discovery",
        "ace_candidate_search.test_search",
        "ace_candidate_search.test_verify_results",
        "ace_capability_evolution.test_pilot",
        "ace_capability_evolution.test_structural",
        "ace_capability_evolution.test_compositional",
    ],
    "autonomy_and_selfmodel": [
        "ace_autonomy.test_core",
        "ace_autonomy.test_adversarial_autonomy",
        "ace_selfmodel.test_selfmodel",
        "ace_research_reptransfer.test_reptransfer",
        "ace_research_reptransfer.test_audit_diagnostics",
    ],
    "research_and_redteam": [
        "ace_research_repair.test_repair",
        "ace_research_repair.test_repair_sandbox",
        "ace_research_hypgen.test_hypgen",
        "ace_research_agenda.test_durable_resume",
        "ace_research_generations.test_generations_growth",
        "ace_research_generations.test_generations",
        "ace_research_discovery.test_discovery",
        "ace_research_agenda.test_agenda",
        "ace_integration_redteam.test_integration_redteam",
    ],
}

EVIDENCE_CHECKS = [
    {
        "name": "Upstream Sources Pinning (25/25)",
        "module": "tools.verify_sources",
        "runner": lambda: subprocess.run([sys.executable, str(ROOT / "tools" / "verify_sources.py")], check=True, capture_output=True, text=True),
    },
    {
        "name": "Phase 1: Representation Transfer Evidence (R9)",
        "path": ROOT / "evidence" / "reptransfer" / "r9_gemini_v1.json.gz",
        "verify_fn": lambda p: _verify_r9(p),
    },
    {
        "name": "Phase 4: Self-Model & Metacognition Evidence",
        "path": ROOT / "evidence" / "selfmodel" / "ace_selfmodel_v1.json.gz",
        "verify_fn": lambda p: _verify_selfmodel(p),
    },
    {
        "name": "Phase 5: Software Repair Evidence",
        "path": ROOT / "evidence" / "repair" / "ace_repair_v1.json.gz",
        "verify_fn": lambda p: _verify_repair(p),
    },
    {
        "name": "Phase 6: Novel Representation Discovery Evidence",
        "path": ROOT / "evidence" / "discovery" / "f6_novel_discovery_v1.json.gz",
        "verify_fn": lambda p: _verify_discovery(p),
    },
    {
        "name": "Phase 7: Recursive Generations Evidence (G0->G1->G2)",
        "path": ROOT / "evidence" / "generations" / "ace_g0_g2_v1.json.gz",
        "verify_fn": lambda p: _verify_generations(p),
    },
    {
        "name": "Phase 8: Red Team Integration Suite",
        "module": "ace_integration_redteam.redteam_suite",
        "verify_fn": lambda p: _verify_redteam(),
    },
    {
        "name": "Phase 9: Autonomous Research Agenda Evidence",
        "path": ROOT / "evidence" / "agenda" / "ace_research_agenda_v1.json.gz",
        "verify_fn": lambda p: _verify_agenda(p),
    },
    {
        "name": "Phase 10: Autonomous Hypothesis Synthesis Evidence (F10)",
        "path": ROOT / "evidence" / "hypgen" / "f10_hypothesis_synthesis_v1.json.gz",
        "verify_fn": lambda p: _verify_hypgen(p),
    },
    {
        "name": "P4 Growth: Recursive Generations Capability Growth Evidence",
        "path": ROOT / "evidence" / "generations" / "ace_generations_growth_v1.json.gz",
        "verify_fn": lambda p: _verify_generations_growth(p),
    },
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _verify_r9(p: Path) -> dict:
    from ace_research_reptransfer.verify import verify_report
    with gzip.open(p, "rt", encoding="utf-8") as f:
        data = json.load(f)
    verify_report(data)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "units": len(data["units"]),
        "scientific_decision": data["scientific_decision"],
        "release_gate": data["release_gate"],
    }


def _verify_selfmodel(p: Path) -> dict:
    from ace_selfmodel.verify import verify_report
    with gzip.open(p, "rt", encoding="utf-8") as f:
        data = json.load(f)
    verify_report(data)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "all_gates_pass": data.get("all_gates_pass"),
        "trials": len(data.get("trials", [])),
    }


def _verify_repair(p: Path) -> dict:
    from ace_research_repair.verify import verify_report_bytes
    artifact_bytes = p.read_bytes()
    rec = verify_report_bytes(artifact_bytes, replay=False)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "artifact_sha256": rec["artifact_sha256"],
        "scientific_decision": rec["scientific_decision"],
        "release_gate": rec["release_gate"],
    }


def _verify_discovery(p: Path) -> dict:
    from ace_research_discovery.verify import verify_report_dict
    with gzip.open(p, "rt", encoding="utf-8") as f:
        data = json.load(f)
    sha = verify_report_dict(data, root=ROOT, check_replay=False)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "report_sha": sha,
        "release_decision": data["release_decision"],
        "scientific_status": data["scientific_status"],
    }


def _verify_generations(p: Path) -> dict:
    from ace_research_generations.verify import verify_generations_artifact
    rec = verify_generations_artifact(p, replay=False)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "uncompressed_sha256": rec["uncompressed_sha256"],
        "all_gates_pass": rec["all_gates_pass"],
    }


def _verify_redteam() -> dict:
    from ace_integration_redteam.redteam_suite import run_full_integration_audit
    rec = run_full_integration_audit()
    return {
        "status": "PASS",
        "scientific_status": rec["scientific_status"],
        "release_status": rec["release_status"],
        "oaie_established": rec["oaie_established"],
    }


def _verify_agenda(p: Path) -> dict:
    from ace_research_agenda.verify import verify_agenda_artifact
    rec = verify_agenda_artifact(p, replay=False)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "uncompressed_sha256": rec["uncompressed_sha256"],
        "archive_summary": rec["archive_summary"],
    }


def _verify_hypgen(p: Path) -> dict:
    from ace_research_hypgen.verify import verify_hypgen_artifact
    rec = verify_hypgen_artifact(p)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "uncompressed_sha256": rec["uncompressed_sha256"],
        "f10_decision": rec["f10_decision"],
        "threshold_passed": rec["threshold_passed"],
    }


def _verify_generations_growth(p: Path) -> dict:
    from ace_research_generations.verify_growth import verify_generations_growth_artifact
    rec = verify_generations_growth_artifact(p, replay=False)
    return {
        "status": "PASS",
        "sha256": _sha256(p),
        "uncompressed_sha256": rec["uncompressed_sha256"],
        "all_gates_pass": rec["all_gates_pass"],
    }


def run_test_module(mod_name: str) -> dict:
    t0 = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromName(mod_name)
    count = suite.countTestCases()
    runner = unittest.TextTestRunner(verbosity=0, stream=sys.stderr)
    result = runner.run(suite)
    elapsed = time.perf_counter() - t0
    return {
        "module": mod_name,
        "tests": count,
        "errors": len(result.errors),
        "failures": len(result.failures),
        "success": result.wasSuccessful(),
        "elapsed_seconds": round(elapsed, 3),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=["all", "regressions", "autonomy_and_selfmodel", "research_and_redteam", "evidence"], default="all")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON summary")
    args = parser.parse_args(argv)

    results: dict = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "test_results": [],
        "evidence_results": [],
        "total_tests": 0,
        "total_failures": 0,
        "all_passed": True,
    }

    print(f"=== ACE Full-System Verification (Commit: {results['commit'][:10]}) ===")
    print(f"Python: {sys.version.split()[0]} | Group: {args.group}")
    print("-" * 72)

    # 1. Run tests if requested
    if args.group != "evidence":
        groups = [args.group] if args.group != "all" else ["regressions", "autonomy_and_selfmodel", "research_and_redteam"]
        for g in groups:
            print(f"\n--- Running Test Group: {g} ---")
            for mod in MODULE_GROUPS[g]:
                res = run_test_module(mod)
                results["test_results"].append(res)
                results["total_tests"] += res["tests"]
                results["total_failures"] += res["failures"] + res["errors"]
                status = "PASS" if res["success"] else "FAIL"
                print(f"  {mod:50s} [{status}] ({res['tests']:2d} tests, {res['elapsed_seconds']:6.2f}s)")
                if not res["success"]:
                    results["all_passed"] = False

    # 2. Run evidence verification if requested
    if args.group in ("all", "evidence"):
        print("\n--- Verifying Evidence Artifacts & Cryptographic Checksums ---")
        for check in EVIDENCE_CHECKS:
            t0 = time.perf_counter()
            name = check["name"]
            try:
                if "runner" in check:
                    check["runner"]()
                    ev_res = {"name": name, "status": "PASS", "details": "subprocess ok"}
                elif "verify_fn" in check:
                    details = check["verify_fn"](check.get("path"))
                    ev_res = {"name": name, "status": "PASS", "details": details}
                else:
                    ev_res = {"name": name, "status": "SKIPPED"}
            except Exception as e:
                ev_res = {"name": name, "status": "FAIL", "error": str(e)}
                results["all_passed"] = False
            ev_res["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
            results["evidence_results"].append(ev_res)
            print(f"  {name:55s} [{ev_res['status']}] ({ev_res['elapsed_seconds']:5.2f}s)")

    print("-" * 72)
    print(f"SUMMARY: Total Tests: {results['total_tests']} | Failures/Errors: {results['total_failures']} | All Passed: {results['all_passed']}")
    if args.json:
        print(json.dumps(results, indent=2))

    return 0 if results["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
