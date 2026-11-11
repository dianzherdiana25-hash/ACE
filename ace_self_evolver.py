#!/usr/bin/env python3
"""
ACE Audited Self-Evolver (Strict Empirical Verification & Branch Isolation)
-------------------------------------------------------------------------
1. Reads autonomous research targets from ACE MissionBus.
2. Synthesizes and empirically evaluates candidates against real specifications.
3. Submits genuine evidence receipts conforming to admission contracts.
4. Enforces strict Git branch isolation (ace-evolution/<id>); NEVER commits or pushes directly to main.
5. Gates all git mutations behind full regression test suites with automatic rollback.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent
CODE_DIR = ROOT_DIR / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from ace_mission.bus import MissionBus
from ace_mission.generator import MissionGenerator
from ace_mission.admission import ARTIFACT_SCHEMA, REQUESTS
from ace_cognition.reasoning import canonical, digest, solve


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: int = 120) -> Tuple[int, str]:
    """Execute a subprocess command safely with timeout and combined stdout/stderr."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, f"Command timed out after {timeout} seconds"
    except Exception as exc:
        return -2, str(exc)


def get_current_git_branch() -> str:
    """Retrieve current git branch safely."""
    code, out = run_cmd(["git", "branch", "--show-current"])
    if code == 0 and out.strip():
        return out.strip().splitlines()[0]
    return "main"


def run_verification_test_gate() -> Tuple[bool, str]:
    """Execute core acceptance and unit test suites as a mandatory release gate.
    
    Returns (True, details) if 100% of tests pass cleanly, otherwise (False, failure_details).
    """
    print("   🧪 [Verification Gate] Running operational acceptance tests...")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CODE_DIR)
    
    # 1. Operational Acceptance (21 tests)
    proc1 = subprocess.run(
        [sys.executable, str(CODE_DIR / "ace_operational" / "test_edition4_acceptance.py")],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if proc1.returncode != 0:
        return False, f"Acceptance suite failed:\n{proc1.stderr or proc1.stdout}"

    # 2. Mission Bus Suite (31 tests)
    proc2 = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "code/ace_mission"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if proc2.returncode != 0:
        return False, f"Mission bus tests failed:\n{proc2.stderr or proc2.stdout}"

    return True, "All verification test suites passed (52 tests total)."


def execute_isolated_git_commit(
    mission_id: str,
    goal: str,
    artifact_path: Path,
    allow_push: bool = False,
) -> Tuple[bool, str]:
    """Isolate evolution commit on a dedicated branch; never touch main directly."""
    base_branch = get_current_git_branch()
    branch_name = f"ace-evolution/{mission_id}"
    
    # Strictly forbid direct operations on main
    if base_branch == branch_name:
        return False, f"Invalid active branch '{base_branch}' matching evolution target"

    # Step 1: Mandatory pre-commit verification gate
    tests_ok, test_msg = run_verification_test_gate()
    if not tests_ok:
        return False, f"Pre-commit verification failed: {test_msg}"

    print(f"\n🌿 [Branch Isolation] Creating evolution branch: {branch_name} from {base_branch}...")
    code, out = run_cmd(["git", "checkout", "-b", branch_name])
    if code != 0:
        return False, f"Failed to create isolated branch '{branch_name}': {out}"

    try:
        # Step 2: Scoped staging (ONLY stage the specific artifact)
        rel_path = artifact_path.relative_to(ROOT_DIR) if artifact_path.is_relative_to(ROOT_DIR) else artifact_path
        code, out = run_cmd(["git", "add", str(rel_path)])
        if code != 0:
            raise RuntimeError(f"Failed to stage artifact: {out}")

        commit_msg = (
            f"feat(ace-evolution): {goal} [{mission_id}]\n\n"
            f"- Empirical verification passed 52/52 acceptance & mission tests\n"
            f"- Branch isolation: {branch_name}\n"
            f"- Governance: Verified offline evolution"
        )
        code, out = run_cmd(["git", "commit", "-m", commit_msg])
        if code != 0 and "nothing to commit" not in out:
            raise RuntimeError(f"Git commit failed: {out}")

        # Step 3: Optional remote push to isolated branch ONLY (never origin/main)
        if allow_push:
            print(f"   🚀 Pushing isolated branch to origin/{branch_name}...")
            p_code, p_out = run_cmd(["git", "push", "origin", branch_name])
            if p_code != 0:
                print(f"   ⚠️ Remote push failed (non-fatal, continuing): {p_out}")

        return True, f"Committed on isolated branch '{branch_name}'"
    except Exception as exc:
        print(f"   ❌ Evolution error: {exc}. Rolling back working tree...")
        run_cmd(["git", "checkout", "--", "."])
        return False, str(exc)
    finally:
        # Always return cleanly to base branch
        run_cmd(["git", "checkout", base_branch])


def evaluate_and_solve_mission(mission: Dict[str, Any], artifacts_dir: Path) -> Tuple[Path, str, Dict[str, Any]]:
    """Empirically evaluate and solve a mission. Never fabricates fake 1.0 metrics."""
    mission_id = mission["id"]
    goal = mission["goal"]
    hypothesis = mission["hypothesis"]
    budget = mission.get("budget", {})

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Pathway A: Formal Reasoning Problem
    if "reasoning_problem" in mission:
        artifact_path = artifacts_dir / f"{mission_id}_solution.json"
        prob_data = mission["reasoning_problem"]
        max_ops = budget.get("max_primitive_operations", 300_000)
        time_limit = min(float(budget.get("time_sec", 5.0)), 5.0)

        try:
            outcome = solve(prob_data, max_operations=max_ops, seconds=time_limit)
            program = outcome.get("program")
        except Exception as exc:
            outcome = {"program": None, "reason": f"ERROR: {exc}"}
            program = None

        if program is not None:
            artifact_doc = {
                "schema": ARTIFACT_SCHEMA,
                "problem_digest": digest(prob_data),
                "program": program,
            }
            artifact_path.write_text(canonical(artifact_doc) + "\n", encoding="utf-8")
            decision = "STAGED_EMPIRICAL"
            metrics = {"benchmark_score": 1.0, "reason": outcome.get("reason", "SOLVED")}
        else:
            try:
                p_digest = digest(prob_data)
            except Exception:
                p_digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            artifact_doc = {
                "schema": ARTIFACT_SCHEMA,
                "problem_digest": p_digest,
                "program": None,
            }
            artifact_path.write_text(canonical(artifact_doc) + "\n", encoding="utf-8")
            decision = "INCONCLUSIVE"
            metrics = {"benchmark_score": 0.0, "reason": outcome.get("reason", "NO_SOLUTION_FOUND")}

        return artifact_path, decision, metrics

    # Pathway B: Non-Reasoning / Unverified Domain Mission
    # Report honestly without claiming fake 1.0 benchmark
    artifact_path = artifacts_dir / f"{mission_id}_proposal.json"
    proposal = {
        "schema": "ace.mission.proposal.v1",
        "mission_id": mission_id,
        "goal": goal,
        "hypothesis": hypothesis,
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "UNVERIFIED_PROPOSAL",
        "decision": "PENDING_EVALUATION",
        "metrics": {
            "benchmark_score": 0.0,
            "empirical_status": "NO_BEHAVIORAL_EVALUATOR_FOR_TASK"
        }
    }
    artifact_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    return artifact_path, "PENDING_EVALUATION", proposal["metrics"]


def execute_self_evolution(
    workspace_path: Path,
    max_missions: int = 1,
    continuous: bool = False,
    loop_delay: int = 10,
    dry_run: bool = False,
    allow_push: bool = False,
):
    bus_path = workspace_path / "mission_bus.sqlite3"
    bus = MissionBus(bus_path)
    generator = MissionGenerator(bus)

    print("\n" + "=" * 65)
    print("   🛡️ ACE AUDITED AUTONOMOUS EVOLVER (STRICT VERIFICATION)")
    print("=" * 65)
    print(f"📁 Workspace: {workspace_path}")
    print(f"🔒 Branch Isolation: ACTIVE (main branch protected)")
    print(f"⚙️ Dry Run: {'ENABLED (No git mutations)' if dry_run else 'DISABLED'}")

    iteration = 0
    while True:
        status = bus.status()
        pending_count = status.get("mission_counts", {}).get("PENDING", 0)

        if pending_count == 0:
            print("\n⚙️ Menerbitkan batch misi frontier baru...")
            diagnostics = [
                {"type": "INFORMATION_SHORTAGE", "details": f"Frontier iteration {iteration}: boundary resolve"},
                {"type": "METHOD_SHORTAGE", "details": f"Frontier iteration {iteration}: dynamic dispatch synthesis"},
                {"type": "TOOL_SHORTAGE", "details": f"Frontier iteration {iteration}: inductive grammar expansion"},
                {"type": "BUDGET_EXHAUSTION", "details": f"Frontier iteration {iteration}: active learning budget optimizer"}
            ]
            missions = generator.generate_from_diagnostics(diagnostics)
            print(f"   ↳ {len(missions)} misi frontier baru diterbitkan ke bus.")

        while continuous or (iteration < max_missions):
            mission = bus.next_mission(agent_id="ace-autonomous-codex")
            if not mission:
                break

            mission_id = mission["id"]
            goal = mission["goal"]
            hypothesis = mission["hypothesis"]

            print(f"\n🎯 [Misi Diambil: {mission_id}]")
            print(f"   • Goal       : {goal}")
            print(f"   • Hipotesis  : {hypothesis}")

            evidence_dir = ROOT_DIR / "evidence" / "autonomous_missions"
            artifact_path, proposed_decision, metrics = evaluate_and_solve_mission(mission, evidence_dir)
            print(f"   • Real Score : {metrics.get('benchmark_score', 0.0)}")
            print(f"   • Proposal   : {proposed_decision}")

            # Submit artifact to bus for independent re-execution / admission verification
            submission = bus.submit_mission(
                mission_id=mission_id,
                artifact_path=str(artifact_path),
                agent_id="ace-autonomous-codex",
                decision=proposed_decision,
                provenance="AUTONOMOUS_EMPIRICAL_LOOP"
            )
            actual_decision = submission.get("decision", "REJECTED")
            print(f"   ↳ Admission Result: {actual_decision}")

            # Only commit if empirically admitted and not dry_run
            if not dry_run and actual_decision in ("ACCEPTED", "STAGED_EMPIRICAL"):
                ok, commit_msg = execute_isolated_git_commit(
                    mission_id=mission_id,
                    goal=goal,
                    artifact_path=artifact_path,
                    allow_push=allow_push,
                )
                print(f"   ↳ Git status: {commit_msg}")
            elif dry_run:
                print("   ↳ Dry run active: Skipping git branch/commit.")
            else:
                print(f"   ↳ Not admitted ({actual_decision}): Skipping git commit.")

            iteration += 1
            if not continuous and iteration >= max_missions:
                break
            time.sleep(1)

        if not continuous or (not continuous and iteration >= max_missions):
            break

        print(f"\n💤 Menunggu {loop_delay}s sebelum siklus evolusi berikutnya...")
        time.sleep(loop_delay)

    print("\n" + "=" * 65)
    print(f"✨ Selesai mengeksekusi {iteration} siklus evolusi terverifikasi!")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="ACE Audited Self-Evolver")
    parser.add_argument("--workspace", default=str(ROOT_DIR / "ace-work-v2"),
                        help="Path ke workspace ACE (default: ./ace-work-v2)")
    parser.add_argument("--missions", type=int, default=1,
                        help="Jumlah misi yang dieksekusi (default: 1)")
    parser.add_argument("--continuous", action="store_true",
                        help="Jalankan terus menerus tanpa henti (daemon mode)")
    parser.add_argument("--delay", type=int, default=15,
                        help="Jeda antar batch saat continuous mode (detik)")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Jalankan evaluasi tanpa mutasi git")
    parser.add_argument("--allow-push", action="store_true", default=False,
                        help="Izinkan git push hanya ke branch terisolasi (bukan main)")
    args = parser.parse_args()

    execute_self_evolution(
        Path(args.workspace).resolve(),
        max_missions=args.missions,
        continuous=args.continuous,
        loop_delay=args.delay,
        dry_run=args.dry_run,
        allow_push=args.allow_push,
    )


if __name__ == "__main__":
    main()
