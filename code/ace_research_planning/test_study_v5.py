"""R6-v5: redaction, online probe decisions, resource caps and freeze integrity."""
from dataclasses import replace
from unittest import TestCase, mock
import unittest

from .planning import generate, simulate
from .online_v5 import (OnlinePolicy, PROBE_MODES, PLANNER_MODES,
                        PROBE_WORK_UNITS, visible_world, should_probe, rollout)
from . import online_v5, study_v5
from .study_v5 import (SEEDS, FAMILIES, CONDITIONS, POLICIES,
                       make_world, fit, evaluate, run, policy_rows)


class TestV5Online(TestCase):
    def setUp(self):
        self.world = generate(9530, 'ood', shock=True)

    def test_policy_closed_grammar(self):
        for kind in ('bad', '', None):
            with self.assertRaises(ValueError):
                OnlinePolicy(kind, 'hier')
            with self.assertRaises(ValueError):
                OnlinePolicy('never', kind)
        self.assertEqual(len(POLICIES), len(PROBE_MODES)*len(PLANNER_MODES))

    def test_planner_has_redacted_future_and_probe_uses_past_only(self):
        original = self.world
        self.assertIsNone(visible_world(original).shock)
        self.assertIsNone(visible_world(replace(original, shock=None)).shock)
        recorded=[]
        real=online_v5.should_probe
        def spy(policy, public, *args, **kwargs):
            recorded.append(public.shock)
            return real(policy,public,*args,**kwargs)
        with mock.patch.object(online_v5,'should_probe',side_effect=spy):
            rollout(original,OnlinePolicy('always','hier'),work_limit=900)
        self.assertTrue(recorded)
        self.assertTrue(all(x is None for x in recorded))

    def test_never_vs_always_for_encountered_closure(self):
        never=rollout(self.world,OnlinePolicy('never','hier'),work_limit=900)
        always=rollout(self.world,OnlinePolicy('always','hier'),work_limit=900)
        self.assertTrue(never['success'])
        self.assertTrue(always['success'])
        self.assertEqual(never['probes'],0)
        self.assertGreater(always['probes'],0)
        self.assertEqual(never['failed_actions'],1)
        self.assertEqual(always['failed_actions'],0)
        self.assertEqual(always['positive_probes'],1)
        self.assertTrue(always['recovered'])
        self.assertEqual(never['travel_cost'],always['travel_cost'])
        self.assertGreaterEqual(always['work_units']-never['work_units'],PROBE_WORK_UNITS)

    def test_no_future_sensing_after_closure_discovery(self):
        w=self.world
        r=rollout(w,OnlinePolicy('always','hier'),work_limit=900)
        self.assertEqual(r['positive_probes'],1)
        self.assertEqual(r['discoveries'],1)
        self.assertEqual(len(r['trace']),1)
        self.assertEqual(r['trace'][0]['event'],'probe_blocked')

    def test_static_probes_cost_work_without_benefit(self):
        static=replace(self.world,shock=None)
        a=rollout(static,OnlinePolicy('never','hier'),900)
        b=rollout(static,OnlinePolicy('always','hier'),900)
        self.assertTrue(a['success'] and b['success'])
        self.assertEqual(a['travel_cost'],b['travel_cost'])
        self.assertEqual(b['failed_actions'],0)
        self.assertGreater(b['probes'],0)
        self.assertGreater(b['work_units'],a['work_units'])
        self.assertFalse(b['recovered'])

    def test_online_switch_only_after_discovery(self):
        policy=OnlinePolicy('never','after_discovery_dijkstra')
        no_shock=rollout(replace(self.world,shock=None),policy,work_limit=900)
        shock=rollout(self.world,policy,work_limit=900)
        self.assertEqual(no_shock['switches'],0)
        self.assertEqual(shock['discoveries'],1)
        self.assertEqual(shock['switches'],1)

    def test_budget_exhaustion_safe_and_accounted(self):
        for p in POLICIES:
            r=rollout(self.world,p,work_limit=1)
            self.assertFalse(r['success'])
            self.assertEqual(r['status'],'work_budget')
            self.assertLessEqual(r['work_units'],1)
            self.assertGreaterEqual(r['probes'],0)
        for v in (0,-1,True,2.4):
            with self.assertRaises(ValueError):
                rollout(self.world,OnlinePolicy('never','hier'),work_limit=v)

    def test_visible_decision_rule_feature_not_future(self):
        w=visible_world(self.world)
        edge=(0,w.adjacency[0][0])
        a=should_probe(OnlinePolicy('heavy','hier'),w,*edge,0,False,set())
        self.assertEqual(a, w.cost(*edge)>=4)
        self.assertFalse(should_probe(OnlinePolicy('always','hier'),w,*edge,0,True,set()))
        self.assertFalse(should_probe(OnlinePolicy('always','hier'),w,*edge,0,False,
                                      {tuple(sorted(edge))}))

    def test_disjoint_public_splits_and_mechanism_shift(self):
        self.assertTrue(set(SEEDS['train']).isdisjoint(SEEDS['validation']))
        self.assertTrue(set(SEEDS['train']).isdisjoint(SEEDS['transfer']))
        self.assertTrue(set(SEEDS['validation']).isdisjoint(SEEDS['transfer']))
        self.assertTrue(set(FAMILIES['train']).isdisjoint(FAMILIES['transfer']))
        for split in SEEDS:
            for family in FAMILIES[split]:
                for cond in CONDITIONS:
                    w=make_world(split,SEEDS[split][0],family,cond)
                    self.assertTrue(w.weights)
                    self.assertIsNone(w.shock) if cond=='static' else self.assertIsNotNone(w.shock)

    def test_no_transfer_argument_to_selector(self):
        tr=evaluate('train',1,300)
        va=evaluate('validation',1,300)
        chosen,audit=fit(tr,va)
        self.assertIn(chosen,POLICIES)
        self.assertLessEqual(len(audit),8)
        with self.assertRaises(TypeError):
            fit(tr,va,transfer=[])
        self.assertEqual(len(policy_rows(tr,chosen)), len(FAMILIES['train'])*len(CONDITIONS))

    def test_transfer_generation_after_freeze(self):
        real=study_v5.evaluate
        real_fit=study_v5.fit
        events=[]
        def capture(split,*args,**kwargs):
            events.append(split)
            return real(split,*args,**kwargs)
        def freeze(*args,**kwargs):
            events.append('freeze')
            return real_fit(*args,**kwargs)
        with mock.patch.object(study_v5,'evaluate',side_effect=capture),\
             mock.patch.object(study_v5,'fit',side_effect=freeze):
            run(1,1,1,budgets=(300,))
        self.assertEqual(events,['train','validation','freeze','transfer'])

    def test_replay_deterministic_on_small_public_case(self):
        a=run(1,1,1,budgets=(300,))
        b=run(1,1,1,budgets=(300,))
        self.assertEqual(a,b)
        self.assertEqual(len(a['transfer_rows']),len(FAMILIES['transfer'])*len(CONDITIONS)*len(POLICIES))


    def test_no_probe_parity_with_legacy_planner(self):
        for world in (self.world, replace(self.world, shock=None),
                      make_world('transfer', SEEDS['transfer'][0], 'interior_portals', 'neutral_closure')):
            for mode, legacy in (("hier", "hier_replan"), ("dijkstra", "dijkstra")):
                fresh=rollout(world,OnlinePolicy("never",mode),work_limit=900)
                prior=simulate(world,legacy,limit=1800,work_limit=900)
                self.assertEqual(fresh['success'],prior['success'])
                self.assertEqual(fresh['travel_cost'],prior['cost'])
                self.assertEqual(fresh['work_units'],prior['work_units'])
                self.assertEqual(fresh['expanded'],prior['expanded'])

    def test_recovery_outcomes_are_event_conditioned(self):
        for policy in POLICIES:
            for w in (self.world,replace(self.world,shock=None)):
                row=rollout(w,policy,work_limit=900)
                self.assertEqual(row['discoveries'],row['positive_probes']+row['failed_actions'])
                self.assertLessEqual(row['discoveries'],1)
                self.assertEqual(row['recovered'], bool(row['discoveries']) and row['success'])

    def test_only_benchmark_oracle_sees_postshock_cost(self):
        from .study_v2 import independent_optimal_cost
        for p in (OnlinePolicy('never','hier'), OnlinePolicy('never','dijkstra'),
                  OnlinePolicy('always','hier')):
            row=rollout(self.world,p,work_limit=900)
            if row['success']:
                bound=independent_optimal_cost(self.world,frozenset((self.world.shock,)))
                self.assertIsNotNone(bound)
                self.assertGreaterEqual(row['travel_cost'],bound)

    def test_no_invalid_scoring_inputs(self):
        for val in (0,19,True,1.5):
            with self.assertRaises(ValueError):
                run(n_train=val,n_validation=1,n_transfer=1,budgets=(300,))
        for budgets in ((0,), (900,300),(300,300),(True,), (10001,)):
            with self.assertRaises(ValueError):
                run(1,1,1,budgets=budgets)
        with self.assertRaises(ValueError):
            make_world('train', SEEDS['transfer'][0], FAMILIES['train'][0],'static')


if __name__ == '__main__':
    unittest.main()
