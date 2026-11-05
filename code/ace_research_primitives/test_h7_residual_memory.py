"""R1 H7 bounded evidence construction and adversarial negative-control tests."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path
from ace_research_primitives import h7_residual_memory as h7
from ace_research_primitives import audit_h7 as audit


class H7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(json.dumps(h7.run()))

    def test_precommitted_results_and_gates(self):
        s = self.report['summary']
        self.assertEqual((s['accepted'], s['holdout_correct']), (64, 16384))
        self.assertEqual(s['oracle_fixed_correct'], 10998)
        self.assertEqual(s['negative_abstentions'], 8)
        self.assertTrue(s['gates']['overall_go'])
        self.assertEqual(self.report['protocol_commit'],
                         '9e7e810952a39a1003e28fb0005037ffe62db0fd')

    def test_constructor_only_observed_positive_substrings(self):
        tr = [('baabbaab', True), ('ababbabb', True), ('bbbbbbbb', False)]
        proposals = h7.candidate_substrings(tr)
        self.assertTrue(proposals)
        self.assertTrue(all(any(p in word for word, truth in tr if truth) for p in proposals))
        self.assertNotIn('aaaaa', proposals)

    def test_no_residual_evidence_abstains(self):
        rows = [(word, False) for word in h7.POOL[:20]]
        response = h7.discover(rows, rows)
        self.assertFalse(response['accepted'])
        self.assertIsNone(response['pattern'])

    def test_budget_fail_closed(self):
        many = [(word, True) for word in h7.POOL[:200]]
        with self.assertRaises(RuntimeError):
            h7.discover(many, many)

    def test_negative_late_drift_and_non_substring(self):
        for row in self.report['controls']:
            self.assertFalse(row['representation']['accepted'])
            self.assertIsNone(row['representation']['pattern'])
        self.assertTrue(any(r['score']['correct'] < 256 for r in self.report['controls']))

    def test_evidence_independent_replay(self):
        result = audit.verify(self.report)
        self.assertEqual(result['worlds_replayed'], 72)
        self.assertEqual(result['query_validation_labels_replayed'], 18432)

    def test_auditor_detects_forged_summary(self):
        wrong = copy.deepcopy(self.report)
        wrong['summary']['holdout_correct'] -= 1
        with self.assertRaises(AssertionError):
            audit.verify(wrong)

    def test_auditor_detects_forged_feature(self):
        wrong = copy.deepcopy(self.report)
        wrong['main'][0]['representation']['pattern'] = 'bbbbb'
        with self.assertRaises(AssertionError):
            audit.verify(wrong)

    def test_auditor_detects_forged_score(self):
        wrong = copy.deepcopy(self.report)
        wrong['main'][0]['score']['correct'] -= 1
        with self.assertRaises(AssertionError):
            audit.verify(wrong)

    def test_generated_samples_are_disjoint(self):
        for i in range(72):
            t, v, h = h7.split_queries(i)
            self.assertEqual((len(t), len(v), len(h)), (128, 128, 256))
            self.assertFalse(set(t) & set(v))
            self.assertFalse(set(t) & set(h))
            self.assertFalse(set(v) & set(h))


if __name__ == '__main__':
    unittest.main()
