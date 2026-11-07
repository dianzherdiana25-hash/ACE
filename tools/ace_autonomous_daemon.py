#!/usr/bin/env python3
"""ACE Autonomous Continuity Daemon Loop (V0.2).

Runs persistent multi-cycle research, state-driven dynamic agenda selection,
isolated evaluation against sealed holdouts, Merkle state chaining,
and automatic GitHub commit/push after each cycle batch.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

from ace_self_dev.coordinator import SelfDevelopmentCoordinator
from ace_self_dev.models import AuthorType
from ace_host_controller.resilient_watchdog import ResilientWatchdog, WatchdogConfig


def log(msg: str):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    formatted = f"[{timestamp}] [Daemon] {msg}"
    print(formatted, flush=True)
    log_file = REPO_ROOT / "checkpoints" / "self_dev" / "daemon.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def git_commit_and_push(cycle_id: int, decision: str, task_id: str):
    """Automatically commit and push completed cycles to GitHub PR #87."""
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
            f"feat(self-dev): autonomous cycle {cycle_id} ({task_id}) [{decision}]\n\n"
            f"- Merkle state chained from prior cycle\n"
            f"- Continuous execution by autonomous background daemon"
        )
        log(f"Committing Cycle {cycle_id}...")
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        branch_res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        branch = branch_res.stdout.strip() or "integration/ace-anti-stagnation-self-repair-20261107"
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


def run_daemon_loop(batch_size: int = 2, sleep_seconds: int = 15):
    """Continuous self-development loop running in background."""
    log("=== ACE Autonomous Daemon Initialized ===")
    log(f"Repository Root: {REPO_ROOT}")
    log(f"Batch Size: {batch_size} cycles | Inter-batch Sleep: {sleep_seconds}s")

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

    coord = SelfDevelopmentCoordinator(
        checkpoint_dir=str(REPO_ROOT / "checkpoints" / "self_dev"),
        evidence_dir=str(REPO_ROOT / "evidence" / "self_dev"),
    )

    iteration = 0
    try:
        while True:
            iteration += 1
            log(f"--- Starting Autonomous Iteration {iteration} (Batch: {batch_size} cycles) ---")

            for step in range(1, batch_size + 1):
                try:
                    res = watchdog.run_guarded_cycle(
                        coord.run_autonomous_cycle,
                        author_type=AuthorType.ACE_AUTONOMOUS_V02,
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
                        f"Step {step}/{batch_size} -> Cycle {cid} Completed: "
                        f"Task={tid}, Gain={gain:+.4f}, Holdout={holdout:.4f}, Decision={dec}, Promoted={promoted}, ActiveHead={head}"
                    )

                    # Halt redundant git commits on rejected/duplicate cycles to prevent repository bloat
                    is_milestone = (cid is not None and cid % 50 == 0)
                    if promoted or is_milestone:
                        git_commit_and_push(cid, dec, tid)
                    else:
                        log(f"Cycle {cid} ({dec}) persisted to local state. Skipping redundant git commit to maintain clean git history.")

                    next_strat = res.get("next_agenda_priority", {}).get("strategy")
                    if next_strat == "SEARCH_SPACE_EXHAUSTED":
                        log("StrategyRepair indicates SEARCH_SPACE_EXHAUSTED: All representation families across all tasks explored.")
                        log("Cleanly halting autonomous daemon loop.")
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

        log(f"Sleeping {sleep_seconds}s before next iteration...")
        time.sleep(sleep_seconds)
    finally:
        log("Halting watchdog background monitor...")
        watchdog.stop_background_monitor()


if __name__ == "__main__":
    run_daemon_loop(batch_size=2, sleep_seconds=15)

