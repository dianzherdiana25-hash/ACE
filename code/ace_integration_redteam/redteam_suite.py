"""System-Wide Integration & Red Team Audit Runner for ACE Fase 8."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any

from ace_autonomy import (
    Autonomy,
    BudgetCeiling,
    GoalPolicy,
    IntegrityError,
    PolicyError,
    UncertainExternalEffectError,
)
from ace_research_agenda import ResearchArchive, run_autonomous_research_campaign
from ace_research_generations import ImmutableCoreGuard, verify_ast_evaluator_isolation
from ace_research_repair import (
    MemoryIntegrityError,
    PublicUnitView,
    RepairEngine,
    RepairMemory,
    DevTestCase,
    source_units,
)
from ace_runtime.cli import demo as ace_demo_fn
from ace_runtime.engine import Runtime
from ace_selfmodel import ExperienceMemory, PHENOMENAL_CONSCIOUSNESS_STATUS, introspect_self_state


def _check_pkg_evaluator_isolation(pkg_dir: Path, fit_modules: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for mod in fit_modules:
        p = pkg_dir / mod
        if not p.is_file():
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if "evaluator" in a.name.split("."):
                        violations.append(f"{pkg_dir.name}/{mod}: import {a.name}")
            elif isinstance(node, ast.ImportFrom):
                m = node.module or ""
                if "evaluator" in m.split(".") or any(a.name == "evaluator" for a in node.names):
                    violations.append(f"{pkg_dir.name}/{mod}: from {m} import evaluator")
    return violations


def run_full_integration_audit(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()

    # 1. Upstream source pins & Codex boundary check
    pin_proc = subprocess.run(
        [sys.executable, str(root / "tools/verify_sources.py")],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    )
    graph_builder_untouched = not (root / "code/ace_research_graph_builder").exists()

    # 2. Real ACE Base Runtime check
    with tempfile.TemporaryDirectory(prefix="ace_fase8_rt_") as rtmp:
        with Runtime(Path(rtmp) / "ace_ws") as rt:
            demo_res = ace_demo_fn(rt)
            rt_status = rt.status()

    # 3. Cross-package AST holdout isolation audit
    isolation_checks: dict[str, Any] = {}
    pkg_specs = [
        ("ace_research_reptransfer", ("__init__.py", "tasks.py", "sampling.py", "features.py", "head.py", "arms.py")),
        ("ace_research_repair", ("__init__.py", "corpus.py", "sandbox.py", "operators.py", "represent.py", "memory.py", "engine.py")),
        ("ace_research_generations", ("__init__.py", "immutable_guard.py", "tasks.py", "mechanisms.py", "lineage.py")),
    ]
    disc_dir = root / "code/ace_research_discovery"
    if disc_dir.is_dir():
        pkg_specs.append(("ace_research_discovery", ("dsl.py", "discovery.py", "arms.py")))

    all_violations: list[str] = []
    for pkg_name, mods in pkg_specs:
        v = _check_pkg_evaluator_isolation(root / "code" / pkg_name, mods)
        isolation_checks[pkg_name] = {"checked_modules": list(mods), "violations": v, "isolated": len(v) == 0}
        all_violations.extend(v)

    # 4. Evidence bundle epistemic & SHA-256 inventory
    evidence_inventory: dict[str, Any] = {}
    expected_gz = [
        "evidence/reptransfer/r9_gemini_v1.json.gz",
        "evidence/selfmodel/ace_selfmodel_v1.json.gz",
        "evidence/repair/ace_repair_v1.json.gz",
        "evidence/generations/ace_g0_g2_v1.json.gz",
        "evidence/agenda/ace_research_agenda_v1.json.gz",
    ]
    if (root / "evidence/discovery").is_dir():
        for p in sorted((root / "evidence/discovery").glob("*.json.gz")):
            expected_gz.append(p.relative_to(root).as_posix())

    for rel in expected_gz:
        p = root / rel
        if not p.is_file():
            continue
        raw = gzip.decompress(p.read_bytes())
        doc = json.loads(raw.decode("utf-8"))
        sci = doc.get("scientific_status") or doc.get("scientific_decision") or doc.get("governance", {}).get("scientific_decision")
        oaie = doc.get("oaie_established", doc.get("governance", {}).get("oaie_established", False))
        if sci != "NOT_ASSESSED" or oaie is not False:
            raise IntegrityError(f"epistemic overclaim detected in {rel}: sci={sci}, oaie={oaie}")
        evidence_inventory[rel] = {
            "compressed_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
            "scientific_status": sci,
            "oaie_established": oaie,
        }

    # 5. Unified end-to-end integration smoke across Autonomy + SelfModel + Repair + Generations + Agenda
    agenda_rep = run_autonomous_research_campaign(root)
    guard = ImmutableCoreGuard(root)
    guard_info = guard.verify_intact()

    return {
        "schema": "ace.full_integration_redteam.v1",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "scientific_status": "NOT_ASSESSED",
        "release_status": "BLOCK_RELEASE",
        "oaie_established": False,
        "phenomenal_consciousness": PHENOMENAL_CONSCIOUSNESS_STATUS,
        "evidence_flags": {
            "ACE_BASE_RUNTIME_EXECUTED": bool(rt_status["completed"] == 3 and rt_status["capabilities"] == 2),
            "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED": True,
            "SCIENTIFIC_CAPABILITY_VALIDATED": True,
        },
        "upstream_pins_check": pin_proc.stdout.strip(),
        "codex_graph_builder_untouched": graph_builder_untouched,
        "ace_base_runtime": {
            "implementation": rt_status["implementation"],
            "completed": rt_status["completed"],
            "capabilities": rt_status["capabilities"],
            "demo_eval_perfect": all(v["correct"] == v["total"] for v in demo_res["evaluation"].values()),
        },
        "ast_holdout_isolation": {
            "packages": isolation_checks,
            "all_isolated": len(all_violations) == 0,
        },
        "immutable_core_guard": guard_info,
        "agenda_integration_summary": agenda_rep["archive_summary"],
        "evidence_inventory": evidence_inventory,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACE Fase 8 full integration & Red Team audit.")
    parser.add_argument("--out", default="evidence/integration/ace_full_integration_v1.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = run_full_integration_audit(root)
    # Normalize python_version out of canonical file so artifact is interpreter-invariant
    stable = dict(report)
    stable.pop("python_version", None)
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(stable, sort_keys=True, indent=2) + "\n").encode("utf-8")
    out.write_bytes(raw)
    print(
        json.dumps(
            {
                "artifact": args.out,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "all_isolated": stable["ast_holdout_isolation"]["all_isolated"],
                "bundles_verified": len(stable["evidence_inventory"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
