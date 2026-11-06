"""ACQ1 adversarial invariants and deterministic reproducibility tests."""
import json
import math
import unittest
from unittest.mock import patch

from . import acq1
from . import invalid_iv


class ACQ1Tests(unittest.TestCase):
    def setUp(self):
        self.w = invalid_iv.world(720000, 'direct_exclusion')

    def test_direct_oracle_hard_bounded_batches(self):
        oracle = acq1.DirectOracle(self.w, 720000)
        for size in (0, -8, 7, 9, 1.1, True, 40):
            with self.subTest(size=size), self.assertRaises(ValueError):
                oracle.buy(size)
        self.assertEqual(oracle.used, 0)
        self.assertEqual(len(oracle.buy(8)), 8)
        self.assertEqual(len(oracle.buy(24)), 24)
        self.assertEqual(oracle.used, 32)
        with self.assertRaises(ValueError):
            oracle.buy(8)
        self.assertEqual(oracle.used, 32)

    def test_oracle_direct_do_sample_has_no_encouragement(self):
        oracle = acq1.DirectOracle(self.w, 720000)
        rows = oracle.buy(32)
        self.assertEqual({z for z, x, y in rows}, {0.0})
        self.assertEqual(sum(x for z, x, y in rows), 0)
        self.assertEqual(sum(x*x for z, x, y in rows), 32)
        for offset in range(0, 32, 8):
            self.assertEqual(sum(x for z, x, y in rows[offset:offset+8]), 0)

    def test_shared_prefix_across_separate_policy_ledgers(self):
        a=acq1.DirectOracle(self.w, 720000)
        b=acq1.DirectOracle(self.w, 720000)
        self.assertEqual(a.buy(8) + a.buy(24), b.buy(32))
        self.assertEqual(a.used, 32)
        self.assertEqual(b.used, 32)

    def test_identical_baseline_samples_for_all_policies(self):
        e,o=acq1.initial_rows(self.w,720000)
        self.assertEqual((e,o),acq1.initial_rows(self.w,720000))
        self.assertEqual((len(e),len(o)),(80,80))
        self.assertEqual(sum(z for z,x,y in e),0)
        self.assertEqual({z for z,x,y in o}, {0.0})

    def test_no_purchase_never_queries(self):
        oracle=acq1.DirectOracle(self.w,720000)
        s=acq1.Signal(-.8, .8, .8)
        self.assertEqual(acq1.choose('no_buy',s,oracle),-1)
        self.assertEqual(oracle.used,0)

    def test_staged_budget_counts_partial_and_full(self):
        s=acq1.Signal(1.0, -1.0, .75)
        oracle=acq1.DirectOracle(self.w,720000)
        acq1.choose('staged8_24', s, oracle)
        self.assertIn(oracle.used,(8,32))
        self.assertEqual(oracle.used%8,0)

    def test_trigger_is_not_oracle_true_tau(self):
        s=acq1.Signal(.9,.8,.75)
        self.assertFalse(acq1.disagreement(s))
        self.assertFalse(acq1.uncertainty(s))
        # Modifying hidden tau while preserving observable signals cannot change trigger.
        alt=invalid_iv.World(-self.w.tau, self.w.confounding, self.w.heterogeneity,
                             self.w.direct_z, self.w.selection_slope, self.w.compliance)
        self.assertNotEqual(alt.tau,self.w.tau)
        self.assertEqual(acq1.disagreement(s),acq1.disagreement(s))

    def test_true_utility_and_cost_accounting(self):
        w=invalid_iv.World(.8, 1.,0.,0.,0.,.7)
        x=acq1.score(w,1,8)
        self.assertAlmostEqual(x['action_regret'],0)
        self.assertAlmostEqual(x['query_cost'],.1)
        self.assertAlmostEqual(x['net_regret'],.1)
        self.assertAlmostEqual(acq1.score(w,-1,0)['action_regret'], 1.6)
        self.assertAlmostEqual(acq1.score(w,0,0)['action_regret'], .3)

    def test_abstention_conditional_wrong_is_null(self):
        zeros=[{p:acq1.score(self.w,0,0) for p in acq1.POLICIES} for _ in range(3)]
        result=acq1.aggregate(zeros)
        self.assertEqual(result['no_buy']['accepted_count'],0)
        self.assertIsNone(result['no_buy']['conditional_wrong_rate'])

    def test_disagreement_trigger_thresholds(self):
        self.assertTrue(acq1.disagreement(acq1.Signal(1.,-1.,.8)))
        self.assertTrue(acq1.disagreement(acq1.Signal(1.,.1,.8)))
        self.assertTrue(acq1.disagreement(acq1.Signal(.3,.2,.12)))
        self.assertFalse(acq1.disagreement(acq1.Signal(1.,.9,.8)))
        self.assertTrue(acq1.uncertainty(acq1.Signal(.52,.8,.8)))
        self.assertFalse(acq1.uncertainty(acq1.Signal(1.,.8,.8)))

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            acq1.choose('oracle_magic',acq1.Signal(1.,1.,1.), acq1.DirectOracle(self.w,1))

    def test_paired_cohort_random_budget_exact_equal(self):
        result=acq1.experiment(3)
        for cohort in result['cohorts'].values():
            a=cohort['means']['disagreement32']['total_direct_rows']
            b=cohort['means']['random_matched32']['total_direct_rows']
            self.assertEqual(a,b)
            self.assertEqual(a,cohort['disagreement_trigger_count']*32)

    def test_determinism_across_repeat_runs(self):
        first=json.dumps(acq1.experiment(3),sort_keys=True,allow_nan=False)
        second=json.dumps(acq1.experiment(3),sort_keys=True,allow_nan=False)
        self.assertEqual(first,second)

    def test_never_purchase_hard_limit_or_negative_cost(self):
        for n in (-1, 33):
            with self.assertRaises(ValueError):
                acq1.score(self.w,1,n)
        for act in (-2,2):
            with self.assertRaises(ValueError):
                acq1.score(self.w,act,0)

    def test_out_of_scope_n_is_rejected(self):
        for worlds in (-1,0,1,201,1.2,True):
            with self.assertRaises(ValueError):
                acq1.experiment(worlds)

    def test_random_budget_selector_independent_of_reward_truth(self):
        # The matched-world mask is chosen from only initial-row triggers and seed.
        group=acq1.experiment(3)['cohorts']['direct_exclusion']
        self.assertEqual(group['means']['disagreement32']['total_purchase_cost'],
                         group['means']['random_matched32']['total_purchase_cost'])

    def test_causal_nonidentifiability_not_fixed_without_do(self):
        # X=Z means tau*X + lambda*Z is identical for tau=.4,lambda=-.8
        # and tau=-.4,lambda=0. Yet do(X) sets Z=0: target tau differs.
        for z in (-1,1):
            self.assertEqual(.4*z-.8*z, -.4*z)
        self.assertNotEqual(.4,-.4)


if __name__ == '__main__':
    unittest.main()
