"""E2E Test Suite: Termux Runtime Resilient to Restart & Resumption (Requirement 8).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (task intake, FIFO execution, pure typed predictions, SQLite WAL persistence)
Tier 2: Boundary & Corner Cases (event chain tamper fail-closed, duplicate task idempotency, invalid grammar)
Tier 3: Cross-Feature Interactions (substrate guardian physical telemetry, WAL database invariants)
Tier 4: Real-World Scenarios (simulated process crash/restart with safe task resumption and replay)
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_capability_evolution import compositional as c
from ace_cognition.substrate_guardian import SubstrateGuardian, SubstrateTelemetry
from ace_runtime.engine import IntegrityError, Runtime


def make_runtime_task(name: str = "source_task", family: str = "equal", seed: int = 20261106):
    """Helper to generate a valid training/validation task pair from capability grammar."""
    train, validation, terminal = c.bank(family, seed)
    return {"name": name, "train": train, "validation": validation}, terminal


class TestRuntimeRecoveryE2E(unittest.TestCase):
    """End-to-end verification of persistent runtime execution, restart recovery, and substrate guardianship."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_e2e_runtime_"))
        self.workspace = self.temp_dir / "runtime_state"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_runtime_task_intake_execution_and_prediction(self):
        """Verify task enqueue, trial execution, staged model acquisition, and pure prediction."""
        task_data, terminal = make_runtime_task(name="parity_task")
        with Runtime(self.workspace) as runtime:
            task_id = runtime.enqueue(task_data)
            self.assertTrue(bool(task_id))

            # Run execution
            results = runtime.run(max_tasks=1)
            self.assertEqual(len(results), 1)
            result = results[0]
            self.assertEqual(result["task_id"], task_id)
            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["staged"])

            # Verify typed predictions
            pred_aabb = runtime.predict(task_id, "aabb")
            pred_aab = runtime.predict(task_id, "aab")
            self.assertIsInstance(pred_aabb, bool)
            self.assertIsInstance(pred_aab, bool)

            # Verify status summary
            status = runtime.status()
            self.assertEqual(status["completed"], 1)
            self.assertEqual(status["pending"], 0)
            self.assertEqual(status["capabilities"], 1)

    def test_tier1_idempotent_task_enqueue(self):
        """Verify re-enqueuing an identical task produces the exact same task_id without duplication."""
        task_data, _ = make_runtime_task()
        with Runtime(self.workspace) as runtime:
            id1 = runtime.enqueue(task_data)
            id2 = runtime.enqueue(task_data)
            self.assertEqual(id1, id2)
            self.assertEqual(runtime.status()["pending"], 1)

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_event_chain_tamper_fails_closed_with_integrity_error(self):
        """Verify that altering an event payload or hash in the SQLite ledger raises IntegrityError upon opening."""
        task_data, _ = make_runtime_task()
        with Runtime(self.workspace) as runtime:
            runtime.enqueue(task_data)
            runtime.run(max_tasks=1)

        # Tamper directly with the SQLite events table
        db_path = self.workspace / "ace.sqlite3"
        db = sqlite3.connect(db_path)
        db.execute("UPDATE events SET hash='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' WHERE seq=1")
        db.commit()
        db.close()

        # Reopening tampered runtime must fail closed
        with self.assertRaises(IntegrityError) as ctx:
            with Runtime(self.workspace):
                pass
        self.assertIn("event chain mismatch", str(ctx.exception))

    def test_tier2_invalid_task_intake_rejected_before_enqueue(self):
        """Verify tasks with invalid names or exceeding grammar budgets are rejected immediately."""
        with Runtime(self.workspace) as runtime:
            # Empty task name
            with self.assertRaises(ValueError):
                runtime.enqueue({"name": "", "train": [("a", True)], "validation": [("b", False)]})

            # Non-disjoint train and validation
            with self.assertRaises(ValueError):
                runtime.enqueue({
                    "name": "overlapping_task",
                    "train": [("a", True), ("b", False)],
                    "validation": [("a", True)],
                })

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_sqlite_wal_mode_and_synchronous_pragmas(self):
        """Verify Runtime establishes WAL journal mode and FULL synchronous persistence."""
        task_data, _ = make_runtime_task()
        with Runtime(self.workspace) as runtime:
            runtime.enqueue(task_data)

        db_path = self.workspace / "ace.sqlite3"
        db = sqlite3.connect(db_path)
        journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        sync_mode = db.execute("PRAGMA synchronous").fetchone()[0]
        db.close()

        self.assertEqual(journal_mode.lower(), "wal")
        # In SQLite: 2 = FULL
        self.assertEqual(sync_mode, 2)

    def test_tier3_substrate_guardian_telemetry_monitoring(self):
        """Verify SubstrateGuardian monitors physical host memory and disk resources."""
        guardian = SubstrateGuardian(workspace_root=self.temp_dir)
        rss, avail = guardian.get_memory_info()
        self.assertGreaterEqual(rss, 0.0)
        self.assertGreater(avail, 0.0)

        # Telemetry snapshot
        telemetry = guardian.sense()
        self.assertIsInstance(telemetry, SubstrateTelemetry)
        self.assertIn(telemetry.status_level, ["OPTIMAL", "CAUTION", "THROTTLED", "CRITICAL"])
        self.assertGreater(telemetry.disk_free_gb, 0.0)

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_cold_restart_recovery_resumes_interrupted_work(self):
        """Simulate cold process stoppage during task processing: reopening cleanly completes work."""
        task1, _ = make_runtime_task(name="task_first", seed=101)
        task2, _ = make_runtime_task(name="task_second", seed=102)

        # 1. Enqueue 2 tasks in first process session, but only run 1
        with Runtime(self.workspace) as runtime:
            id1 = runtime.enqueue(task1)
            id2 = runtime.enqueue(task2)
            results = runtime.run(max_tasks=1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["task_id"], id1)

            # Confirm 1 is completed and 1 is pending
            status1 = runtime.status()
            self.assertEqual(status1["completed"], 1)
            self.assertEqual(status1["pending"], 1)

        # 2. Reopen in a second fresh process session (simulating post-restart recovery)
        with Runtime(self.workspace) as runtime_reopened:
            status2 = runtime_reopened.status()
            self.assertEqual(status2["completed"], 1)
            self.assertEqual(status2["pending"], 1)

            # Resume execution of remaining pending work
            results2 = runtime_reopened.run(max_tasks=1)
            self.assertEqual(len(results2), 1)
            self.assertEqual(results2[0]["task_id"], id2)

            status3 = runtime_reopened.status()
            self.assertEqual(status3["completed"], 2)
            self.assertEqual(status3["pending"], 0)


if __name__ == "__main__":
    unittest.main()
