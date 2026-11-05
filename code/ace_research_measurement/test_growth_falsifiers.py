"""Deterministic replay and negative control for public null screening."""
from __future__ import annotations
import json
from pathlib import Path
import unittest
from .growth_falsifiers import calibrated_null


class GrowthNullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual=calibrated_null()

    def test_exact_published_summary_replay(self):
        expected=json.loads(Path(__file__).with_name('results_growth_null.json').read_text())
        self.assertEqual(self.actual, expected)

    def test_known_zero_effect_does_not_become_claim(self):
        self.assertEqual(self.actual['design']['known_true_delta'], 0)
        self.assertEqual(self.actual['claim'], 'PUBLIC_NULL_DIAGNOSTIC_ONLY_NO_REAL_ACE')

    def test_stronger_gate_but_nonzero_false_passes(self):
        self.assertEqual(self.actual['counts']['naive_delta_at_least_10pp'], 42)
        self.assertEqual(self.actual['counts']['public_screen_pass'], 9)
        self.assertLess(self.actual['counts']['public_screen_pass'],
                        self.actual['counts']['naive_delta_at_least_10pp'])

    def test_invalid_run_count_rejected(self):
        with self.assertRaises(ValueError):calibrated_null(runs=0)
        with self.assertRaises(ValueError):calibrated_null(runs=True)


if __name__=='__main__': unittest.main()
