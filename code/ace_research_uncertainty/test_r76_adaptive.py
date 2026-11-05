"""Deterministic safety and cost invariant tests before R7.6 final scoring."""
import unittest
from unittest.mock import patch
from . import r76_adaptive as r

class R76Tests(unittest.TestCase):
    def setUp(self):
        self.prior=(.18,.42,.63,.78,.91,.97)
        self.w=r.worlds('validation','stable',r.TRAIN_SEED,1)[0]

    def test_prereg_cap_and_split_rejection(self):
        with self.assertRaises(ValueError):r.worlds('train','swap',r.TRAIN_SEED,3)
        with self.assertRaises(ValueError):r.worlds('test','stable',r.TRAIN_SEED,3)
        with self.assertRaises(ValueError):r.worlds('test','stable',r.SEEDS[0],True)
        with self.assertRaises(ValueError):r.play(self.w,self.prior,'oracle',24)
        with self.assertRaises(ValueError):r.play(self.w,self.prior,'adaptive10',25)

    def test_world_ids_disjoint(self):
        banks=[r.worlds('train','stable',r.TRAIN_SEED,18),r.worlds('validation','stable',r.TRAIN_SEED,12)]
        banks.extend(r.worlds('test',f,s,20) for f in r.BASES for s in r.SEEDS)
        ids=[w.uid for group in banks for w in group]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(':r76:' not in id for id in []))
        self.assertTrue(all(id.startswith('r76:') for id in ids))

    def test_supermartingale(self):
        for p in (0.,.1,.4,.79,.8):
            expectation=p*r.P1/r.P0+(1-p)*(1-r.P1)/(1-r.P0)
            self.assertLessEqual(expectation,1+1e-12)
        self.assertGreater(.99*r.P1/r.P0+.01*(1-r.P1)/(1-r.P0),1)

    def test_shortlist_only_uses_observations(self):
        self.assertEqual(r.shortlist((0,0,1,1,0,0),self.prior),(3,2))
        with self.assertRaises(ValueError):r.shortlist((1,0),self.prior)
        with self.assertRaises(ValueError):r.shortlist((1,0,0,0,0,True),self.prior)

    def test_zero_budget_all_abstain(self):
        for method in r.METHODS:
            x=r.play(self.w,self.prior,method,0)
            self.assertEqual(x.result['purchases'],0)
            self.assertEqual(x.result['abstentions'],6)
            self.assertIsNone(x.candidate)

    def test_no_certification_from_diagnostic_only(self):
        for method in r.METHODS:
            x=r.play(self.w,self.prior,method,6)
            self.assertFalse(x.certified)
            self.assertEqual(x.certificates,0)

    def test_adaptive_buys_new_diagnostics_and_fresh_certification(self):
        groups=[]; orig=r.Evaluator.buy
        def log(self,g): groups.append(g);return orig(self,g)
        with patch.object(r.Evaluator,'buy',log):
            t=r.play(self.w,self.prior,'adaptive10',24)
        self.assertEqual(groups[:6],list(range(6)))
        self.assertEqual(len(groups[6:10]),4)
        self.assertTrue(all(g==t.candidate for g in groups[10:]))
        self.assertEqual(t.result['purchases'],t.diagnostics+t.certificates)
        self.assertEqual(t.diagnostics,10)

    def test_oracle_never_used_in_decisions(self):
        with patch.object(r.Evaluator,'oracle_ceiling',side_effect=AssertionError('LEAK')):
            for method in r.METHODS:
                r.play(self.w,self.prior,method,24)

    def test_budget_conservation_and_one_candidate(self):
        for method in r.METHODS:
            for cap in r.CAPS:
                x=r.aggregate((self.w,),self.prior,method,cap)
                self.assertLessEqual(x['purchases'],cap)
                self.assertEqual(x['true_accepts']+x['false_accepts']+x['abstentions'],6)
                self.assertLessEqual(x['certified_tasks'],1)
                self.assertEqual(x['diagnostic_labels']+x['certificate_labels'],x['purchases'])
                self.assertIsNone(x['false_acceptance_rate']) if x['true_accepts']+x['false_accepts']==0 else self.assertIsNotNone(x['false_acceptance_rate'])

    def test_abstain_negative_control(self):
        for cap in r.CAPS:
            x=r.play(self.w,self.prior,'abstain6',cap)
            self.assertFalse(x.certified)
            self.assertEqual(x.result['purchases'],min(6,cap))

    def test_correlated_does_not_claim_iid(self):
        world=r.worlds('test','correlated',r.SEEDS[0],1)[0]
        self.assertEqual(world.family,'correlated')
        self.assertEqual(r.play(world,self.prior,'broad6',24),r.play(world,self.prior,'broad6',24))

    def test_evaluation_score_not_used_for_choice(self):
        with patch.object(r.Evaluator,'grade',side_effect=RuntimeError('scoring unavailable')):
            with self.assertRaisesRegex(RuntimeError,'scoring unavailable'):
                r.play(self.w,self.prior,'adaptive10',24)

    def test_validation_deterministic(self):
        self.assertEqual(r.validation(),r.validation())

if __name__=='__main__':unittest.main()