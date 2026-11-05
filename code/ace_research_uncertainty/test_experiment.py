"""Independent observable invariants for the ACE R7 pilot."""
import unittest
from unittest.mock import patch

from .experiment import (BUDGETS, Config, Evaluator, Belief, GROUPS,
                         Task, aggregate, choose_group, fit_prior, make_tasks,
                         run, simulate, tune)


class IsolationTests(unittest.TestCase):
    def test_split_ids_are_disjoint(self):
        all_sets = [set(t.uid for t in make_tasks(s, 'shift' if s == 'ood' else 'stable', 8))
                    for s in ('train', 'validation', 'test', 'ood')]
        self.assertEqual(len(set.union(*all_sets)), 32)
        for i in range(4):
            for j in range(i):
                self.assertFalse(all_sets[i] & all_sets[j])

    def test_ood_cannot_be_used_for_training_or_validation_tuning(self):
        ood = make_tasks('ood', 'shift', 2)
        with self.assertRaises(ValueError):
            fit_prior(ood)
        with self.assertRaises(ValueError):
            tune((.5,) * GROUPS, ood)

    def test_query_hard_cap_and_invalid_queries(self):
        task = make_tasks('test', 'stable', 1)[0]
        evaluator = Evaluator(task, 1)
        with self.assertRaises(ValueError):
            evaluator.query(-1)
        with self.assertRaises(ValueError):
            evaluator.query(True)
        evaluator.query(0)
        with self.assertRaisesRegex(RuntimeError, 'budget'):
            evaluator.query(1)
        self.assertEqual(evaluator.purchases, 1)

    def test_only_offline_oracle_can_access_privileged_probability(self):
        task = make_tasks('test', 'stable', 1)[0]
        with patch.object(Evaluator, 'oracle_upper_bound', side_effect=AssertionError('leak')):
            simulate(task, (.5,) * GROUPS, 'active_lcb', Config(2, 1.64), 12)
        with self.assertRaises(ValueError):
            simulate(task, (.5,) * GROUPS, 'oracle', Config(2, 1.64), 12)

    def test_evaluation_sample_namespace_separate_from_purchased_labels(self):
        task = make_tasks('test', 'stable', 1)[0]
        evaluator = Evaluator(task, 6)
        before = evaluator.score((.5,)*GROUPS, (False,)*GROUPS)
        for group in range(6):
            evaluator.query(group)
        after = evaluator.score((.5,)*GROUPS, (False,)*GROUPS)
        self.assertEqual(before['calibration'], after['calibration'])
        self.assertEqual(after['purchases'], 6)


class DecisionTests(unittest.TestCase):
    def test_no_evidence_means_abstain(self):
        task = make_tasks('test', 'stable', 1)[0]
        for method in ('fixed', 'random', 'random_lcb', 'active_lcb'):
            result = simulate(task, (.99,) * GROUPS, method, Config(12, 1.0), 0)
            self.assertEqual(result['true_accepts'] + result['false_accepts'], 0)
            self.assertEqual(result['abstentions'], GROUPS)
            self.assertEqual(result['purchases'], 0)

    def test_lcb_stricter_than_posterior_mean(self):
        b = Belief((.95,) * GROUPS, Config(12, 2.33))
        for label in (1, 1, 1):
            b.observe(0, label)
        self.assertTrue(b.accept(0, 'fixed', 1.0))
        self.assertFalse(b.accept(0, 'active_lcb', 2.33))

    def test_adaptive_choice_based_only_on_beliefs(self):
        a = Belief((.5,)*GROUPS, Config(2, 1.64))
        g = choose_group(a, 'active_lcb', 0, 'test:stable:0')
        self.assertTrue(0 <= g < GROUPS)
        a.observe(g, 1)
        nxt = choose_group(a, 'active_lcb', 1, 'test:stable:0')
        self.assertNotEqual(g, nxt)

    def test_score_counts_false_accepts_on_hidden_truth(self):
        t = Task('test:counterexample', 'stable', (.1, .2, .3, .4, .9, .95))
        e = Evaluator(t, 0)
        result = e.score((.9,)*6, (True,)*6)
        self.assertEqual(result['false_accepts'], 4)
        self.assertEqual(result['true_accepts'], 2)
        self.assertGreater(result['ece'], 0) if 'ece' in result else self.assertEqual(len(result['calibration']), 10)

    def test_budget_consumption_and_aggregation(self):
        tasks = make_tasks('test', 'stable', 2)
        for cap in BUDGETS:
            result = aggregate(tasks, (.5,)*GROUPS, 'active_lcb', Config(2, 1.64), cap)
            self.assertEqual(result['purchases'], cap * 2)
            self.assertEqual(result['abstentions'] + result['true_accepts']
                             + result['false_accepts'], GROUPS * 2)
            self.assertGreaterEqual(result['ece'], 0)
            self.assertLessEqual(result['ece'], 1)

    def test_deterministic_replay_and_validation_locked(self):
        a = run()
        b = run()
        self.assertEqual(a, b)
        self.assertEqual(a['offline_training_labels'], 30*GROUPS*12)
        self.assertEqual(a['validation_tuning_evaluations'], 12)
        for split in ('test', 'ood'):
            self.assertEqual(a['results'][split]['24']['active_lcb']['purchases'], 20*24)
            self.assertEqual(a['results'][split]['oracle_upper_bound']['purchases'], 0)
        self.assertNotEqual(a['lock']['split_ids_sha256']['test'],
                            a['lock']['split_ids_sha256']['ood'])


if __name__ == '__main__':
    unittest.main()
