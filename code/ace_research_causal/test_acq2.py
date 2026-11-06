"""Independent invariants and negative counterexamples for R5 ACQ2."""
import json
import math
import unittest

from . import acq1, acq2, invalid_iv


class ACQ2Tests(unittest.TestCase):
    def test_analytic_evpi_matches_numerical_integral(self):
        for interval in ((-1.5,1.5),(-1.1,0.8),(-.2,.7),(.3,1.2),(-1.5,-.6)):
            a,b=interval
            n=5000
            brute=sum(max(0,abs(a+(i+.5)*(b-a)/n)-.5) for i in range(n))/n
            self.assertAlmostEqual(acq2.expected_perfect_value(interval),brute,delta=0.0001)
            self.assertLessEqual(acq2.evpi(interval),acq2.expected_perfect_value(interval)+1e-10)

    def test_full_prior_evpi(self):
        self.assertAlmostEqual(acq2.evpi((-1.5,1.5)),1/3)
        self.assertEqual(acq2.robust_action((-1.5,1.5)),0)
        self.assertEqual(acq2.belief_action((-1.5,1.5)),0)

    def test_cost_dominating_evpi_never_buys_32(self):
        signal=acq1.Signal(float('nan'),float('nan'),0)
        self.assertFalse(acq2.triggers(signal,.025)['evpi32'])
        self.assertFalse(acq2.triggers(signal,.0125)['evpi32'])
        self.assertTrue(acq2.triggers(signal,.0025)['evpi32'])

    def test_weak_first_stage_returns_wide_interval(self):
        for iv_effect in (-100,0,100,float('nan')):
            self.assertEqual(acq2.candidate_interval(acq1.Signal(iv_effect,0,.01)),acq2.PRIOR)

    def test_conflicting_incompatible_evidence_falls_back_to_prior(self):
        self.assertEqual(acq2.candidate_interval(acq1.Signal(100,0,.8)),acq2.PRIOR)

    def test_ambiguous_identification_not_confident_action(self):
        signal=acq1.Signal(1.,0.,.75)
        interval=acq2.candidate_interval(signal)
        self.assertLessEqual(interval[0],0)
        self.assertGreaterEqual(interval[1],0)
        self.assertEqual(acq2.robust_action(interval),0)

    def test_robust_action_not_overconfident(self):
        self.assertEqual(acq2.robust_action((.6,1.5)),1)
        self.assertEqual(acq2.robust_action((-1.5,-.6)),-1)
        self.assertEqual(acq2.robust_action((-.4,.8)),0)

    def test_invalid_interval_fails_closed(self):
        for x in ((1,1),(2,3),(-2,1),(1,-1)):
            with self.assertRaises(ValueError): acq2.evpi(x)

    def test_monotonic_purchase_probability_across_prices(self):
        for iv_est in (-3,-1,0,1,3):
            for pi in (.1,.25,.75):
                s=acq1.Signal(iv_est,0,pi)
                values=[acq2.triggers(s,p)['evpi32'] for p in acq2.PRICES]
                self.assertEqual(values,sorted(values,reverse=True))

    def test_price_is_charged_exactly_on_spent_samples(self):
        w=invalid_iv.World(.8,1,0,0,0,.7)
        for price in acq2.PRICES:
            for n in (0,8,32):
                r=acq2.score(w,1,n,price)
                self.assertAlmostEqual(r['purchase_cost'],price*n)
                self.assertAlmostEqual(r['net_regret'],r['action_regret']+r['purchase_cost'])

    def test_intervention_oracle_is_capped_and_prefix_identical(self):
        w=invalid_iv.world(810000,'valid')
        a=acq1.DirectOracle(w,810000)
        b=acq1.DirectOracle(w,810000)
        self.assertEqual(a.buy(8)+a.buy(24),b.buy(32))
        with self.assertRaises(ValueError):b.buy(8)

    def test_evidence_rules_need_no_true_tau_or_world(self):
        signal=acq1.Signal(-.8,1.,.7)
        for price in acq2.PRICES:
            interval=acq2.candidate_interval(signal)
            self.assertEqual(acq2.choose('bayes_no_buy',signal,price,object()),
                             acq2.belief_action(interval))
            self.assertEqual(acq2.choose('robust_no_buy',signal,price,object()),
                             acq2.robust_action(interval))
            # If purchase isn't justified, it must not even open an oracle.
            if not acq2.triggers(signal,price)['evpi32']:
                self.assertEqual(acq2.choose('evpi32',signal,price,object()),
                                 acq2.belief_action(interval))

    def test_matched_random_exact_budget(self):
        r=acq2.experiment(3)
        for cohort in r['cohorts'].values():
            for price in acq2.PRICES:
                means=cohort[str(price)]['means']
                self.assertEqual(means['evpi32']['total_direct_rows'],
                                 means['random_matched32']['total_direct_rows'])

    def test_random_and_policy_query_costs_same(self):
        r=acq2.experiment(3)
        for cohort in r['cohorts'].values():
            for price in acq2.PRICES:
                means=cohort[str(price)]['means']
                self.assertEqual(means['evpi32']['purchase_cost'],
                                 means['random_matched32']['purchase_cost'])

    def test_all_null_conditional_rates_with_zero_acceptance(self):
        w=invalid_iv.World(.8,0,0,0,0,.7)
        rows=[{p:acq2.score(w,0,0,.0125) for p in acq2.POLICIES} for _ in range(3)]
        result=acq2.aggregate(rows)
        self.assertEqual(result['robust_no_buy']['accepted_count'],0)
        self.assertIsNone(result['robust_no_buy']['conditional_wrong_rate'])

    def test_replay_is_deterministic(self):
        a=json.dumps(acq2.experiment(2),sort_keys=True,allow_nan=False)
        b=json.dumps(acq2.experiment(2),sort_keys=True,allow_nan=False)
        self.assertEqual(a,b)

    def test_reject_invalid_configs(self):
        for n in (-1,1,201,2.5,True):
            with self.assertRaises(ValueError): acq2.experiment(n)
        w=invalid_iv.World(.8,1,0,0,0,.7)
        with self.assertRaises(ValueError): acq2.score(w,1,24,.0125)
        with self.assertRaises(ValueError): acq2.score(w,1,8,.03)
        with self.assertRaises(ValueError): acq2.choose('unknown',acq1.Signal(1,0,.7),.0125,acq1.DirectOracle(w,1))


if __name__=='__main__':
    unittest.main()
