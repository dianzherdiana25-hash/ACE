"""E2E Test Suite: Evidence Provenance and Independent Evaluator (Requirement 9).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (dual-oracle decoupling, Merkle exposure chaining, HMAC receipt verification)
Tier 2: Boundary & Corner Cases (direct terminal query violation, ledger tampering, n-gram contamination leakage)
Tier 3: Cross-Feature Interactions (cryptographic pre-registration commitment binding manifests and thresholds)
Tier 4: Real-World Scenarios (sealed evaluation lifecycle: holdout scoring, gain verification, signed receipt custody)
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_host_controller.budget_permits import ExecutionBudget
from ace_host_controller.evaluator_v2 import (
    ChainedExposureRecord,
    ContaminationDetectedError,
    DualOracleHarness,
    LedgerTamperError,
    MerkleExposureLedger,
    OracleBoundaryViolation,
    PreRegistrationCommitment,
)


class TestEvidenceProvenanceE2E(unittest.TestCase):
    """End-to-end verification of dual-oracle decoupling, evidence ledgers, and signed receipts."""

    def setUp(self):
        # Experiment oracle for training/epistemic queries
        self.exp_oracles = {
            "task_parity": lambda w: len(w) % 2 == 0,
            "task_starts_a": lambda w: w.startswith("a"),
        }
        # Sealed terminal holdout bank (disjoint holdout strings)
        self.term_holdouts = {
            "task_parity": [("aaaaaaaa", True), ("aaaaaaa", False), ("baaaaaa", False)],
            "task_starts_a": [("abbbbbbb", True), ("bbbbbbbb", False)],
        }
        self.harness = DualOracleHarness(
            experiment_oracles=self.exp_oracles,
            terminal_holdouts=self.term_holdouts,
            prior_baseline_scores={"task_parity": 0.50, "task_starts_a": 0.50},
        )
        self.budget = ExecutionBudget(max_execution_seconds=10.0, max_queries=50, max_candidates=10)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_metered_experiment_oracle_query_and_exposure_chaining(self):
        """Verify experiment oracle answers valid training queries and chains them in exposure ledger."""
        ans = self.harness.query_experiment_oracle("cand_01", "task_parity", "aaaa", self.budget)
        self.assertTrue(ans)
        self.assertEqual(self.budget.used_queries, 1)

        # Check exposure ledger has recorded query
        self.assertEqual(len(self.harness.exposure_ledger.records), 1)
        record = self.harness.exposure_ledger.records[0]
        self.assertIsInstance(record, ChainedExposureRecord)
        self.assertEqual(record.candidate_id, "cand_01")
        self.assertEqual(record.query_content, "aaaa")
        self.assertTrue(self.harness.exposure_ledger.verify_chain_integrity())

    def test_tier1_terminal_holdout_evaluation_and_signed_receipt(self):
        """Verify terminal holdout evaluation generates cryptographically signed EvaluationReceipt."""
        def perfect_solver(w: str, task_name: str | None = None) -> bool:
            if task_name == "task_parity":
                return len(w) % 2 == 0
            if task_name == "task_starts_a":
                return w.startswith("a")
            return False

        receipt = self.harness.evaluate_terminal_holdouts(
            candidate_id="cand_proven",
            candidate_fn=perfect_solver,
            budget=self.budget,
            min_gain=0.15,
            max_regression=0.02,
            parent_score=0.50,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.holdout_accuracy, 1.0)
        self.assertLessEqual(receipt.prior_regression, 0.02)
        # Verify receipt HMAC signature
        self.assertTrue(self.harness.verify_receipt(receipt))

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_direct_terminal_oracle_query_raises_boundary_violation(self):
        """Verify direct query to terminal holdout oracle strictly raises OracleBoundaryViolation."""
        with self.assertRaises(OracleBoundaryViolation) as ctx:
            self.harness.query_terminal_oracle("cand_malicious", "task_parity", "aaaaaaaa")
        self.assertIn("forbidden direct query to terminal holdout", str(ctx.exception))

    def test_tier2_ledger_tampering_breaks_integrity_and_blocks_evaluation(self):
        """Verify tampering with a record in the exposure ledger raises LedgerTamperError on evaluation."""
        self.harness.query_experiment_oracle("cand_01", "task_parity", "aa", self.budget)
        self.harness.query_experiment_oracle("cand_01", "task_parity", "bb", self.budget)
        self.assertTrue(self.harness.exposure_ledger.verify_chain_integrity())

        # Forcibly tamper with record 0
        r0 = self.harness.exposure_ledger.records[0]
        tampered_r0 = ChainedExposureRecord(
            record_id=r0.record_id,
            candidate_id=r0.candidate_id,
            query_type=r0.query_type,
            query_content="FORGED_PROBE",
            prev_hash=r0.prev_hash,
            current_hash=r0.current_hash,
        )
        self.harness.exposure_ledger.records[0] = tampered_r0
        self.assertFalse(self.harness.exposure_ledger.verify_chain_integrity())

        # Evaluating terminal holdouts with tampered ledger must raise LedgerTamperError
        with self.assertRaises(LedgerTamperError):
            self.harness.evaluate_terminal_holdouts(
                candidate_id="cand_test",
                candidate_fn=lambda w, t=None: True,
                budget=self.budget,
            )

    def test_tier2_ngram_substring_contamination_raises_contamination_detected_error(self):
        """Verify active learning query containing an 8-character holdout substring blocks promotion."""
        # Holdout contains "abbbbbbb"
        # Candidate queries a probe containing that exact 8-character substring:
        self.harness.query_experiment_oracle("cand_leak", "task_starts_a", "xxabbbbbbbxx", self.budget)

        # Terminal evaluation must detect substring n-gram contamination and fail
        with self.assertRaises(ContaminationDetectedError) as ctx:
            self.harness.evaluate_terminal_holdouts(
                candidate_id="cand_leak",
                candidate_fn=lambda w, t=None: True,
                budget=self.budget,
            )
        self.assertIn("Contamination detected", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_preregistration_commitment_detects_post_hoc_tampering(self):
        """Verify cryptographic commitment hash changes if thresholds or target tasks are modified."""
        base_commit = PreRegistrationCommitment(
            commitment_id="f13_pilot_01",
            manifest_digest="sha256_manifest_digest_abc",
            min_gain=0.1500,
            max_regression=0.0200,
            target_tasks=("task_parity", "task_starts_a"),
        )
        base_hash = base_commit.commitment_hash

        # 1. Post-hoc threshold relaxation
        relaxed_commit = PreRegistrationCommitment(
            commitment_id="f13_pilot_01",
            manifest_digest="sha256_manifest_digest_abc",
            min_gain=0.1000,  # relaxed gain
            max_regression=0.0200,
            target_tasks=("task_parity", "task_starts_a"),
        )
        self.assertNotEqual(base_hash, relaxed_commit.commitment_hash)

        # 2. Target task substitution
        substituted_commit = PreRegistrationCommitment(
            commitment_id="f13_pilot_01",
            manifest_digest="sha256_manifest_digest_abc",
            min_gain=0.1500,
            max_regression=0.0200,
            target_tasks=("task_parity", "task_other"),
        )
        self.assertNotEqual(base_hash, substituted_commit.commitment_hash)

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_underperforming_candidate_rejected_cleanly(self):
        """Verify candidate failing minimum gain threshold produces receipt marked passed=False."""
        def underperforming_solver(w: str, task_name: str | None = None) -> bool:
            return False  # Gets 0% accuracy

        receipt = self.harness.evaluate_terminal_holdouts(
            candidate_id="cand_failing",
            candidate_fn=underperforming_solver,
            budget=self.budget,
            min_gain=0.15,
            max_regression=0.02,
            parent_score=0.50,
        )
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.holdout_accuracy, 0.6)
        # Receipt is still authentically signed as negative evidence
        self.assertTrue(self.harness.verify_receipt(receipt))


if __name__ == "__main__":
    unittest.main()
