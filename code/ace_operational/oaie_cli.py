"""Unified single-command CLI entrypoint for ACE OAIE-∞ & Passive Evolution Loop.

Usage:
    PYTHONPATH=code python3 -m ace_operational.oaie_cli status
    PYTHONPATH=code python3 -m ace_operational.oaie_cli compositional-oaie
    PYTHONPATH=code python3 -m ace_operational.oaie_cli evolve-plan
    PYTHONPATH=code python3 -m ace_operational.oaie_cli evolve-verify
    PYTHONPATH=code python3 -m ace_operational.oaie_cli evolve-once
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .compositional_oaie import CompositionalOAIERunner
from .evolution_mission_loop import EvolutionPatchVerifier, PassiveEvolutionPlanner
from .neuro_formal_genesis import run_neuro_formal_genesis_cycle
from .oaie_unlimited import run_oaie_unlimited_cycle
from .sovereign_runtime import SovereignRuntimeSupervisor


def _resolve_cli_workspace(args: argparse.Namespace) -> Path:
    """Resolve workspace path, defaulting to ``<repo-root>/.ace_evolution`` or ``./.ace_evolution``."""
    raw = getattr(args, "workspace", None)
    if raw:
        return Path(raw).resolve()
    repo_root = getattr(args, "repo_root", None)
    if repo_root:
        return (Path(repo_root).resolve() / ".ace_evolution").resolve()
    return Path(".ace_evolution").resolve()


def _resolve_passive_workspace(ws: Path) -> Path:
    """Resolve either parent workspace (adding ``passive_evolution``) or a direct work-order dir."""
    if (
        ws.name in {"passive_evolution", ".ace_evolution"}
        or (ws / "EVOLUTION_WORK_ORDER.json").is_file()
        or (ws / "evolution_state.json").is_file()
    ):
        return ws
    return ws / "passive_evolution"


def _dispatch_evolve_command(args: argparse.Namespace, ws: Path) -> dict[str, Any] | None:
    if args.command == "evolve-plan":
        passive_ws = _resolve_passive_workspace(ws)
        planner = PassiveEvolutionPlanner(
            passive_ws,
            Path(args.repo_root),
            scan_subpath=args.scan_subpath,
        )
        comp_report = args.compositional_report
        if comp_report is None:
            candidate = ws / "compositional_oaie" / "compositional_oaie_report.json"
            if candidate.is_file():
                comp_report = str(candidate)
        return planner.plan_next_evolution(
            test_modules=args.test_modules,
            compositional_report_path=comp_report,
        )

    if args.command == "evolve-verify":
        verifier = EvolutionPatchVerifier(_resolve_passive_workspace(ws), Path(args.repo_root))
        return verifier.verify_and_ratify_evolution(extra_checks=args.extra_checks)

    if args.command == "evolve-once":
        from .autonomous_evolver import AutonomousEvolver

        return AutonomousEvolver(ws / "evolver", repo_root=args.repo_root).run_evolution_generation(
            args.generation_id,
            include_compositional_oaie=not args.skip_compositional,
        )

    if args.command == "evolve-multi":
        from .autonomous_evolver import AutonomousEvolver

        return AutonomousEvolver(ws / "evolver", repo_root=args.repo_root).run_multi_generation_loop(
            generations=args.generations,
            include_compositional_oaie=not args.skip_compositional,
        )
    return None


def _dispatch_runtime_command(args: argparse.Namespace, ws: Path) -> dict[str, Any]:
    if args.command == "status":
        rt_dir = ws / "runtime" if (ws / "evolution_state.json").is_file() or (ws / "EVOLUTION_WORK_ORDER.json").is_file() else ws
        sup = SovereignRuntimeSupervisor(rt_dir)
        return {
            "schema": "ace.oaie_cli.status.v1",
            "workspace": str(ws),
            "runtime_state": sup.state,
            "dag_chain_valid": sup.dag.verify_chain(),
            "dag_nodes": len(sup.dag.nodes()),
        }

    if args.command == "run-cycle":
        sup = SovereignRuntimeSupervisor(ws)
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

    if args.command == "compositional-oaie":
        return CompositionalOAIERunner(
            ws / "compositional_oaie",
            max_candidates=args.max_candidates,
            timeout_sec=args.timeout_sec,
        ).run(include_falsification=not args.no_falsification)

    if args.command == "verify-spore":
        from .sovereign_runtime import SubstrateSpore

        return SubstrateSpore.import_and_verify_spore(
            spore_path=args.spore_path,
            target_workspace=ws / "spore_verify_probe",
            expected_ancestor_skills=["core_stage2_guard"],
            antibody_probes=[],
        )

    if args.command == "work-order":
        sup = SovereignRuntimeSupervisor(ws)
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


def run_cli_action(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch CLI subcommand against the resolved workspace."""
    ws = _resolve_cli_workspace(args)
    ws.mkdir(parents=True, exist_ok=True)
    evolve_out = _dispatch_evolve_command(args, ws)
    if evolve_out is not None:
        return evolve_out
    return _dispatch_runtime_command(args, ws)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for ACE OAIE-∞ CLI."""
    parser = argparse.ArgumentParser(prog="ace-oaie", description="ACE OAIE-∞ & Passive Evolution CLI")
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace directory (defaults to <repo-root>/.ace_evolution or ./.ace_evolution)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Inspect sovereign runtime & stigmergic DAG status")

    rc = sub.add_parser("run-cycle", help="Run OAIE-Unlimited + Neuro-Formal Genesis + Runtime cycles")
    rc.add_argument("--seed", type=int, default=20261114)
    rc.add_argument("--cycles", type=int, default=3)

    co = sub.add_parser("compositional-oaie", help="Run zero-theater 4-arm Compositional OAIE benchmark")
    co.add_argument("--max-candidates", type=int, default=160000)
    co.add_argument("--timeout-sec", type=float, default=2.0)
    co.add_argument("--no-falsification", action="store_true")

    ep = sub.add_parser("evolve-plan", help="Audit repo & emit AI-agnostic EVOLUTION_WORK_ORDER.{json,md}")
    ep.add_argument("--repo-root", default=".")
    ep.add_argument("--scan-subpath", default="code")
    ep.add_argument("--test-module", dest="test_modules", action="append")
    ep.add_argument("--compositional-report", default=None)

    ev_ver = sub.add_parser("evolve-verify", help="Verify AI edits fail-closed & ratify into DAG + Spore")
    ev_ver.add_argument("--repo-root", default=".")
    ev_ver.add_argument("--check", dest="extra_checks", action="append")

    ev = sub.add_parser("evolve-once", help="Run a unified zero-theater self-evolution generation")
    ev.add_argument("--generation-id", default="gen-1")
    ev.add_argument("--repo-root", default=None)
    ev.add_argument("--skip-compositional", action="store_true")

    em = sub.add_parser("evolve-multi", help="Run N generations with Succession Continuity Exams")
    em.add_argument("--generations", type=int, default=2)
    em.add_argument("--repo-root", default=None)
    em.add_argument("--skip-compositional", action="store_true")

    vs = sub.add_parser("verify-spore", help="Verify a SubstrateSpore bundle via Succession Continuity Exam")
    vs.add_argument("--spore-path", required=True)

    wo = sub.add_parser("work-order", help="Emit a deterministic zero-API Work Order")
    wo.add_argument("--order-id", required=True)
    wo.add_argument("--goal", required=True)
    wo.add_argument("--target-file", dest="target_files", action="append")
    wo.add_argument("--check", dest="checks", action="append")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
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
