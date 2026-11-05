"""Pre-score tests. Deliberately never generates R7.2 test or OOD worlds."""
import unittest
from unittest.mock import patch

from . import experiment as baseline
from . import r72_certification as r72


class LockedResearchTests(unittest.TestCase):
    def test_beta_binomial_distribution_normalized(self):
        for a, b in ((1., 1.), (2.3, 12.), (15.2, 2.4)):
            for horizon in (1, 2, 3, 8):
                self.assertAlmostEqual(sum(r72.predictive_pmf(a, b, horizon, k)
                     for k in range(horizon + 1)), 1., places=11)

    def test_prior_and_world_splits_disjoint(self):
        train = r72.make_worlds('train', 30)
        val = r72.make_worlds('validation', 12)
        self.assertEqual(len(set(t.uid for t in train + val)), 42)
        self.assertTrue(all('r72' in t.uid for t in train+val))
        self.assertTrue(all(t.family=='stable' for t in train+val))
        self.assertNotEqual(train, val)

    def test_training_rejects_nontrain(self):
        with self.assertRaises(ValueError):
            baseline.fit_prior(r72.make_worlds('validation', 2))
        with self.assertRaises(ValueError):
            r72.make_worlds('intruder', 1)

    def test_no_evidence_means_abstain(self):
        t = r72.make_worlds('validation', 1)[0]
        prior = (.95,) * baseline.GROUPS
        r = r72.simulate_certificate(t, prior, 0)
        self.assertEqual(r['purchases'], 0)
        self.assertEqual(r['true_accepts']+r['false_accepts'], 0)
        self.assertEqual(r['abstentions'], baseline.GROUPS)

    def test_selector_readonly_does_not_accept_task_truth(self):
        belief = baseline.Belief((.92,)*baseline.GROUPS, r72.CONFIG)
        group = r72.next_certificate_group(belief, 24)
        self.assertTrue(group is None or 0 <= group < baseline.GROUPS)
        self.assertEqual(belief.counts, [0]*baseline.GROUPS)

    def test_no_privileged_oracle_during_acquisition(self):
        t = r72.make_worlds('validation', 1)[0]
        with patch.object(baseline.Evaluator, 'oracle_upper_bound',
                          side_effect=AssertionError('privilege leak')):
            r = r72.simulate_certificate(t, (.9,)*baseline.GROUPS, 24)
        self.assertLessEqual(r['purchases'], 24)

    def test_no_budgets_overrun(self):
        t = r72.make_worlds('validation', 1)[0]
        for cap in r72.BUDGETS:
            r = r72.simulate_certificate(t, (.85,)*baseline.GROUPS, cap)
            self.assertLessEqual(r['purchases'], cap)
            self.assertEqual(r['abstentions']+r['true_accepts']+r['false_accepts'], baseline.GROUPS)

    def test_early_stop_for_low_prior(self):
        t = r72.make_worlds('validation', 1)[0]
        r = r72.simulate_certificate(t, (.02,)*baseline.GROUPS, 24)
        self.assertEqual(r['purchases'], 0)
        self.assertEqual(r['abstentions'], baseline.GROUPS)

    def test_decision_after_three_evidence_points_minimum(self):
        b = baseline.Belief((.99,)*baseline.GROUPS, r72.CONFIG)
        self.assertFalse(r72.certifiable(b.a[0], b.b[0], b.counts[0]))
        for _ in range(2): b.observe(0, 1)
        self.assertFalse(r72.certifiable(b.a[0], b.b[0], b.counts[0]))
        b.observe(0, 1)
        self.assertTrue(r72.certifiable(b.a[0], b.b[0], b.counts[0]))

    def test_utility_wrong_accept_more_costly(self):
        r = {'true_accepts':1, 'false_accepts':0, 'abstentions':0, 'purchases':3}
        self.assertGreater(r72.utility(r), 0)
        r['true_accepts']=0; r['false_accepts']=1
        self.assertLess(r72.utility(r), 0)

    def test_validation_replay_and_cost(self):
        x = r72.validation_smoke()
        self.assertEqual(x, r72.validation_smoke())
        self.assertEqual(x['offline_training_labels'],2160)
        active=x['validation']['certificate']
        self.assertLessEqual(active['purchases'], 12*24)
        self.assertEqual(active['true_accepts']+active['false_accepts']+active['abstentions'],72)

    def test_random_matched_acquisition(self):
        t = r72.make_worlds('validation', 1)[0]
        p=(.5,)*baseline.GROUPS
        random=baseline.aggregate((t,),p,'random',baseline.Config(0,1.0),24)
        lcb=baseline.aggregate((t,),p,'random_lcb',r72.CONFIG,24)
        self.assertEqual(random['purchases'],lcb['purchases'])


if __name__=='__main__':unittest.main()
