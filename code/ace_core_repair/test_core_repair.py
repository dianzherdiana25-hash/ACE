"""Unit tests for W3 Core Learner Repairs.

Tests follow TDD: verify failure before wiring the implementation.
"""
import unittest


class TestCoreLearnerRepair(unittest.TestCase):
    def test_admission_aware_selection_and_max_errors(self):
        """Selector prioritizes admission over validation, reports pos/neg accuracy separately, and supports max_errors."""
        from ace_core_repair.admission import AdmissionAwareSelector

        selector = AdmissionAwareSelector(max_errors=1)

        # Train set with 1 noisy mislabeled row among 10 rows
        train_data = [
            ("a", True), ("aa", True), ("aaa", True), ("aaaa", True), ("aaaaa", True),
            ("b", False), ("bb", False), ("bbb", False), ("bbbb", False), ("bba", False)  # noisy label
        ]
        val_data = [
            ("aaaaaa", True), ("bbbbb", False)
        ]

        def candidate_perfect_rule(word):
            return "a" in word

        result = selector.evaluate_and_select(candidate_perfect_rule, train_data, val_data)
        self.assertIn(result["status"], ("ADMITTED_WITH_ERRORS", "ADMITTED"))
        self.assertEqual(result["errors"], 1)
        self.assertIn("pos_accuracy", result)
        self.assertIn("neg_accuracy", result)

    def test_second_counterexample_round_prevents_guard_overfit(self):
        """Second counterexample round prevents 'contains aa' guard from overfitting on count-matched negatives."""
        from ace_core_repair.admission import verify_guard_robustness

        # Overfitting guard: checks if 'aa' in word
        overfitting_guard = lambda word: "aa" in word

        robust, report = verify_guard_robustness(overfitting_guard, guard_type="contains_aa")
        self.assertFalse(robust, "Naive 'contains aa' guard must fail second counterexample round on count-matched order mutations.")
        self.assertGreater(report["counterexamples_found"], 0)

    def test_late_flip_drift_triggers_abstain_with_zero_false_admission(self):
        """Late-flip semantic drift triggers ABSTAIN via semantic quarantine, resulting in 0 false admissions."""
        from ace_core_repair.drift_quarantine import SemanticDriftQuarantine

        quarantine = SemanticDriftQuarantine(consistency_threshold=0.95)

        # Base distribution: length > 3
        base_observations = [("a", False), ("ab", False), ("abc", False), ("abcd", True), ("abcde", True)]
        # Flipped distribution (late-flip anomaly): length > 3 now labeled False
        late_flip_observations = [("abcd", False), ("abcde", False), ("abcdef", False)]

        decision, details = quarantine.check_distribution_consistency(
            base_observations, late_flip_observations
        )
        self.assertEqual(decision, "ABSTAIN")
        self.assertEqual(details["false_admission_count"], 0)
        self.assertTrue(details["quarantined"])

    def test_decomposed_library_saves_cross_family_fits(self):
        """Decomposed component library enables inheriting sub-components (counter, guard) to save fits without refitting."""
        from ace_core_repair.decomposed_library import DecomposedLibrary

        lib = DecomposedLibrary()
        # Register a proven counter primitive and a proven boundary guard
        lib.register_component("counter_mod2", kind="counter", predicate=lambda w: w.count("a") % 2 == 0)
        lib.register_component("guard_starts_a", kind="guard", predicate=lambda w: w.startswith("a"))

        # Composite query requiring (starts_a AND mod2)
        train_new_family = [
            ("a", False), ("aa", True), ("aab", True), ("ba", False), ("baa", False)
        ]
        reused_model, fits_saved = lib.compose_and_solve(train_new_family)
        self.assertIsNotNone(reused_model)
        self.assertGreaterEqual(fits_saved, 1, "Must save at least 1 fit by composing existing sub-components without refitting.")

    def test_doctor_diagnostics(self):
        """ace.py doctor runs system diagnostics and reports health checks."""
        from ace_core_repair.doctor import run_doctor_diagnostics

        report = run_doctor_diagnostics()
        self.assertTrue(report["source_integrity_pass"])
        self.assertIn("checks", report)


if __name__ == "__main__":
    unittest.main()
