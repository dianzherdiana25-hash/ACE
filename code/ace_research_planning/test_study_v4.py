"""R6-v4 instrumented budget and train/validation/transfer integrity tests."""
from dataclasses import replace
from unittest import TestCase, mock
import json
import unittest

from .planning import (Meter, WorkBudgetExceeded, forced_key_order_certificate,
                       generate, simulate)
from .study_v4 import (SEEDS, FAMILIES, CONDITIONS, FEATURES, METHODS, Selector, assess, candidates,
                       evaluate_worlds, features, fit, make_world, run, selected_rows)


class V4IntegrityTests(TestCase):
    def test_disjoint_splits_and_new_mechanisms(self):
        self.assertTrue(set(SEEDS['train']).isdisjoint(SEEDS['validation']))
        self.assertTrue(set(SEEDS['train']).isdisjoint(SEEDS['transfer']))
        self.assertTrue(set(SEEDS['validation']).isdisjoint(SEEDS['transfer']))
        self.assertTrue(set(FAMILIES['transfer']).isdisjoint(FAMILIES['train']))
        for split in FAMILIES:
            for fam in FAMILIES[split]:
                w=make_world(split,fam,SEEDS[split][0],'static')
                self.assertGreater(len(w.weights),0)
                self.assertEqual(len(features(w)),len(FEATURES))

    def test_interior_portals_really_nonterminal(self):
        seed=SEEDS['transfer'][1]
        ordinary=make_world('transfer','weight_shift',seed,'static')
        portals=make_world('transfer','interior_portals',seed,'static')
        added={(u,v) for u,v,_ in portals.weights} - {(u,v) for u,v,_ in ordinary.weights}
        self.assertGreaterEqual(len(added),2)
        terminals=set(portals.keys)|{0,portals.goal}
        self.assertTrue(all(u not in terminals and v not in terminals for u,v in added))

    def test_features_ignore_future_shock(self):
        seed=SEEDS['transfer'][0]
        w=make_world('transfer','gated_bypass',seed,'static')
        revealed=make_world('transfer','gated_bypass',seed,'neutral_closure')
        self.assertEqual(features(w),features(revealed))
        self.assertFalse(forced_key_order_certificate(w))

    def test_selector_rejects_unknown_feature(self):
        self.assertEqual(Selector(None,'dijkstra','dijkstra').choose({}),'dijkstra')
        with self.assertRaises(ValueError):
            Selector('future_shock','astar','dijkstra').choose({})
        self.assertTrue(all(c.false_method in METHODS and c.true_method in METHODS for c in candidates()))
        self.assertEqual(len(candidates()),len(METHODS)+len(FEATURES)*len(METHODS)*(len(METHODS)-1))

    def test_meter_exact_cap_and_quota_failure(self):
        w=generate(21231,'ood',False)
        for meth in METHODS:
            a=simulate(w,meth,limit=1800,work_limit=1)
            self.assertFalse(a['success'])
            self.assertEqual(a['work_units'],1)
            self.assertEqual(a['status'],'work_budget')
            self.assertTrue(a['work_exceeded'])
            b=simulate(w,meth,limit=1800,work_limit=250)
            self.assertLessEqual(b['work_units'],250)
        with self.assertRaises(ValueError):
            simulate(w,'astar',work_limit=0)
        with self.assertRaises(ValueError):
            simulate(w,'astar',work_limit=True)
        with self.assertRaises(ValueError):
            simulate(w,'astar',work_limit=1.5)

    def test_new_meter_no_effect_when_not_enabled(self):
        w=generate(9501,'ood',False)
        a=simulate(w,'astar',limit=1800)
        b=simulate(w,'astar',limit=1800,work_limit=30000)
        for key in a:
            self.assertEqual(a[key],b[key],key)

    def test_val_only_selection_and_no_transfer_argument(self):
        tr=evaluate_worlds('train',1,250)
        val=evaluate_worlds('validation',1,250)
        chosen,rank=fit(tr,val)
        self.assertIn(chosen,candidates())
        self.assertGreater(len(rank),0)
        self.assertEqual(assess(val,chosen)['n'],len(FAMILIES['validation'])*2)
        with self.assertRaises(TypeError):
            fit(tr,val,transfer=[])
        self.assertEqual(len(selected_rows(tr,chosen)),len(FAMILIES['train'])*2)

    def test_transfer_evaluated_only_after_policy_frozen(self):
        # Patch the named functions at the interface, recording call order.
        from . import study_v4
        actual_eval=study_v4.evaluate_worlds
        actual_fit=study_v4.fit
        events=[]
        def capture_eval(*args,**kwargs):
            events.append('evaluate:'+args[0])
            return actual_eval(*args,**kwargs)
        def capture_fit(*args,**kwargs):
            events.append('freeze')
            return actual_fit(*args,**kwargs)
        with mock.patch.object(study_v4,'evaluate_worlds',side_effect=capture_eval), mock.patch.object(study_v4,'fit',side_effect=capture_fit):
            a=run(1,1,1,budgets=(250,))
        self.assertEqual(events,['evaluate:train','evaluate:validation','freeze','evaluate:transfer'])
        self.assertEqual(a,run(1,1,1,budgets=(250,)))
        self.assertEqual(len(a['transfer_rows']),len(FAMILIES['transfer'])*len(CONDITIONS)*len(METHODS))

    def test_invalid_protocol_inputs(self):
        for n in (0,25,True,1.2):
            with self.assertRaises(ValueError):
                run(n,1,1,budgets=(250,))
        for b in ((0,),(2200,250),(250,250),(True,),(30001,)):
            with self.assertRaises(ValueError):
                run(1,1,1,budgets=b)
        with self.assertRaises(ValueError):
            make_world('transfer','ordered_grid',SEEDS['transfer'][0],'static')
        with self.assertRaises(ValueError):
            make_world('train','ordered_grid',SEEDS['transfer'][0],'static')


if __name__ == '__main__':
    unittest.main()
