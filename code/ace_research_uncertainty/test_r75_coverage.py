"""R7.5 pre-final unit tests; intentionally no final_once() call."""
import hashlib
import math
import unittest
from unittest.mock import patch
from . import r75_coverage as r


class R75Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior, cls.source_cost = r.fit_source_prior()
        cls.world = r.worlds('validation','stable',r.SEED_TRAIN,1)[0]

    def test_precommitted_families_and_cap(self):
        self.assertEqual(len(r.FAMILIES),7)
        self.assertEqual(r.BUDGETS,(0,6,12,18,24))
        self.assertEqual(r.ALPHA,.10)
        self.assertEqual(r.P0,.8)

    def test_training_cost_conserved(self):
        self.assertEqual(self.source_cost,1296)
        self.assertEqual(len(self.prior),6)
        self.assertTrue(all(0 < p < 1 for p in self.prior))

    def test_disjoint_task_names(self):
        banks=[r.worlds('train','stable',r.SEED_TRAIN,18),
               r.worlds('validation','stable',r.SEED_TRAIN,12)]
        banks.extend(r.worlds('test',f,s,24) for f in r.FAMILIES for s in r.FINAL_SEEDS)
        ids=[w.uid for bank in banks for w in bank]
        self.assertEqual(len(ids),18+12+7*3*24)
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(uid.startswith('r75:') for uid in ids))

    def test_no_old_test_world_namespace(self):
        self.assertFalse(any('r74' in w.uid for w in r.worlds('test','new23',20261109,24)))

    def test_wrong_split_or_seed_rejected(self):
        for args in [('train','new23',r.SEED_TRAIN,2),
                     ('validation','stable',20261109,2),
                     ('test','stable',20261108,2),
                     ('unknown','stable',r.SEED_TRAIN,2),
                     ('test','new23',20261109,True)]:
            with self.assertRaises(ValueError):r.worlds(*args)

    def test_all_null_has_no_safe_strata(self):
        bank=r.worlds('test','all_null',20261109,24)
        self.assertTrue(all(not any(p >= r.P0 for p in w.p) for w in bank))

    def test_source_fit_no_final_reads(self):
        with patch.object(r,'worlds',wraps=r.worlds) as make:
            r.fit_source_prior()
            self.assertTrue(all(c.args[0]=='train' for c in make.call_args_list))

    def test_e_process_supermartingale_under_iid_null(self):
        for p1 in (.96,.99):
            for true_p in (0,.1,.5,.79,.8):
                self.assertLessEqual(r.null_expectation(true_p,p1),1+1e-12)
            self.assertAlmostEqual(r.null_expectation(.8,p1),1)
            self.assertGreater(r.null_expectation(.95,p1),1)

    def test_e_step_validation(self):
        for label in (True,-1,2):
            with self.assertRaises(ValueError):r.multiplier(label,.99)
        with self.assertRaises(ValueError):r.multiplier(1,.92)

    def test_candidate_chooses_new_groups(self):
        obs=((0,0),(1,0),(2,1),(3,0),(4,0),(5,0),
             (0,0),(1,0),(2,1),(3,0),(4,0),(5,0))
        self.assertEqual(r.select_candidate(obs,self.prior,tuple(range(6))),2)
        with self.assertRaises(ValueError):r.select_candidate(obs[:-1],self.prior,tuple(range(6)))

    def test_diagnostic_order_is_fixed_and_separate(self):
        queries=[]
        orig=r.Evaluator.buy
        def traced(self,g):
            queries.append(g)
            return orig(self,g)
        with patch.object(r.Evaluator,'buy',traced):
            row=r.play(self.world,self.prior,'full099',24)
        self.assertEqual(queries[:12],list(r.FULL_SEQUENCE))
        self.assertTrue(all(g==row.selected for g in queries[12:]))
        self.assertEqual(len(queries),row.diag_count+row.cert_count)

    def test_narrow_diagnostic_control(self):
        queries=[]
        orig=r.Evaluator.buy
        def traced(self,g):
            queries.append(g)
            return orig(self,g)
        with patch.object(r.Evaluator,'buy',traced):
            row=r.play(self.world,self.prior,'narrow099',24)
        self.assertEqual(queries[:6],list(r.NARROW_SEQUENCE))
        self.assertIn(row.selected,(0,4,5))

    def test_no_scoring_oracle_called_by_policy(self):
        with patch.object(r.Evaluator,'oracle_ceiling',side_effect=AssertionError('privilege leak')):
            for method in r.METHODS:
                r.play(self.world,self.prior,method,24)

    def test_hard_online_caps(self):
        for method in r.METHODS:
            for cap in r.BUDGETS:
                rec=r.play(self.world,self.prior,method,cap)
                self.assertLessEqual(rec.grade['purchases'],cap)
                self.assertEqual(rec.grade['purchases'],rec.diag_count+rec.cert_count)
                self.assertLessEqual(rec.grade['true_accepts']+rec.grade['false_accepts'],1)

    def test_minimum_label_requirements(self):
        for cap in (0,6,12):
            row=r.play(self.world,self.prior,'full099',cap)
            self.assertFalse(row.certified)
            self.assertEqual(row.cert_count,0)
        self.assertEqual(r.play(self.world,self.prior,'diag_abstain',24).cert_count,0)

    def test_invalid_group_and_budget(self):
        ev=r.Evaluator(self.world,1)
        for bad in (-1,6,True,1.5):
            with self.assertRaises(ValueError):ev.buy(bad)
        ev.buy(0)
        with self.assertRaises(RuntimeError):ev.buy(0)
        with self.assertRaises(ValueError):r.play(self.world,self.prior,'full099',25)
        with self.assertRaises(ValueError):r.play(self.world,self.prior,'oracle',24)

    def test_conditional_false_accept_rate_null_if_none(self):
        record=r.summarize((self.world,),self.prior,'diag_abstain',24)
        self.assertIsNone(record['false_acceptance_rate'])
        self.assertEqual(record['false_accepts'],0)

    def test_replay(self):
        a=r.validation()
        b=r.validation()
        self.assertEqual(a,b)

    def test_evaluator_scoring_namespace_separate(self):
        ev=r.Evaluator(self.world,2)
        base=ev.grade(None,(.5,)*6)
        ev.buy(0);ev.buy(0)
        other=ev.grade(None,(.5,)*6)
        self.assertEqual(base['bins'],other['bins'])
        self.assertEqual(base['brier_sum'],other['brier_sum'])

    def test_correlated_replies_reuse_pairs(self):
        world=r.worlds('test','correlated',20261109,1)[0]
        e=r.Evaluator(world,4)
        self.assertEqual(e.buy(0),e.buy(0))
        self.assertEqual(e.buy(1),e.buy(1))

    def test_e_threshold_finite_cap(self):
        self.assertLess((.99/.8)**10,10)
        self.assertGreater((.99/.8)**11,10)
        self.assertLess((.96/.8)**12,10)
        self.assertGreater((.96/.8)**13,10)

    def test_prefix_not_reused_in_certification_evidence(self):
        # Cert evidence is exactly the product of additional labels, and
        # any 0 certification labels leaves E=1 regardless of diagnostics.
        row=r.play(self.world,self.prior,'full099',12)
        self.assertEqual(row.cert_count,0)
        self.assertEqual(row.e_final,1.)

    def test_metric_arithmetic_and_oracle_ceiling(self):
        w=r.worlds('validation','stable',r.SEED_TRAIN,3)
        for method in r.METHODS:
            rec=r.summarize(w,self.prior,method,24)
            self.assertEqual(rec['abstained']+rec['true_accepts']+rec['false_accepts'],len(w)*6)
            self.assertEqual(rec['utility'],20*rec['true_accepts']-60*rec['false_accepts']-2*rec['abstained']-rec['purchases'])
            self.assertLessEqual(rec['true_accepts'],sum(r.Evaluator(t,0).oracle_ceiling() for t in w))


if __name__=='__main__':unittest.main()
