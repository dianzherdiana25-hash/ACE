"""Pre-final R7.3 protocol integrity and independent local unit checks."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from . import experiment as e
from . import r73_shift as r


class R73SplitAndPriorTests(unittest.TestCase):
    def test_all_split_identifiers_new_and_disjoint(self):
        banks=[r.new_tasks('train','stable',30),r.new_tasks('validation','stable',12),
               *r.assemble_splits().values()]
        ids=[t.uid for bank in banks for t in bank]
        self.assertEqual(len(ids),30+12+24*3)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(':r73:' in id for id in ids))

    def test_reject_wrong_family_or_unbounded_count(self):
        for split,family,n in [('ood_a','stable',24),('test','shift_a',24),
                               ('train','stable',0),('invalid','stable',1)]:
            with self.assertRaises(ValueError):
                r.new_tasks(split,family,n)

    def test_fit_prior_is_only_train_source(self):
        prior, cost = e.fit_prior(r.new_tasks('train','stable',2))
        self.assertEqual(cost,144)
        self.assertEqual(len(prior),6)
        with self.assertRaises(ValueError):
            e.fit_prior(r.new_tasks('ood_a','shift_a',2))


class R73DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.prior=(.18,.42,.63,.78,.91,.97)

    def test_bayes_factor_depends_only_on_purchased_labels(self):
        good=tuple((g,1) for g in r.SENTINELS)
        bad=tuple((g,0) for g in r.SENTINELS)
        self.assertLess(r.prior_log_bayes_factor(self.prior,good),r.THRESHOLD_LBF)
        self.assertGreater(r.prior_log_bayes_factor(self.prior,bad),r.THRESHOLD_LBF)

    def test_impossible_observations_rejected(self):
        for invalid in (((4,True),),((0,1),),((5,2),)):
            with self.assertRaises(ValueError):
                r.prior_log_bayes_factor(self.prior,invalid)

    def test_strength_reset_replays_existing_observations(self):
        belief=e.Belief(self.prior,e.Config(12,1.0))
        evaluator=e.Evaluator(r.new_tasks('ood_a','shift_a',1)[0],6)
        obs=r.prefix(evaluator,belief,6)
        self.assertEqual(obs[0][0],4)
        weak=e.Belief(self.prior,e.Config(0,1.0))
        for g,y in obs:
            weak.observe(g,y)
        self.assertEqual(weak.counts[4],3)
        self.assertEqual(weak.counts[5],3)
        self.assertEqual(evaluator.purchases,6)
        self.assertTrue(0 <= weak.mean(4) <= 1)
        self.assertNotEqual(weak.mean(4),belief.mean(4))

    def test_expensive_truth_only_in_evaluator(self):
        task=r.new_tasks('ood_a','shift_a',1)[0]
        with patch.object(e.Evaluator,'oracle_upper_bound',side_effect=AssertionError('oracle leak')):
            for method in ('random_lcb','certificate','sentinel_control','shift_aware'):
                r.simulate(task,self.prior,method,24)

    def test_decisions_do_not_use_scoring_probes(self):
        task=r.new_tasks('ood_a','shift_a',1)[0]
        with patch.object(e.Evaluator,'score',side_effect=RuntimeError('score unavailable')):
            with self.assertRaisesRegex(RuntimeError,'score unavailable'):
                r.simulate(task,self.prior,'shift_aware',24)


class R73BudgetAndMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.prior=(.18,.42,.63,.78,.91,.97)
        self.bank=r.new_tasks('test','stable',3)

    def test_no_labels_means_full_abstention_even_with_prior(self):
        for method in ('random_lcb','certificate','sentinel_control','shift_aware'):
            outcome=r.simulate(self.bank[0],self.prior,method,0)
            self.assertEqual(outcome.row['purchases'],0)
            self.assertEqual(outcome.row['abstentions'],6)
            self.assertFalse(outcome.shift_detected)

    def test_counts_never_exceed_cap_and_disjoint_outcomes(self):
        for method in ('random_lcb','certificate','sentinel_control','shift_aware'):
            for cap in r.BUDGETS:
                row=r.aggregate(self.bank,self.prior,method,cap)
                self.assertLessEqual(row['purchases'],cap*len(self.bank))
                self.assertEqual(row['true_accepts']+row['false_accepts']+
                                 row['abstentions'],6*len(self.bank))
                self.assertLessEqual(row['total_diagnostic_labels'],cap*len(self.bank))

    def test_false_acceptance_undefined_when_no_predictions(self):
        row=r.aggregate(self.bank,self.prior,'shift_aware',0)
        self.assertIsNone(row['false_acceptance_rate'])

    def test_no_changing_budget_or_method_after_proposal(self):
        for method,cap in [('oracle',24),('shift_aware',25),('fixed',24)]:
            with self.assertRaises(ValueError):
                r.simulate(self.bank[0],self.prior,method,cap)

    def test_validation_replays_deterministically(self):
        self.assertEqual(r.validation_smoke(),r.validation_smoke())


if __name__=='__main__':
    unittest.main()
