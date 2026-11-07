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


if __name__ == "__main__":
    unittest.main()
