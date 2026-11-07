"""Unit, regression, and continuity tests for ACE Autonomous Self-Development Loop V0.2."""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from ace_self_dev import (
    AgendaEngine,
    AuthorType,
    CandidateDecision,
    ConfirmationTask,
    PersistentResearchState,
    ProvenanceEngine,
    ProvenanceProof,
    SelfDevelopmentCoordinator,
    StateManager,
    create_confirmation_suite,
)
from ace_self_dev.state_manager import ConcurrencyLockError


class TestSelfDevelopmentLoop(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ckpt_dir = Path(self.temp_dir) / "checkpoints"
        self.evidence_dir = Path(self.temp_dir) / "evidence"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_provenance_engine_cryptographic_verification(self):
        """Verifies provenance proof generation, key fingerprints, and tamper detection."""
        engine = ProvenanceEngine(signing_key="test_signing_key_secret_123")
        self.assertTrue(len(engine.key_fingerprint) == 16)

        proof = engine.create_provenance_proof(
            source_sha="test_source_sha_456",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )
        self.assertEqual(proof.author_type, AuthorType.ACE_AUTONOMOUS_V02)
        self.assertEqual(proof.execution_pid, os.getpid())
        self.assertEqual(proof.source_sha, "test_source_sha_456")

        # Valid proof verifies
        ok, msg = engine.verify_provenance_proof(proof)
        self.assertTrue(ok, msg)

        # Tampered proof is rejected
        tampered_dict = proof.to_dict()
        tampered_dict["source_sha"] = "tampered_sha_999"
        tampered_proof = ProvenanceProof.from_dict(tampered_dict)
        ok_tampered, _ = engine.verify_provenance_proof(tampered_proof)
        self.assertFalse(ok_tampered)

    def test_state_manager_concurrency_lock_and_lease(self):
        """State manager enforces concurrency lease and handles lease conflicts."""
        sm = StateManager(state_dir=str(self.ckpt_dir), lock_ttl_seconds=2.0)
        token1 = sm.acquire_lock("worker_1")
        self.assertTrue(bool(token1))

        # Second worker is rejected while lock is active
        with self.assertRaises(ConcurrencyLockError):
            sm.acquire_lock("worker_2")

        # First worker releases lock
        sm.release_lock(token1)

        # Now second worker can acquire
        token2 = sm.acquire_lock("worker_2")
        self.assertTrue(bool(token2))
        sm.release_lock(token2)

    def test_state_manager_crash_recovery(self):
        """Simulate state corruption and verify fail-closed recovery to verified backup/baseline."""
        sm = StateManager(state_dir=str(self.ckpt_dir))
        state = sm.load_state()
        state.cycle_count = 1
        sm.record_completed_cycle(
            cycle_id=1,
            hypothesis_id="HYP_1",
            target_task_id="task_j1",
            candidate_id="CAND_1",
            source_sha="sha_1",
            decision="REJECTED",
            holdout_score=0.4500,
            gain_over_parent=0.0000,
            rejection_reason="Gain below 0.1500",
            evidence_path="evidence/path1.json.gz",
            receipt_signature="sig_1",
            gene_dict={"mod_op": 1},
            mutation_ordinal=1,
            active_head_id="G0_root",
        )

        # Corrupt state file
        sm.state_path.write_text("CORRUPTED_NOT_VALID_JSON{", encoding="utf-8")

        # Recovery should trigger automatically
        recovered = sm.load_state()
        self.assertGreaterEqual(recovered.fail_closed_recovery["recovery_count"], 1)
        self.assertEqual(recovered.cycle_count, 1)
        self.assertFalse(recovered.concurrency_lock["is_locked"])

    def test_agenda_engine_avoids_repeated_falsified_mutations(self):
        """Agenda engine observes past failures and selects next unexplored ordinal/task."""
        agenda = AgendaEngine(max_attempts_per_task=2)
        tasks = create_confirmation_suite(task_seed=123)
        state = PersistentResearchState(
            schema_version="2.0",
            active_generation_id="G0_root",
            cycle_count=1,
            failure_catalog={
                "task_k2_modular_stride_shift": [
                    {"cycle_id": 1, "mutation_ordinal": 1, "gain_over_parent": 0.0}
                ]
            },
        )
        diagnosis = agenda.diagnoser_dummy = type("DummyDiag", (), {
            "diagnostic_details": {
                "task_scores": {
                    "task_k2_modular_stride_shift": 0.40,
                    "task_j1_multiscale_run_parity": 0.60,
                    "task_j2_symmetric_run_boundary": 0.60,
                    "task_k1_center_pivot_density": 0.60,
                }
            }
        })()

        # Should advance to ordinal 2 since ordinal 1 failed on task_k2
        tid, seed, ord_val = agenda.select_cycle_strategy(state, diagnosis, tasks)
        self.assertEqual(tid, "task_k2_modular_stride_shift")
        self.assertEqual(ord_val, 2)

    def test_three_sequential_autonomous_continuity_cycles(self):
        """Prove minimum three sequential cycles across separate invocations with unbroken state chaining."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )

        # Cycle 1
        c1 = coord.run_autonomous_cycle(author_type=AuthorType.ACE_AUTONOMOUS_V02)
        self.assertEqual(c1["cycle_id"], 1)
        self.assertIsNone(c1["prior_cycle_id"])
        self.assertTrue(Path(c1["evidence_path"]).exists())
        self.assertIn(c1["decision"], ("ACCEPTED", "REJECTED"))

        # Cycle 2 (reads state from Cycle 1)
        c2 = coord.run_autonomous_cycle(author_type=AuthorType.ACE_AUTONOMOUS_V02)
        self.assertEqual(c2["cycle_id"], 2)
        self.assertEqual(c2["prior_cycle_id"], 1)
        self.assertEqual(c2["state_digest_before"], c1["state_digest_after"])
        self.assertTrue(Path(c2["evidence_path"]).exists())

        # Cycle 3 (reads state from Cycle 2)
        c3 = coord.run_autonomous_cycle(author_type=AuthorType.ACE_AUTONOMOUS_V02)
        self.assertEqual(c3["cycle_id"], 3)
        self.assertEqual(c3["prior_cycle_id"], 2)
        self.assertEqual(c3["state_digest_before"], c2["state_digest_after"])
        self.assertTrue(Path(c3["evidence_path"]).exists())

        # Verify state file persistence
        state = coord.state_manager.load_state()
        self.assertEqual(state.cycle_count, 3)
        self.assertEqual(len(state.completed_cycles), 3)

        # Lineage invariance: rejected candidates never become active lineage head
        for c in (c1, c2, c3):
            if c["decision"] == "REJECTED":
                self.assertNotIn(c["candidate_id"], c["active_head_id"])

    def test_negative_control_evaluation(self):
        """Evaluator detects and rejects adversarial / inverted negative controls."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        tasks = create_confirmation_suite(42)
        is_rejected, acc = coord.evaluator.evaluate_negative_control(
            task=tasks["task_k2_modular_stride_shift"],
            host_controller=None,
        )
        self.assertTrue(is_rejected)
        self.assertLessEqual(acc, 0.5000)


if __name__ == "__main__":
    unittest.main()
