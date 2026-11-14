"""Unified single-command CLI entrypoint for ACE OAIE-∞ (Epochs A–F).

Usage:
    PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace /tmp/ace_ws status
    PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace /tmp/ace_ws run-cycle
    PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace /tmp/ace_ws factory
    PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace /tmp/ace_ws work-order --order-id wo-1 --goal "..."
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .commercial_product_factory import run_commercial_factory_cycle
from .neuro_formal_genesis import run_neuro_formal_genesis_cycle
from .oaie_unlimited import run_oaie_unlimited_cycle
from .sovereign_runtime import SovereignRuntimeSupervisor


def run_cli_action(args: argparse.Namespace) -> dict[str, Any]:
    ws = Path(args.workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    sup = SovereignRuntimeSupervisor(ws)

    if args.command == "status":
        return {
            "schema": "ace.oaie_cli.status.v1",
            "workspace": str(ws),
            "runtime_state": sup.state,
            "dag_chain_valid": sup.dag.verify_chain(),
            "dag_nodes": len(sup.dag.nodes()),
        }

    if args.command == "run-cycle":
        unlimited = run_oaie_unlimited_cycle(ws / "unlimited", seed=args.seed)
        genesis = run_neuro_formal_genesis_cycle()
        rt = sup.run_until_health(
            target_health=0.8,
            max_cycles=args.cycles,
            task_factory=lambda idx: {
                "task_id": f"cli_cycle_{args.seed}_{idx}",
                "expected_benefit": 1.0,
                "estimated_dt": 0.4,
                "remaining_budget_ratio": 1.0,
            },
        )
        return {
            "schema": "ace.oaie_cli.run_cycle.v1",
            "verified_unlimited_ok": unlimited["verified_unlimited_ok"],
            "unlimited_replay_digest": unlimited["unlimited_replay_digest"],
            "synthesized_skills": genesis["skills_synthesized"],
            "runtime_health": rt["final_health"],
            "unhandled_crashes": rt["unhandled_crashes"],
        }

    if args.command == "factory":
        return run_commercial_factory_cycle(ws / "commercial")

    if args.command == "evolve-once":
        from .autonomous_evolver import AutonomousEvolver

        return AutonomousEvolver(ws / "evolver").run_evolution_generation(args.generation_id)

    if args.command == "evolve-multi":
        from .autonomous_evolver import AutonomousEvolver

        return AutonomousEvolver(ws / "evolver").run_multi_generation_loop(generations=args.generations)

    if args.command == "verify-spore":
        from .sovereign_runtime import SubstrateSpore

        return SubstrateSpore.import_and_verify_spore(
            spore_path=args.spore_path,
            target_workspace=ws / "spore_verify_probe",
            expected_ancestor_skills=["core_stage2_guard"],
            antibody_probes=[],
        )

    if args.command == "work-order":
        return sup.work_bridge.export_work_order(
            order_id=args.order_id,
            goal=args.goal,
            target_files=args.target_files or [],
            acceptance_checks=args.checks or ["unittest", "verify_sources.py"],
            forbidden_paths=[
                "code/ace_runtime/",
                "code/ace_mission/",
                "docs/UPSTREAM_SOURCES.json",
                "evidence/",
            ],
        )

    raise ValueError(f"Unknown command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ace-oaie", description="ACE OAIE-∞ Sovereign CLI")
    parser.add_argument("--workspace", default="/tmp/ace_oaie_workspace", help="Workspace directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Inspect sovereign runtime & stigmergic DAG status")

    rc = sub.add_parser("run-cycle", help="Run OAIE-Unlimited + Neuro-Formal Genesis + Runtime cycles")
    rc.add_argument("--seed", type=int, default=20261114)
    rc.add_argument("--cycles", type=int, default=3)

    sub.add_parser("factory", help="Build commercial CLI deliverables & O(1) B2A receipts")

    ev = sub.add_parser("evolve-once", help="Run a unified Epochs A-F self-evolution generation")
    ev.add_argument("--generation-id", default="gen-1")

    em = sub.add_parser("evolve-multi", help="Run N generations with Succession Continuity Exams")
    em.add_argument("--generations", type=int, default=2)

    vs = sub.add_parser("verify-spore", help="Verify a SubstrateSpore bundle via Succession Continuity Exam")
    vs.add_argument("--spore-path", required=True)

    wo = sub.add_parser("work-order", help="Emit a deterministic zero-API Work Order")
    wo.add_argument("--order-id", required=True)
    wo.add_argument("--goal", required=True)
    wo.add_argument("--target-file", dest="target_files", action="append")
    wo.add_argument("--check", dest="checks", action="append")
    return parser


def main(argv: list[str] | None = None) -> int:
    import contextlib
    import io

    parser = build_parser()
    args = parser.parse_args(argv)
    with contextlib.redirect_stdout(io.StringIO()):
        out = run_cli_action(args)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
