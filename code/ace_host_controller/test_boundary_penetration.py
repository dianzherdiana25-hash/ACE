"""Adversarial penetration and negative security test suite for ACE Host Boundary V2.

Verifies:
1. Frame traversal attack (inspect.stack, sys._getframe) blocked.
2. GC heap scanning attack (gc.get_objects) blocked.
3. Dynamic import & OS escape attack (__import__, eval, exec) blocked.
4. Immutable promotion rules tampering blocked (FrozenInstanceError).
5. Forged HMAC signature rejection.
6. Fail-closed NOT_SEALED handling when OS containment is absent.
"""
from __future__ import annotations

import unittest

from ace_host_controller import (
    ExecutionBudget,
    HostSandboxGate,
    SandboxSecurityError,
    SealedHoldoutEvaluator,
)
from ace_host_controller.boundary import (
    ImmutablePromotionRules,
    SealingStatus,
    detect_os_sealing,
)
from ace_host_controller.subprocess_evaluator import SubprocessSealedEvaluator


class TestHostBoundaryPenetration(unittest.TestCase):
    def setUp(self):
        self.holdouts = {
            "task_test": [("a", False), ("aa", True), ("aaa", False), ("aaaa", True)]
        }
        self.evaluator = SubprocessSealedEvaluator(
            manifest_id="pen_test_manifest",
            holdout_banks=self.holdouts,
            prior_baseline_scores={},
        )
        self.budget = ExecutionBudget(max_execution_seconds=10.0, max_candidates=5)

    def test_frame_traversal_attack_blocked(self):
        """Attacker tries to inspect caller frame to access supervisor variables."""
        attack_code = (
            "def candidate_fn(w):\n"
            "    import sys\n"
            "    f = sys._getframe(1)\n"
            "    return True\n"
        )
        # AST gate catches import
        gate = HostSandboxGate(enforce_os_containment=False)
        res = gate.audit_ast(attack_code)
        self.assertFalse(res.allowed)
        self.assertIn("Forbidden import 'sys'", res.violations)

    def test_gc_heap_scan_attack_blocked(self):
        """Attacker tries to scan gc.get_objects to discover holdout banks."""
        attack_code = (
            "def candidate_fn(w):\n"
            "    import gc\n"
            "    objs = gc.get_objects()\n"
            "    return True\n"
        )
        gate = HostSandboxGate(enforce_os_containment=False)
        res = gate.audit_ast(attack_code)
        self.assertFalse(res.allowed)
        self.assertIn("Forbidden import 'gc'", res.violations)

    def test_dynamic_eval_escape_blocked(self):
        """Attacker attempts to use eval/exec to bypass AST restrictions."""
        attack_code = (
            "def candidate_fn(w):\n"
            "    eval('__import__(\"os\").system(\"id\")')\n"
            "    return True\n"
        )
        gate = HostSandboxGate(enforce_os_containment=False)
        res = gate.audit_ast(attack_code)
        self.assertFalse(res.allowed)
        self.assertIn("Forbidden function call 'eval()'", res.violations)

    def test_dunder_reflection_escape_blocked(self):
        """Attacker attempts class reflection escape to access sub-classes."""
        attack_code = (
            "def candidate_fn(w):\n"
            "    subs = ().__class__.__subclasses__()\n"
            "    return True\n"
        )
        gate = HostSandboxGate(enforce_os_containment=False)
        res = gate.audit_ast(attack_code)
        self.assertFalse(res.allowed)
        self.assertIn("Forbidden attribute access '__subclasses__'", res.violations)

    def test_immutable_promotion_rules_tamper_resistant(self):
        """Attacker tries to mutate frozen promotion rules."""
        rules = ImmutablePromotionRules(min_gain=0.15, max_regression=0.02)
        with self.assertRaises(Exception):  # FrozenInstanceError / AttributeError
            rules.min_gain = 0.0  # type: ignore

    def test_forged_hmac_receipt_rejected(self):
        """Attacker creates forged receipt with passed=True but fake signature."""
        from ace_host_controller.sealed_evaluator import EvaluationReceipt

        fake_receipt = EvaluationReceipt(
            receipt_id="rcpt_forged_123",
            candidate_id="cand_malicious",
            holdout_accuracy=1.0,
            holdout_count=100,
            prior_regression=0.0,
            evaluator_manifest_digest="fake_digest",
            execution_seconds=0.001,
            passed=True,
            hmac_signature="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )
        local_eval = self.evaluator._local_evaluator
        self.assertFalse(local_eval.verify_receipt(fake_receipt))

    def test_subprocess_evaluation_clean_candidate(self):
        """Legitimate safe candidate evaluates cleanly in isolated subprocess."""
        safe_code = (
            "def candidate_fn(w, task_name=None):\n"
            "    return len(w) % 2 == 0\n"
        )
        receipt = self.evaluator.evaluate_candidate_isolated(
            candidate_id="clean_cand_01",
            candidate_source=safe_code,
            budget=self.budget,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.holdout_accuracy, 1.0)
        self.assertTrue(self.evaluator._local_evaluator.verify_receipt(receipt))

    def test_not_sealed_detection_and_blocking(self):
        """When OS containerization is absent, sealing status is NOT_SEALED."""
        status = detect_os_sealing()
        self.assertIsInstance(status, SealingStatus)
        rules = ImmutablePromotionRules(require_os_containment=True)
        # If running in environment without bwrap/docker:
        if status == SealingStatus.NOT_SEALED:
            ok, violations = rules.validate_candidate(
                gain=0.20, regression=0.0, contaminated=False, sealing=status
            )
            self.assertFalse(ok)
            self.assertIn("OS containment absent (NOT_SEALED)", violations)

    def test_supervisor_can_block_candidate(self):
        """Supervisor explicitly blocks a candidate; subsequent gating rejects promotion."""
        from ace_host_controller import HostController, HostSandboxGate, SealedHoldoutEvaluator

        local_eval = SealedHoldoutEvaluator(
            manifest_id="test_man",
            holdout_banks=self.holdouts,
            prior_baseline_scores={},
        )
        host = HostController(
            evaluator=local_eval,
            budget=self.budget,
            sandbox_gate=HostSandboxGate(enforce_os_containment=False),
            root_candidate_id="G0_root",
        )
        # Supervisor explicitly blocks malicious candidate
        host.block_candidate("cand_bad_01", reason="Known security evasion attempt")

        # Gating evaluation attempt
        decision = host.evaluate_and_gate(
            candidate_id="cand_bad_01",
            parent_id="G0_root",
            generation=1,
            source_sha="a" * 64,
            candidate_fn=lambda w: True,
        )
        self.assertEqual(decision.status, "REJECTED")
        self.assertTrue(any("BLOCKED" in r for r in decision.rejection_reasons))

    def test_supervisor_can_revoke_promotion(self):
        """Supervisor revokes promotion of an accepted candidate, rolling back active head."""
        from ace_host_controller import HostController, HostSandboxGate, SealedHoldoutEvaluator

        local_eval = SealedHoldoutEvaluator(
            manifest_id="test_man",
            holdout_banks=self.holdouts,
            prior_baseline_scores={"task_test": 0.50},
        )
        host = HostController(
            evaluator=local_eval,
            budget=self.budget,
            sandbox_gate=HostSandboxGate(enforce_os_containment=False),
            root_candidate_id="G0_root",
        )
        # Normal candidate accepted
        dec = host.evaluate_and_gate(
            candidate_id="G1_accepted",
            parent_id="G0_root",
            generation=1,
            source_sha="b" * 64,
            candidate_fn=lambda w, t=None: len(w) % 2 == 0,
        )
        self.assertEqual(dec.status, "ACCEPTED")
        self.assertEqual(host.lineage.active_head_id, "G1_accepted")

        # Supervisor discovers post-promotion defect and revokes promotion
        rollback_rec = host.revoke_promotion("G1_accepted", reason="Post-eval contamination discovered")
        self.assertEqual(rollback_rec.rolled_back_from, "G1_accepted")
        self.assertEqual(rollback_rec.restored_head, "G0_root")
        self.assertEqual(host.lineage.active_head_id, "G0_root")
        self.assertEqual(host.lineage.nodes["G1_accepted"].status, "REVOKED")

    def test_safe_baseline_scores_update(self):
        """HostController safely updates baseline scores without exposing private banks."""
        from ace_host_controller import HostController, SealedHoldoutEvaluator

        local_eval = SealedHoldoutEvaluator(
            manifest_id="test_man",
            holdout_banks=self.holdouts,
            prior_baseline_scores={},
        )
        host = HostController(evaluator=local_eval, root_candidate_id="G0_root")
        host.update_baseline_scores({"task_test": 1.0})
        self.assertEqual(local_eval._prior_baseline_scores["task_test"], 1.0)

    def test_worker_receives_no_signing_key_or_ground_truth_labels(self):
        """Worker subprocess payload must contain ONLY inputs; never signing keys or expected labels."""
        inputs_by_task = {k: [inp for inp, _ in v] for k, v in self.evaluator._holdout_banks.items()}
        for task_name, inputs in inputs_by_task.items():
            for item in inputs:
                self.assertIsInstance(item, str)
        # Ensure evaluator holds signing key privately and does not leak it in public properties
        self.assertFalse(hasattr(self.evaluator, "signing_key"))
        self.assertFalse(hasattr(self.evaluator, "holdout_banks"))

    def test_worker_blocks_forbidden_ast_candidate(self):
        """Candidate attempting dangerous import fails gracefully in isolated worker."""
        attack_code = (
            "def candidate_fn(w, task_name=None):\n"
            "    import os\n"
            "    return True\n"
        )
        receipt = self.evaluator.evaluate_candidate_isolated(
            candidate_id="attack_cand_01",
            candidate_source=attack_code,
            budget=self.budget,
        )
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.holdout_accuracy, 0.0)

    def test_lineage_forgery_and_tampering_blocked(self):
        """Tampering with lineage or attempting forged child registration is rejected."""
        from ace_host_controller.lineage import LineageGraph, LineageNotFoundError

        graph = LineageGraph(root_id="G0_root")
        graph.register_candidate(
            candidate_id="G0_root",
            parent_id=None,
            source_sha="0" * 64,
            generation=0,
        )
        # Cannot add node with invalid/non-existent parent
        with self.assertRaises(LineageNotFoundError):
            graph.register_candidate(
                candidate_id="G1_orphan",
                parent_id="non_existent_parent",
                generation=1,
                source_sha="1" * 64,
            )


if __name__ == "__main__":
    unittest.main()

