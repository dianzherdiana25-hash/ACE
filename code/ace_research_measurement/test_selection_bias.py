"""Controls for evaluator false-positive measurement under researcher selection."""
from __future__ import annotations
import unittest
from .selection_bias import experiment


class SelectionBiasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = experiment()

    def test_deterministic(self):
        self.assertEqual(self.result, experiment())

    def test_null_population_declared(self):
        self.assertEqual(self.result['design']['ground_truth_candidate_accuracy'], 0.5)
        self.assertEqual(self.result['claim_gate'], 'NOT_ASSESSED')

    def test_max_validation_is_optimistic(self):
        self.assertGreater(self.result['means']['validation_selection_optimism'], 0.10)

    def test_evaluation_returns_to_null(self):
        self.assertLess(abs(self.result['means']['selected_evaluation'] - 0.5), 0.025)

    def test_no_substantial_true_gain_over_fixed(self):
        self.assertLess(abs(self.result['means']['selected_evaluation_minus_fixed_evaluation']), 0.025)

    def test_high_rate_of_spurious_validation_gains(self):
        self.assertGreater(self.result['rates']['naive_validation_gain_at_least_threshold'], 0.75)

    def test_some_wins_are_false_progress(self):
        self.assertGreater(self.result['counts']['naive_false_progress'], 100)

    def test_gate_does_not_claim_confirmation(self):
        self.assertEqual(self.result['claim_gate'], 'NOT_ASSESSED')

    def test_unsupported_configurations_rejected(self):
        for args in [{'arms': 0}, {'repetitions': -1}, {'evaluation_cases': 3},
                     {'seed': False}, {'threshold': 0.0}, {'threshold': 0.1}]:
            if args == {'threshold': 0.1}:
                # valid float threshold; don't treat every 0.1 as invalid
                self.assertEqual(experiment(repetitions=1, arms=2, **args)['claim_gate'], 'NOT_ASSESSED')
                continue
            with self.subTest(args=args), self.assertRaises(ValueError):
                experiment(**args)


if __name__ == '__main__':
    unittest.main()
