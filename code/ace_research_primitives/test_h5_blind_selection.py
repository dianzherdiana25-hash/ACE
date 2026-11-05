"""H5 state-class selection falsification, integrity, and independent replay."""
from __future__ import annotations

import copy
import unittest

try:
    from . import h5_blind_selection as h5
    from . import audit_h5 as audit
    from . import primitive_discovery as d
except ImportError:
    import h5_blind_selection as h5
    import audit_h5 as audit
    import primitive_discovery as d


class H5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=h5.run_h5()

    def test_24_tasks_and_disjoint_holdouts(self):
        self.assertEqual(len(self.data['tasks']),24)
        self.assertEqual([r['group'] for r in self.data['tasks']],
                         ['finite']*12+['counter']*8+['drift']*4)
        targets=h5.tasks()
        for row,target in zip(self.data['tasks'],targets):
            self.assertEqual(row['id'],target['id'])
            self.assertFalse(set(target['holdout']) & set(d.training_words()+d.validation_words()))
            self.assertEqual(len(set(target['holdout'])),len(target['holdout']))

    def test_new_target_generator_is_deterministic(self):
        self.assertEqual(h5.new_finite_targets(),h5.new_finite_targets())
        self.assertEqual(h5.finite_holdout(0),h5.finite_holdout(0))
        self.assertEqual(h5.block_holdout('a_block_b_block',18),h5.block_holdout('a_block_b_block',18))

    def test_budget_and_selection_no_unknown_task_label(self):
        self.assertEqual([self.data[k] for k in ('training_labels','validation_labels','holdout_labels','total_oracle_labels')],
                         [1512,4608,3648,9768])
        for row in self.data['tasks']:
            self.assertEqual(row['scores']['finite']['train']['correct'],63)
            self.assertLessEqual(row['finite']['merges'],10000)
            self.assertLessEqual(row['counter']['proposals'],1000)
            self.assertLessEqual(row['counter']['guards'],1000)
            selected=row['selection']['chosen']
            self.assertIn(selected,('finite','counter_or_fallback'))
            self.assertEqual(row['scores']['selected'],row['scores'][selected])

    def test_h5_fails_strong_baseline_gain_gate(self):
        m=self.data['metrics']
        self.assertEqual(m['selected_mean'],1.0)
        self.assertEqual(m['counter_mean'],1.0)
        self.assertEqual(m['improvement_vs_best_fixed'],0.0)
        self.assertEqual(m['selected_tasks_at_90'],20)
        self.assertFalse(m['h5a_pass'])

    def test_drift_falsifier_is_not_detected(self):
        m=self.data['metrics']
        self.assertEqual(m['drift_semantic_abstentions'],0)
        self.assertFalse(m['h5b_pass'])
        self.assertFalse(m['combined_h5_go'])
        for row in self.data['tasks'][20:]:
            self.assertEqual(row['scores']['selected']['holdout']['correct'],0)
            self.assertEqual(row['scores']['selected']['train']['correct'],63)

    def test_separate_auditor_verifies_all_scores(self):
        receipt=audit.verify(self.data)
        self.assertEqual(receipt['verified_tasks'],24)
        self.assertEqual(receipt['verified_split_method_scores'],432)
        self.assertEqual(receipt['oracle_labels_verified'],9768)

    def test_tampered_holdout_truth_fails_closed(self):
        evidence=copy.deepcopy(self.data)
        evidence['tasks'][0]['holdout_labels'][0] ^= 1
        with self.assertRaises(AssertionError):audit.verify(evidence)

    def test_tampered_validation_selection_fails_closed(self):
        evidence=copy.deepcopy(self.data)
        evidence['tasks'][0]['selection']['finite_validation_errors'] += 1
        with self.assertRaises(AssertionError):audit.verify(evidence)

    def test_tampered_finite_machine_fails_closed(self):
        evidence=copy.deepcopy(self.data)
        machine=evidence['tasks'][0]['finite']['automaton']
        machine[0][0] = not bool(machine[0][0])
        with self.assertRaises(AssertionError):audit.verify(evidence)

    def test_tampered_aggregate_false_success_fails_closed(self):
        evidence=copy.deepcopy(self.data)
        evidence['metrics']['combined_h5_go']=True
        with self.assertRaises(AssertionError):audit.verify(evidence)


if __name__=='__main__':unittest.main()
