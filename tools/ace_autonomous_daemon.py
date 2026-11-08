#!/usr/bin/env python3
"""ACE Autonomous Continuity & Software Researcher Daemon (V0.3).

Runs continuous or bounded autonomous research cycles:
- Problem selection & hypothesis formulation from code & failure diagnostics
- Code patch synthesis and AST validation
- Isolated worktree execution & regression testing
- Independent evaluation against sealed holdouts and negative controls
- Autonomous git branch & pull request management
- Merkle state chaining and persistent research state checkpointing
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

from ace_self_dev.coordinator import SelfDevelopmentCoordinator
from ace_self_dev.models import AuthorType
from ace_host_controller.resilient_watchdog import ResilientWatchdog, WatchdogConfig
from ace_code_agent.controller import AutonomousSoftwareResearcher


def log(msg: str):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    formatted = f"[{timestamp}] [Daemon] {msg}"
    print(formatted, flush=True)
    log_file = REPO_ROOT / "checkpoints" / "self_dev" / "daemon.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def get_current_branch() -> str:
    try:
        branch_res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return branch_res.stdout.strip() or "integration/ace-autonomous-self-dev-bootstrap-v03-20261107"
    except Exception:
        return "integration/ace-autonomous-self-dev-bootstrap-v03-20261107"


def git_commit_and_push(cycle_id: int, decision: str, task_or_problem_id: str):
    """Automatically commit and push state milestones or promotions to remote."""
    try:
        log(f"Staging artifacts and state for Cycle {cycle_id}...")
        subprocess.run(
            ["git", "add", "checkpoints/", "evidence/", "code/", "docs/", "tools/"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        if not status.stdout.strip():
            log("No changes to commit.")
            return

        commit_msg = (
            f"feat(self-dev): autonomous cycle {cycle_id} ({task_or_problem_id}) [{decision}]\n\n"
            f"- Merkle state chained from prior cycle\n"
            f"- Continuous execution by autonomous background daemon V0.3"
        )
        log(f"Committing Cycle {cycle_id}...")
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        branch = get_current_branch()
        log(f"Pushing to origin/{branch}...")
        push_res = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if push_res.returncode == 0:
            log(f"Push successful for Cycle {cycle_id}.")
        else:
            log(f"Push warning: {push_res.stderr.strip()}")
    except Exception as e:
        log(f"Git push error (non-fatal, continuing loop): {e}")


def run_researcher_cycle(
    researcher: AutonomousSoftwareResearcher,
    auto_pr: bool = False,
) -> Dict[str, Any]:
    """Runs a single software development research cycle."""
    log("Executing Autonomous Software-Development Research Cycle...")
    res = researcher.execute_autonomous_cycle(auto_pr=auto_pr)
    prob_title = res.get("problem", {}).get("title", "Unknown Problem")
    hyp_stmt = res.get("hypothesis", {}).get("statement", "Unknown Hypothesis")
    decision = res.get("decision", "UNKNOWN")
    log(f"  Problem:    {prob_title}")
    log(f"  Hypothesis: {hyp_stmt}")
    log(f"  Decision:   {decision}")
    if res.get("pr_metadata"):
        branch_name = res["pr_metadata"].get("branch_name")
        pr_url = res["pr_metadata"].get("pr_url")
        pr_num = res["pr_metadata"].get("pr_number")
        log(f"  PR Branch Created: {branch_name}")
        if pr_url:
            log(f"  GitHub PR Created: {pr_url} (#{pr_num})")
    return res


def run_parameter_cycle(
    watchdog: ResilientWatchdog,
    coord: SelfDevelopmentCoordinator,
    author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
) -> Dict[str, Any]:
    """Runs a single parameter / representation exploration cycle."""
    res = watchdog.run_guarded_cycle(
        coord.run_autonomous_cycle,
        author_type=author_type,
        timeout_seconds=60.0,
        fallback_on_timeout=True,
    )
    cid = res.get("cycle_id")
    dec = res.get("decision")
    tid = res.get("target_task_id") or res.get("hypothesis", {}).get("target_task_id", "unknown")
    gain = res.get("gain_over_parent", 0.0)
    holdout = res.get("holdout_score", 0.0)
    promoted = res.get("is_promoted", False)
    head = res.get("active_head_id")
    log(
        f"  Cycle {cid} (Param): Task={tid}, Gain={gain:+.4f}, Holdout={holdout:.4f}, "
        f"Decision={dec}, Promoted={promoted}, ActiveHead={head}"
    )
    return res


def run_daemon_loop(
    mode: str = "researcher",
    max_cycles: int = 0,
    batch_size: int = 2,
    sleep_seconds: int = 15,
    auto_pr: bool = True,
):
    """Main daemon loop running continuous or bounded research iterations."""
    log("=== ACE Autonomous Daemon V0.3 Initialized ===")
    log(f"Repository Root: {REPO_ROOT}")
    log(f"Mode: {mode.upper()} | Max Cycles: {max_cycles if max_cycles > 0 else 'Continuous'}")
    log(f"Batch Size: {batch_size} | Inter-batch Sleep: {sleep_seconds}s | Auto-PR: {auto_pr}")

    watchdog = ResilientWatchdog(
        WatchdogConfig(
            state_dir=str(REPO_ROOT / "checkpoints" / "self_dev"),
            diagnostic_dir=str(REPO_ROOT / "evidence" / "self_dev" / "diagnostics"),
            heartbeat_file="daemon_heartbeat.json",
            cycle_timeout_seconds=60.0,
            heartbeat_interval_seconds=15.0,
        )
    )

    log("Verifying persistent research state integrity...")
    valid_state = watchdog.ensure_valid_state()
    cycle_cnt = valid_state.get("cycle_count", 0)
    state_dig = str(valid_state.get("state_digest", ""))[:16]
    log(f"State verified: CycleCount={cycle_cnt}, Digest={state_dig}...")

    watchdog.start_background_monitor()

    researcher = AutonomousSoftwareResearcher(repo_root=REPO_ROOT)
    coord = SelfDevelopmentCoordinator(
        checkpoint_dir=str(REPO_ROOT / "checkpoints" / "self_dev"),
        evidence_dir=str(REPO_ROOT / "evidence" / "self_dev"),
    )

    iteration = 0
    total_completed = 0

    try:
        while True:
            iteration += 1
            log(f"--- Starting Autonomous Iteration {iteration} (Batch: {batch_size} cycles) ---")

            for step in range(1, batch_size + 1):
                try:
                    if mode in ("researcher", "hybrid"):
                        # Primary: Autonomous Software-Development Research
                        r_res = run_researcher_cycle(researcher, auto_pr=auto_pr)
                        total_completed += 1
                        r_dec = r_res.get("decision", "REJECTED")
                        prob_id = r_res.get("problem", {}).get("problem_id", "prob")
                        r_cid = r_res.get("cycle", total_completed)
                        if r_dec == "ACCEPTED":
                            git_commit_and_push(r_cid, r_dec, prob_id)

                    if mode in ("parameter", "hybrid"):
                        # Representation Parameter search
                        p_res = run_parameter_cycle(watchdog, coord)
                        total_completed += 1
                        p_cid = p_res.get("cycle_id")
                        p_dec = p_res.get("decision")
                        p_tid = p_res.get("target_task_id") or "param_task"
                        p_promoted = p_res.get("is_promoted", False)

                        is_milestone = (p_cid is not None and p_cid % 50 == 0)
                        if p_promoted or is_milestone:
                            git_commit_and_push(p_cid, p_dec, p_tid)

                    if max_cycles > 0 and total_completed >= max_cycles:
                        log(f"Target max_cycles ({max_cycles}) reached. Cleanly terminating daemon loop.")
                        return

                except Exception as e:
                    log(f"Error in cycle execution: {e}")
                    time.sleep(5)

            log(f"Iteration {iteration} complete. Running external verifier...")
            try:
                ver = subprocess.run(
                    [sys.executable, str(REPO_ROOT / "tools" / "verify_self_dev.py")],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if ver.returncode == 0:
                    log("External verifier: ALL CHECKS PASSED.")
                else:
                    log(f"External verifier output: {ver.stdout[-300:]}")
            except Exception as ve:
                log(f"Verifier error: {ve}")

            if max_cycles > 0 and total_completed >= max_cycles:
                return

            log(f"Active heartbeat maintained. Sleeping {sleep_seconds}s before next iteration...")
            time.sleep(sleep_seconds)

    finally:
        log("Halting watchdog background monitor...")
        watchdog.stop_background_monitor()


def main():
    parser = argparse.ArgumentParser(description="ACE Autonomous Continuity & Software Researcher Daemon (V0.3)")
    parser.add_argument("--mode", choices=["researcher", "parameter", "hybrid"], default="researcher", help="Operating mode")
    parser.add_argument("--max-cycles", type=int, default=0, help="Maximum cycles to execute (0 for continuous loop)")
    parser.add_argument("--batch-size", type=int, default=1, help="Cycles per iteration batch")
    parser.add_argument("--sleep-seconds", type=int, default=15, help="Sleep duration between batches")
    parser.add_argument("--auto-pr", action="store_true", default=False, help="Automatically create git branch and PR on promotion")
    args = parser.parse_args()

    run_daemon_loop(
        mode=args.mode,
        max_cycles=args.max_cycles,
        batch_size=args.batch_size,
        sleep_seconds=args.sleep_seconds,
        auto_pr=args.auto_pr,
    )


if __name__ == "__main__":
    main()
