"""Adversarial and real CLI checks for the non-frozen W3 admission path."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ace_core_repair.admission import AdmissionAwareSelector, fit_with_admission

ROOT = Path(__file__).resolve().parents[2]


class AdmissionContractTests(unittest.TestCase):
    train = [("a", True), ("b", False)]
    validation = [("aa", True), ("bb", False)]

    def test_training_memorizer_is_rejected_on_unseen_validation(self):
        result = AdmissionAwareSelector().evaluate_and_select(
            lambda w: w == "a", self.train, [("aa", True), ("bb", True)])
        self.assertEqual(("REJECTED", 0.0, 0, 2),
                         (result["status"], result["val_accuracy"],
                          result["errors"], result["validation_errors"]))
        self.assertEqual("validation", result["counterexamples"][0]["split"])

    def test_large_training_tolerance_never_relaxes_validation(self):
        result = AdmissionAwareSelector(100).evaluate_and_select(
            lambda w: False, self.train, self.validation)
        self.assertEqual("REJECTED", result["status"])

    def test_training_noise_is_tolerated_with_exact_validation(self):
        result = AdmissionAwareSelector(1).evaluate_and_select(
            lambda w: w.startswith("a"), [("a", True), ("b", True)], self.validation)
        self.assertEqual("ADMITTED_WITH_ERRORS", result["status"])
        self.assertEqual(1, result["errors"])
        self.assertEqual(0, result["validation_errors"])
        self.assertEqual(4, result["candidate_predictions"])
        self.assertEqual("BLOCK_RELEASE", result["release_gate"])
        self.assertFalse(result["candidate_deployed"])

    def test_training_error_beyond_tolerance_is_rejected(self):
        result = AdmissionAwareSelector().evaluate_and_select(
            lambda w: w.startswith("a"), [("a", False), ("b", False)], self.validation)
        self.assertEqual("TRAIN_ERROR_BUDGET_EXCEEDED", result["reason"])

    def test_invalid_budget_is_rejected(self):
        for value in (-1, True, 0.5, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                AdmissionAwareSelector(value)

    def test_empty_invalid_duplicate_and_overlapping_data_precede_evaluation(self):
        calls = []
        invalid_pairs = [([], self.validation), (self.train, []),
                         ([("a", 1)], self.validation),
                         ([("a", True), ("a", True)], self.validation),
                         (self.train, [("a", True)]),
                         ([("c", False)], self.validation)]
        for train, val in invalid_pairs:
            with self.subTest(train=train, val=val), self.assertRaises(ValueError):
                AdmissionAwareSelector().evaluate_and_select(
                    lambda w: calls.append(w) or True, train, val)
        self.assertEqual([], calls)

    def test_nonboolean_predictions_are_not_coerced_into_success(self):
        result = AdmissionAwareSelector().evaluate_and_select(
            lambda w: 1, self.train, self.validation)
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("NONBOOLEAN_PREDICTION", result["reason"])
        self.assertIsNone(result["train_accuracy"])

    def test_candidate_exception_cannot_leave_partial_admission(self):
        def broken(word):
            if word == "aa":
                raise ArithmeticError("diagnostic")
            return word == "a"
        result = AdmissionAwareSelector().evaluate_and_select(broken, self.train, self.validation)
        self.assertEqual("CANDIDATE_EVALUATION_ERROR", result["reason"])
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual(3, result["candidate_predictions"])
        self.assertEqual(0, result["validation_evaluated"])
        self.assertIsNone(result["val_accuracy"])

    def test_absent_label_class_is_unmeasured(self):
        result = AdmissionAwareSelector().evaluate_and_select(
            lambda w: True, [("a", True)], [("aa", True)])
        self.assertEqual("ADMITTED", result["status"])
        self.assertIsNone(result["neg_accuracy"])
        self.assertIsNone(result["validation_neg_accuracy"])

    def test_counterexamples_are_bounded_while_all_errors_are_counted(self):
        val = [("a" * i, True) for i in range(2, 15)]
        result = AdmissionAwareSelector().evaluate_and_select(lambda w: False, self.train, val)
        self.assertEqual(13, result["validation_errors"])
        self.assertEqual(8, len(result["counterexamples"]))
        self.assertEqual(15, result["candidate_predictions"])


class AdmissionTrainCLITests(unittest.TestCase):
    def invoke(self, task, max_errors=0):
        with tempfile.TemporaryDirectory(prefix="ace-w3-cli-") as tmp:
            task_path = Path(tmp) / "task.json"
            task_path.write_text(json.dumps(task))
            workspace = Path(tmp) / "state"
            proc = subprocess.run([sys.executable, str(ROOT / "ace.py"), "train",
                                   "--workspace", str(workspace), "--task", str(task_path),
                                   "--max-errors", str(max_errors)],
                                  cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertFalse(workspace.exists(), "train is a diagnostic, not a persisted promotion")
            self.assertNotIn("Traceback", proc.stderr)
            return proc

    def test_starts_uses_existing_qualified_arm_and_serialized_program_replays(self):
        from ace_capability_evolution import compositional as c
        train, val, terminal = c.bank("starts", 20261106)
        proc = self.invoke({"name": "starts", "train": train, "validation": val})
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual("ADMITTED", result["status"])
        self.assertEqual(0, result["validation_errors"])
        self.assertTrue(all(c.replay(result["program"], w) == label for w, label in terminal))
        self.assertGreaterEqual(result["unique_programs_evaluated"], 1)
        self.assertEqual(result["candidate_predictions"], result["admission_work"]["predictions"])

    def test_outside_grammar_returns_no_usable_program(self):
        from ace_capability_evolution import compositional as c
        train, val, _ = c.bank("ratio4", 20261106)
        proc = self.invoke({"name": "ratio4", "train": train, "validation": val})
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual("REJECTED", result["status"])
        self.assertIsNone(result["program"])
        self.assertIsNone(result["selected_arm"])

    def test_negative_budget_fails_before_fitting_or_workspace_write(self):
        proc = self.invoke({"name": "bad", "train": [["a", True]],
                            "validation": [["aa", True]]}, max_errors=-1)
        self.assertEqual(2, proc.returncode)
        self.assertIn("nonnegative", proc.stderr)


if __name__ == "__main__":
    unittest.main()
