"""Unit tests for Sealed Evaluation V2 and Dual Oracle Governance.

Tests:
1. Dual oracle separation (experiment oracle vs terminal holdout).
2. Merkle exposure ledger chaining and tamper detection.
3. Multi-tier contamination checking (exact match + n-gram substring).
4. Terminal evaluation, HMAC signing, and regression gating.
5. Pre-registration commitment hash verification.
"""
from __future__ import annotations

import unittest

from ace_host_controller import ExecutionBudget
from ace_host_controller.evaluator_v2 import (
    ContaminationDetectedError,
    DualOracleHarness,
    LedgerTamperError,
    MerkleExposureLedger,
    PreRegistrationCommitment,
)


class TestEvaluatorV2(unittest.TestCase):
    def setUp(self):
        # Experiment oracle for training probes
        self.exp_oracles = {
            "task_parity": lambda w: len(w) % 2 == 0,
            "task_starts_a": lambda w: w.startswith("a"),
        }
        # Sealed terminal holdout bank (disjoint longer strings)
        self.term_holdouts = {
            "task_parity": [("aaaaaaaa", True), ("aaaaaaa", False), ("baaaaaa", False)],
            "task_starts_a": [("abbbbbbb", True), ("bbbbbbbb", False)],
        }
        self.harness = DualOracleHarness(
            experiment_oracles=self.exp_oracles,
            terminal_holdouts=self.term_holdouts,
            prior_baseline_scores={"task_parity": 0.50},
        )
        self.budget = ExecutionBudget(max_execution_seconds=10.0, max_queries=50, max_candidates=10)

    def test_dual_oracle_querying_and_budget(self):
        # Querying experiment oracle works and consumes budget
        ans = self.harness.query_experiment_oracle("cand_01", "task_parity", "aa", self.budget)
        self.assertTrue(ans)
        self.assertEqual(self.budget.used_queries, 1)

        # Querying non-existent task fails
        with self.assertRaises(KeyError):
            self.harness.query_experiment_oracle("cand_01", "non_existent_task", "aa", self.budget)

    def test_merkle_exposure_ledger_chain_and_tamper(self):
        ledger = MerkleExposureLedger()
        r1 = ledger.record_query("cand_01", "probe", "aaa")
        r2 = ledger.record_query("cand_01", "probe", "bbb")
        self.assertEqual(r2.prev_hash, r1.current_hash)
        self.assertTrue(ledger.verify_chain_integrity())

        # Tamper with record 1 in memory
        tampered_r1 = r1.__class__(
            record_id=r1.record_id,
            candidate_id=r1.candidate_id,
            query_type=r1.query_type,
            query_content="FORGED_CONTENT",
            prev_hash=r1.prev_hash,
            current_hash=r1.current_hash,
        )
        ledger.records[0] = tampered_r1
        self.assertFalse(ledger.verify_chain_integrity())

    def test_multitier_contamination_detection(self):
        ledger = MerkleExposureLedger()
        ledger.record_query("cand_01", "probe", "aaaaaaaa")  # Exact match with terminal holdout

        holdout_samples = ["aaaaaaaa", "bbbbbbbb"]
        res = ledger.check_contamination_multitier(holdout_samples)
        self.assertTrue(res["is_contaminated"])
        self.assertEqual(res["exact_leak_count"], 1)

    def test_terminal_evaluation_and_gating(self):
        # Candidate solving both tasks
        def solver(w: str, task_name: str | None = None) -> bool:
            if task_name == "task_parity":
                return len(w) % 2 == 0
            if task_name == "task_starts_a":
                return w.startswith("a")
            return False

        receipt = self.harness.evaluate_terminal_holdouts(
            candidate_id="cand_good",
            candidate_fn=solver,
            budget=self.budget,
            min_gain=0.15,
            max_regression=0.02,
            parent_score=0.50,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.holdout_accuracy, 1.0)
        self.assertTrue(self.harness.verify_receipt(receipt))

    def test_preregistration_commitment_hash(self):
        commit1 = PreRegistrationCommitment(
            commitment_id="f13_pre_01",
            manifest_digest="digest_abc",
            min_gain=0.15,
            max_regression=0.02,
            target_tasks=("task_parity", "task_starts_a"),
        )
        commit2 = PreRegistrationCommitment(
            commitment_id="f13_pre_01",
            manifest_digest="digest_abc",
            min_gain=0.20,  # Changed threshold
            max_regression=0.02,
            target_tasks=("task_parity", "task_starts_a"),
        )
        self.assertNotEqual(commit1.commitment_hash, commit2.commitment_hash)

    def test_direct_terminal_oracle_query_raises_boundary_violation(self):
        """Direct queries to terminal holdout oracle are strictly forbidden."""
        from ace_host_controller.evaluator_v2 import OracleBoundaryViolation

        with self.assertRaises(OracleBoundaryViolation):
            self.harness.query_terminal_oracle("cand_malicious", "task_parity", "aaaaaaaa")

    def test_zero_leakage_limitation_and_ngram_leak_detection(self):
        """Demonstrates that simple exact-match checking alone fails to catch substring leakage,
        confirming that multi-tier n-gram indexing is required to detect contamination."""
        ledger = MerkleExposureLedger()
        # Candidate queries a longer string containing an 8-gram of the holdout
        ledger.record_query("cand_01", "probe", "prefix_bbbbbbbb_suffix")

        holdout_samples = ["bbbbbbbb"]  # Exactly 8 characters
        res = ledger.check_contamination_multitier(holdout_samples, min_ngram_overlap_len=8)
        self.assertTrue(res["is_contaminated"])
        self.assertEqual(res["exact_leak_count"], 0)  # Exact match was 0!
        self.assertEqual(res["ngram_leak_count"], 1)  # Caught by n-gram checking!

    def test_receipt_integrity_distinguished_from_evaluator_independence(self):
        """HMAC receipts prove payload data integrity, not scientific independence of evaluator."""
        # A valid receipt can be generated and verified
        def dummy_solver(w, t=None):
            return True

        receipt = self.harness.evaluate_terminal_holdouts(
            candidate_id="cand_test",
            candidate_fn=dummy_solver,
            budget=self.budget,
            min_gain=0.0,
            max_regression=1.0,
            parent_score=0.0,
        )
        self.assertTrue(self.harness.verify_receipt(receipt))

        # Modifying any byte breaks HMAC integrity
        corrupted_receipt = receipt.__class__(
            receipt_id=receipt.receipt_id,
            candidate_id=receipt.candidate_id,
            holdout_accuracy=1.0,  # Falsified
            holdout_count=receipt.holdout_count,
            prior_regression=receipt.prior_regression,
            evaluator_manifest_digest=receipt.evaluator_manifest_digest,
            execution_seconds=receipt.execution_seconds,
            passed=receipt.passed,
            hmac_signature=receipt.hmac_signature,
        )
        self.assertFalse(self.harness.verify_receipt(corrupted_receipt))

    def test_dual_oracle_update_baseline_scores(self):
        """Safe updating of baseline scores without exposing holdout answers."""
        self.harness.update_baseline_scores({"task_starts_a": 0.95})
        self.assertEqual(self.harness._prior_baseline_scores["task_starts_a"], 0.95)


if __name__ == "__main__":
    unittest.main()
