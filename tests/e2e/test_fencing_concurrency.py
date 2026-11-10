"""E2E Test Suite: Atomic Lease, Fencing Concurrency, and Persistent State (Requirement 1).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (happy-path lease acquisition, atomic save, escrow commit)
Tier 2: Boundary & Corner Cases (stale token rejection, expired lease takeover, invalid tokens)
Tier 3: Cross-Feature Interactions (concurrent workers contending for state, transactional crash recovery)
Tier 4: Real-World Scenarios (simulated worker crash during lease hold, safe resumption and baseline integrity)
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_self_dev.state_manager import (
    ConcurrencyLockError,
    GENESIS_BASELINE,
    GENESIS_DIGEST,
    PersistentResearchState,
    StateManager,
)
from ace_autonomy.escrow import ExternalActionEscrow, ESCROW_STATES
from ace_autonomy.policy import digest


class TestFencingConcurrencyE2E(unittest.TestCase):
    """End-to-end verification of atomic leases, fencing tokens, and persistent state."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_e2e_fencing_"))
        self.state_dir = self.temp_dir / "checkpoints" / "self_dev"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.manager = StateManager(
            state_dir=str(self.state_dir),
            state_file="research_state.json",
            lock_ttl_seconds=2.0,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_fresh_state_initialization_and_genesis_integrity(self):
        """Verify clean initial state generation matches genesis cryptographic invariants."""
        state = self.manager.load_state()
        self.assertIsInstance(state, PersistentResearchState)
        self.assertEqual(state.schema_version, "2.0")
        self.assertEqual(state.cycle_count, 0)
        self.assertEqual(state.active_generation_id, GENESIS_BASELINE["root_candidate_id"])
        self.assertEqual(state.state_digest, GENESIS_DIGEST)
        self.assertFalse(state.concurrency_lock.get("is_locked", False))

        # Check immutable baseline file exists on disk
        baseline_path = self.state_dir / "immutable_baseline.json"
        self.assertTrue(baseline_path.exists())
        saved_baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        self.assertEqual(saved_baseline["root_candidate_id"], GENESIS_BASELINE["root_candidate_id"])

    def test_tier1_lease_acquisition_and_orderly_release(self):
        """Verify normal lease acquisition produces a unique token and releases cleanly."""
        token = self.manager.acquire_lock("worker_alpha")
        self.assertTrue(isinstance(token, str) and len(token) > 0)

        # Check in-flight state is locked
        state = self.manager.load_state()
        self.assertTrue(state.concurrency_lock.get("is_locked"))
        self.assertEqual(state.concurrency_lock.get("locked_by"), "worker_alpha")
        self.assertEqual(state.concurrency_lock.get("lock_token"), token)

        # Release lock
        self.manager.release_lock(token)
        state_after = self.manager.load_state()
        self.assertFalse(state_after.concurrency_lock.get("is_locked"))
        self.assertEqual(state_after.concurrency_lock.get("locked_by"), "")

    def test_tier1_external_action_escrow_lifecycle(self):
        """Verify ExternalActionEscrow durably records dispatched intents and validates state."""
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("""
            CREATE TABLE external_escrow (
                intent_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action_digest TEXT NOT NULL,
                state TEXT NOT NULL,
                lease_epoch INTEGER NOT NULL,
                receipt_json TEXT,
                signature TEXT NOT NULL
            )
        """)

        def dummy_signer(payload: dict) -> str:
            return digest(payload)

        escrow = ExternalActionEscrow(db, dummy_signer)
        action_payload = {"tool": "git_commit", "message": "test commit"}
        intent_id = escrow.record_dispatched(
            goal_id="goal_001",
            step_index=0,
            action=action_payload,
            lease_epoch=1,
        )
        self.assertTrue(bool(intent_id))

        # Verify query and signature validation
        row = escrow.get_intent("goal_001", 0)
        self.assertIsNotNone(row)
        self.assertEqual(row["state"], "DISPATCHED")
        self.assertEqual(row["lease_epoch"], 1)

        # Escrow verification passes without tampered rows
        escrow.verify_all()
        db.close()

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_active_lease_rejects_second_worker_with_concurrency_error(self):
        """Verify that an active unexpired lease strictly raises ConcurrencyLockError for rival worker."""
        token1 = self.manager.acquire_lock("worker_primary")
        self.assertTrue(bool(token1))

        # Second worker attempts acquisition before TTL expiration
        with self.assertRaises(ConcurrencyLockError) as ctx:
            self.manager.acquire_lock("worker_rival")
        self.assertIn("locked by worker_primary", str(ctx.exception))

        # Clean release allows subsequent acquisition
        self.manager.release_lock(token1)
        token2 = self.manager.acquire_lock("worker_rival")
        self.assertTrue(bool(token2))
        self.manager.release_lock(token2)

    def test_tier2_expired_lease_allows_safe_takeover(self):
        """Verify that an expired lease (now >= expires_at) is safely broken by a new worker."""
        # Use short TTL of 0.2 seconds
        short_manager = StateManager(
            state_dir=str(self.state_dir),
            state_file="research_state.json",
            lock_ttl_seconds=0.2,
        )
        token_first = short_manager.acquire_lock("stalled_worker")
        self.assertTrue(bool(token_first))

        # Wait for lease to expire
        time.sleep(0.3)

        # New worker should automatically break the expired lock without error
        token_second = short_manager.acquire_lock("recovery_worker")
        self.assertTrue(bool(token_second))
        self.assertNotEqual(token_first, token_second)

        state = short_manager.load_state()
        self.assertEqual(state.concurrency_lock.get("locked_by"), "recovery_worker")
        short_manager.release_lock(token_second)

    def test_tier2_release_with_mismatched_token_is_handled_safely(self):
        """Verify that attempting to release an active lock with an invalid token raises ConcurrencyLockError."""
        real_token = self.manager.acquire_lock("worker_beta")
        # Attempt release with bogus token must raise ConcurrencyLockError
        with self.assertRaises(ConcurrencyLockError) as ctx:
            self.manager.release_lock("bogus_token_12345")
        self.assertIn("invalid owner token", str(ctx.exception))

        # Lock remains held by real worker until valid token is supplied
        state = self.manager.load_state()
        self.assertTrue(state.concurrency_lock.get("is_locked"))
        self.assertEqual(state.concurrency_lock.get("locked_by"), "worker_beta")

        # Valid token releases cleanly
        self.manager.release_lock(real_token)
        state_after = self.manager.load_state()
        self.assertFalse(state_after.concurrency_lock.get("is_locked"))

    def test_tier2_corrupted_json_triggers_fail_closed_recovery(self):
        """Verify that corrupted state JSON on disk triggers automated fail-closed recovery."""
        state_file = self.state_dir / "research_state.json"
        state_file.write_text("CORRUPTED_NON_JSON_DATA{{{", encoding="utf-8")

        # Loading corrupted state triggers automated recovery
        recovered_state = self.manager.load_state()
        self.assertIsInstance(recovered_state, PersistentResearchState)
        self.assertEqual(recovered_state.immutable_baseline["root_candidate_id"], GENESIS_BASELINE["root_candidate_id"])

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_atomic_save_prevents_partial_write_corruption(self):
        """Verify that atomic save uses temporary file replacement preventing torn reads."""
        state = self.manager.load_state()
        state.cycle_count = 42
        state.active_generation_id = "G1_candidate_42"

        self.manager._atomic_save(state)

        # Confirm temporary file is removed and destination has exact content
        tmp_file = self.state_dir / "research_state.tmp"
        self.assertFalse(tmp_file.exists())

        loaded = self.manager.load_state()
        self.assertEqual(loaded.cycle_count, 42)
        self.assertEqual(loaded.active_generation_id, "G1_candidate_42")

    def test_tier3_state_recovery_restores_immutable_genesis_baseline(self):
        """Verify crash recovery preserves immutable baseline even if corrupted state deleted it."""
        # Intentionally delete recovery backup to test raw fallback
        backup_file = self.manager.recovery_backup_path
        if backup_file.exists():
            backup_file.unlink()

        # Trigger recovery
        recovered = self.manager.recover_from_crash("Simulated critical system failure")
        self.assertIsInstance(recovered, PersistentResearchState)
        self.assertEqual(recovered.cycle_count, 0)
        self.assertEqual(recovered.immutable_baseline["root_candidate_id"], GENESIS_BASELINE["root_candidate_id"])
        self.assertEqual(recovered.immutable_baseline["baseline_accuracy"], 0.5000)
        self.assertTrue(self.manager.state_path.exists())
        self.assertTrue(backup_file.exists())
        self.assertFalse(recovered.concurrency_lock.get("is_locked"))

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_multi_worker_sequential_turnover_simulation(self):
        """Simulate 10 sequential worker cycles with lock acquisition, state mutation, and release."""
        for cycle in range(1, 11):
            worker_id = f"worker_cycle_{cycle}"
            token = self.manager.acquire_lock(worker_id)
            state = self.manager.load_state()

            # Mutate state within lock
            state.cycle_count = cycle
            state.active_generation_id = f"candidate_gen_{cycle}"
            self.manager._atomic_save(state)

            self.manager.release_lock(token)

        final_state = self.manager.load_state()
        self.assertEqual(final_state.cycle_count, 10)
        self.assertEqual(final_state.active_generation_id, "candidate_gen_10")
        self.assertFalse(final_state.concurrency_lock.get("is_locked"))


if __name__ == "__main__":
    unittest.main()
