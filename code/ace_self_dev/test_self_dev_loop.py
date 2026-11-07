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
    ResearchHypothesis,
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

    def test_composite_candidate_generation_and_isolated_evaluation(self):
        """Verify SourceGenerator and IsolatedEvaluator handle composite mechanisms safely."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        tasks = create_confirmation_suite(42)
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_COMPOSITE",
            statement="Applying composite mechanism synthesis for task_k2",
            target_task_id="task_k2_modular_stride_shift",
            strategy="SYNTHESIZE_COMPOSITE_MECHANISM",
        )
        cand = coord.generator.generate_candidate(
            hypothesis=hyp,
            parent_candidate=None,
            parent_id="G0_root",
            ordinal=1,
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )
        self.assertTrue(cand.gene_dict.get("is_composite"))
        self.assertIn("^", cand.source_code)

        # Isolated evaluation must compile and execute composite candidate without error
        receipt = coord.evaluator.evaluate_candidate(
            candidate=cand,
            hypothesis=hyp,
            tasks=tasks,
            host_controller=None,
            prior_cycle_id=1,
            state_digest_before="state_digest_test",
        )
        self.assertIsNotNone(receipt)
        self.assertIn(receipt.decision.value, ("ACCEPTED", "REJECTED"))

    def test_relational_gated_candidate_generation_and_isolated_evaluation(self):
        """Verify SourceGenerator and IsolatedEvaluator handle multi-clause relational gated mechanisms safely."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        tasks = create_confirmation_suite(42)
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_RELATIONAL",
            statement="Applying multi-clause relational gated synthesis for task_k2",
            target_task_id="task_k2_modular_stride_shift",
            strategy="SYNTHESIZE_RELATIONAL_MULTI_CLAUSE",
        )
        cand = coord.generator.generate_candidate(
            hypothesis=hyp,
            parent_candidate=None,
            parent_id="G0_root",
            ordinal=1,
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )
        self.assertTrue(cand.gene_dict.get("is_relational"))
        self.assertTrue(cand.gene_dict.get("is_relational_gated"))
        self.assertIn("and", cand.source_code)

        # Isolated evaluation must compile and evaluate relational candidate safely
        receipt = coord.evaluator.evaluate_candidate(
            candidate=cand,
            hypothesis=hyp,
            tasks=tasks,
            host_controller=None,
            prior_cycle_id=1,
            state_digest_before="state_digest_test",
        )
        self.assertIsNotNone(receipt)
        self.assertIn(receipt.decision.value, ("ACCEPTED", "REJECTED"))
        self.assertGreaterEqual(receipt.train_score, 0.0)
        self.assertGreaterEqual(receipt.validation_score, 0.0)

    def test_sealed_terminal_holdout_gating_prevents_repeated_queries(self):
        """Verify that sealed holdout evaluations are gated to prevent steering search or cherry-picking."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        tasks = create_confirmation_suite(42)
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_GATING",
            statement="Applying typed AST mutation ordinal 1 for task_k2",
            target_task_id="task_k2_modular_stride_shift",
            strategy="LINEAR_MUTATION",
        )
        cand = coord.generator.generate_candidate(
            hypothesis=hyp,
            parent_candidate=None,
            parent_id="G0_root",
            ordinal=1,
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )

        # First evaluation succeeds
        receipt1 = coord.evaluator.evaluate_candidate(
            candidate=cand,
            hypothesis=hyp,
            tasks=tasks,
            host_controller=None,
            prior_cycle_id=1,
            state_digest_before="state_digest_test",
        )
        self.assertIsNotNone(receipt1)

        # Second evaluation of the same candidate against sealed holdout is blocked by gating
        with self.assertRaises(RuntimeError) as ctx:
            coord.evaluator.evaluate_candidate(
                candidate=cand,
                hypothesis=hyp,
                tasks=tasks,
                host_controller=None,
                prior_cycle_id=1,
                state_digest_before="state_digest_test",
            )
        self.assertIn("Holdout gating violation", str(ctx.exception))

    def test_candidate_search_relies_strictly_on_train_and_validation_metrics(self):
        """Verify that candidate search explores variants using train and validation pools without holdout access."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        tasks = create_confirmation_suite(42)
        target_task = tasks["task_k2_modular_stride_shift"]
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_SEARCH",
            statement="Applying multi-clause relational gated synthesis for task_k2",
            target_task_id="task_k2_modular_stride_shift",
            strategy="SYNTHESIZE_RELATIONAL_MULTI_CLAUSE",
        )

        # Search across 3 candidate variants on validation pool
        best_cand = coord.search_and_select_candidate(
            hypothesis=hyp,
            parent_candidate=None,
            active_head_id="G0_root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            target_task=target_task,
            search_budget=3,
        )
        self.assertIsNotNone(best_cand)
        # Verify holdout was NEVER queried during search
        self.assertEqual(len(coord.evaluator._holdout_queried_candidates), 0)

    def test_frozen_thresholds_fail_closed_on_artificial_relaxation(self):
        """Verify that artificial lowering of min_required_gain or relaxation of tolerance fails closed."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.ckpt_dir),
            evidence_dir=str(self.evidence_dir),
        )
        tasks = create_confirmation_suite(42)

        # Sub-threshold min_gain is rejected
        hyp_low_gain = ResearchHypothesis(
            hypothesis_id="HYP_LOW_GAIN",
            statement="Test lowering gain",
            target_task_id="task_k2_modular_stride_shift",
            min_required_gain=0.1000,  # Below frozen 0.1500
        )
        cand = coord.generator.generate_candidate(
            hypothesis=hyp_low_gain,
            parent_candidate=None,
            parent_id="G0_root",
            ordinal=1,
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )
        with self.assertRaises(ValueError) as ctx:
            coord.evaluator.evaluate_candidate(
                candidate=cand,
                hypothesis=hyp_low_gain,
                tasks=tasks,
                host_controller=None,
            )
        self.assertIn("Fail-closed governance invariant violation", str(ctx.exception))

        # Excessive regression tolerance is rejected
        hyp_high_reg = ResearchHypothesis(
            hypothesis_id="HYP_HIGH_REG",
            statement="Test relaxing regression tolerance",
            target_task_id="task_k2_modular_stride_shift",
            max_regression_tolerance=0.0500,  # Exceeds frozen 0.0200
        )
        cand2 = coord.generator.generate_candidate(
            hypothesis=hyp_high_reg,
            parent_candidate=None,
            parent_id="G0_root",
            ordinal=2,
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )
        with self.assertRaises(ValueError) as ctx:
            coord.evaluator.evaluate_candidate(
                candidate=cand2,
                hypothesis=hyp_high_reg,
                tasks=tasks,
                host_controller=None,
            )
        self.assertIn("Fail-closed governance invariant violation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
