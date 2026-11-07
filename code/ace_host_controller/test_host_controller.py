"""Comprehensive unit tests for ACE Host Controller.

Tests lineage DAG, budget limits, permits, sandbox security gate,
exposure ledger non-contamination, sealed holdouts, acceptance gating, and rollback.
"""
from __future__ import annotations

import json
import unittest

from ace_host_controller import (
    AcceptanceDecision,
    BudgetExceededError,
    CapabilityPermit,
    ContaminationError,
    EvaluatorManifest,
    ExecutionBudget,
    ExposureLedger,
    HostController,
    HostSandboxGate,
    LineageCycleError,
    LineageGraph,
    LineageNotFoundError,
    PermitDeniedError,
    SandboxSecurityError,
    SealedHoldoutEvaluator,
)
from ace_host_controller.verify import verify_governance_report


class TestLineageGraph(unittest.TestCase):
    def test_lineage_registration_and_traversal(self):
        graph = LineageGraph(root_id="root")
        graph.register_candidate("root", None, "sha_root", 0)
        graph.update_status("root", "ACCEPTED", holdout_score=0.5)

        c1 = graph.register_candidate("cand_1", "root", "sha_1", 1)
        self.assertEqual(c1.lineage_depth, 1)
        self.assertEqual(graph.get_ancestors("cand_1"), ["root"])

        c2 = graph.register_candidate("cand_2", "cand_1", "sha_2", 2)
        self.assertEqual(c2.lineage_depth, 2)
        self.assertEqual(graph.get_ancestors("cand_2"), ["cand_1", "root"])

    def test_lineage_errors(self):
        graph = LineageGraph()
        with self.assertRaises(LineageNotFoundError):
            graph.register_candidate("cand_x", "non_existent_parent", "sha_x", 1)

        graph.register_candidate("root", None, "sha_root", 0)
        with self.assertRaises(ValueError):
            # Duplicate registration
            graph.register_candidate("root", None, "sha_root", 0)


class TestBudgetAndPermits(unittest.TestCase):
    def test_budget_exhaustion(self):
        budget = ExecutionBudget(max_execution_seconds=1.0, max_queries=5, max_candidates=2)
        budget.consume_queries(3)
        self.assertEqual(budget.remaining_queries, 2)
        with self.assertRaises(BudgetExceededError):
            budget.consume_queries(3)

        budget.record_candidate_eval()
        budget.record_candidate_eval()
        with self.assertRaises(BudgetExceededError):
            budget.record_candidate_eval()

    def test_permits(self):
        permit = CapabilityPermit(allowed_capabilities=frozenset({"ast_inspect"}))
        permit.verify_capability("ast_inspect")
        with self.assertRaises(PermitDeniedError):
            permit.verify_capability("arbitrary_eval")
        with self.assertRaises(PermitDeniedError):
            permit.verify_operation("network")
        with self.assertRaises(PermitDeniedError):
            permit.verify_operation("shell_exec")


class TestSandboxGate(unittest.TestCase):
    def setUp(self):
        self.gate = HostSandboxGate(enforce_os_containment=False)

    def test_safe_ast(self):
        code = "def solve(x):\n    return x.count('a') % 2 == 0\n"
        res = self.gate.audit_ast(code)
        self.assertTrue(res.allowed)

    def test_forbidden_imports(self):
        code = "import os\ndef solve(x):\n    os.system('id')\n"
        res = self.gate.audit_ast(code)
        self.assertFalse(res.allowed)
        with self.assertRaises(SandboxSecurityError):
            res.enforce()

    def test_forbidden_calls_and_attributes(self):
        code = "def exploit():\n    return ().__class__.__subclasses__()\n"
        res = self.gate.audit_ast(code)
        self.assertFalse(res.allowed)
        self.assertIn("Forbidden attribute access '__subclasses__'", res.violations)


class TestExposureLedger(unittest.TestCase):
    def test_contamination_detection(self):
        ledger = ExposureLedger()
        ledger.record_exposure("cand_1", "query", "sample_input_abc")
        ledger.record_exposure("cand_1", "query", "sample_input_def")

        holdout_clean = ["holdout_xyz", "holdout_123"]
        is_contam, leaks = ledger.check_contamination(holdout_clean)
        self.assertFalse(is_contam)
        self.assertEqual(len(leaks), 0)
        ledger.assert_clean(holdout_clean)

        holdout_dirty = ["holdout_xyz", "sample_input_abc"]
        is_contam, leaks = ledger.check_contamination(holdout_dirty)
        self.assertTrue(is_contam)
        self.assertEqual(leaks, ["sample_input_abc"])
        with self.assertRaises(ContaminationError):
            ledger.assert_clean(holdout_dirty)


class TestHostControllerIntegration(unittest.TestCase):
    def setUp(self):
        # Create a sealed evaluator with test tasks
        holdouts = {
            "task_parity": [("a", False), ("aa", True), ("aaa", False), ("aaaa", True)],
            "task_prefix": [("ab", True), ("ba", False), ("aba", True), ("bb", False)],
        }
        prior_scores = {"task_parity": 0.50, "task_prefix": 0.50}
        self.evaluator = SealedHoldoutEvaluator(
            manifest_id="test_manifest_v1",
            holdout_banks=holdouts,
            prior_baseline_scores=prior_scores,
        )
        self.controller = HostController(
            evaluator=self.evaluator,
            budget=ExecutionBudget(max_execution_seconds=10.0, max_queries=100, max_candidates=10),
            sandbox_gate=HostSandboxGate(enforce_os_containment=False),
            min_gain=0.15,
            max_regression=0.02,
        )

    def test_candidate_acceptance_and_promotion(self):
        # Candidate solving both parity and prefix: 100% accuracy (gain 0.50 > 0.15, regression 0.0)
        def good_solver(inp: str) -> bool:
            if inp in ("aa", "aaaa", "ab", "aba"):
                return True
            return False

        good_code = "def good_solver(inp):\n    return inp in ('aa', 'aaaa', 'ab', 'aba')\n"
        dec = self.controller.evaluate_and_gate(
            candidate_id="G1_good",
            parent_id="G0_root",
            generation=1,
            source_sha="sha_good_candidate",
            candidate_fn=good_solver,
            candidate_code_or_spec=good_code,
            metadata={"description": "High accuracy G1 successor"},
        )
        self.assertEqual(dec.status, "ACCEPTED")
        self.assertEqual(dec.holdout_accuracy, 1.0)
        self.assertEqual(self.controller.lineage.active_head_id, "G1_good")

    def test_candidate_rejection_on_regression(self):
        # Candidate regressing on prefix task
        def regressive_solver(inp: str) -> bool:
            return False  # 0% accuracy

        dec = self.controller.evaluate_and_gate(
            candidate_id="G1_bad",
            parent_id="G0_root",
            generation=1,
            source_sha="sha_bad_candidate",
            candidate_fn=regressive_solver,
        )
        self.assertEqual(dec.status, "REJECTED")
        self.assertEqual(self.controller.lineage.active_head_id, "G0_root")

    def test_candidate_rejection_on_contamination(self):
        # Expose a holdout sample to the ledger
        self.controller.exposure_ledger.record_exposure(
            candidate_id="leak_cand",
            query_type="probe",
            content="aaaa",  # This is in task_parity holdouts!
        )

        def solver(inp: str) -> bool:
            return True

        dec = self.controller.evaluate_and_gate(
            candidate_id="G1_leaked",
            parent_id="G0_root",
            generation=1,
            source_sha="sha_leaked",
            candidate_fn=solver,
        )
        self.assertEqual(dec.status, "REJECTED")
        self.assertTrue(dec.contamination_detected)

    def test_rollback(self):
        # First promote G1
        def good_solver(inp: str) -> bool:
            return inp in ("aa", "aaaa", "ab", "aba")

        self.controller.evaluate_and_gate(
            candidate_id="G1_promoted",
            parent_id="G0_root",
            generation=1,
            source_sha="sha_g1",
            candidate_fn=good_solver,
        )
        self.assertEqual(self.controller.lineage.active_head_id, "G1_promoted")

        # Now trigger rollback
        rollback_rec = self.controller.rollback(reason="Test regression detected post-deployment")
        self.assertEqual(rollback_rec.rolled_back_from, "G1_promoted")
        self.assertEqual(rollback_rec.restored_head, "G0_root")
        self.assertEqual(self.controller.lineage.active_head_id, "G0_root")
        self.assertEqual(self.controller.lineage.nodes["G1_promoted"].status, "ROLLED_BACK")

    def test_governance_report_and_verifier(self):
        report = self.controller.get_governance_report()
        self.assertEqual(report["release_gate"], "BLOCK_RELEASE")
        self.assertEqual(report["scientific_status"], "NOT_ASSESSED")
        self.assertFalse(report["oaie_established"])

        ok, msg = verify_governance_report(report)
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
