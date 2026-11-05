"""R6-v6: information boundary, calibration, negative shift and resource accounting."""
from dataclasses import replace
from unittest import TestCase, mock

from .planning import generate
from .online_v5 import OnlinePolicy, rollout, visible_world
from .metareason_v6 import (RiskModel, POLICIES, salience, fit_risk, edge_priors,
                            make_decider, run_policy, utility)
from . import study_v6


class TestV6(TestCase):
    def setUp(self):
        self.world = study_v6.sample_world('train',study_v6.SEEDS['train'][0],
                                          study_v6.FAMILIES['train'][0])
        self.model=fit_risk((self.world,replace(self.world,shock=None)))

    def test_original_controller_unchanged_without_callback(self):
        a=rollout(self.world,OnlinePolicy('never','hier'),work_limit=900)
        b=rollout(self.world,OnlinePolicy('never','hier'),work_limit=900,decision_fn=None)
        self.assertEqual(a,b)
        self.assertNotIn('decision_calls',a)

    def test_decider_gets_only_redacted_world(self):
        observations=[]
        def spy(public,*args):
            observations.append(public.shock)
            return (False,0)
        rollout(self.world,OnlinePolicy('never','hier'),work_limit=900,decision_fn=spy)
        self.assertTrue(observations)
        self.assertEqual(set(observations), {None})

    def test_same_first_decision_with_different_unobserved_shock(self):
        world=replace(self.world,shock=None)
        edge=(0,world.adjacency[0][0])
        for mode in POLICIES:
            d1=make_decider(mode,self.model)
            d2=make_decider(mode,self.model)
            self.assertEqual(d1(world,*edge,0,False,frozenset(),frozenset()),
                             d2(world,*edge,0,False,frozenset(),frozenset()))
        self.assertEqual(salience(world),salience(self.world))
        self.assertEqual(edge_priors(self.model,world),edge_priors(self.model,self.world))

    def test_priors_nonnegative_and_sum_to_shock_prevalence(self):
        p=edge_priors(self.model,self.world)
        self.assertTrue(all(0<=v<=1 for v in p.values()))
        self.assertAlmostEqual(sum(p.values()),self.model.shock_frequency)

    def test_posterior_updates_after_known_open_and_discovery(self):
        public=visible_world(self.world)
        top=salience(public)
        edge=next(iter(top))
        d=make_decider('learned_voi',self.model)
        a=d(public,*edge,0,False,frozenset(),frozenset())
        b=d(public,*edge,1,False,frozenset({edge}),frozenset())
        c=d(public,*edge,1,True,frozenset(),frozenset())
        self.assertIsInstance(a[0],bool)
        self.assertFalse(b[0]);self.assertFalse(c[0])

    def test_fail_closed_on_bad_callback_return_and_missing_model(self):
        for result in ((True,-1),('yes',0),(False,True)):
            with self.assertRaises(ValueError):
                rollout(self.world,OnlinePolicy('never','hier'),900,
                        decision_fn=lambda *_:result)
        with self.assertRaises(ValueError):
            make_decider('learned_voi')
        with self.assertRaises(ValueError):
            make_decider('anything',self.model)
        with self.assertRaises(ValueError):
            fit_risk(())
        with self.assertRaises(ValueError):
            RiskModel(-1,.5,.8,2,1,(1,2))

    def test_all_callbacks_share_operation_caps(self):
        for mode in POLICIES:
            for limit in (1,5,25):
                row=run_policy(self.world,mode,self.model,limit)
                self.assertLessEqual(row['work_units'],limit)
                self.assertFalse(row['success'])
                self.assertEqual(row['status'],'work_budget')

    def test_successful_moves_are_observed_open(self):
        public=visible_world(self.world)
        seen=[]
        def capture(w,u,v,steps,discovered,known_open,closed):
            seen.append((steps, known_open))
            return False,0
        rollout(self.world,OnlinePolicy('never','hier'),900,decision_fn=capture)
        after=[known for steps,known in seen if steps >= 1]
        self.assertTrue(after)
        self.assertTrue(any(known for known in after))

    def test_simulator_shocks_are_solvable_and_policy_independent(self):
        from .study_v2 import independent_optimal_cost
        for split in study_v6.SEEDS:
            seed=study_v6.SEEDS[split][0]
            for family in study_v6.FAMILIES[split]:
                world=study_v6.sample_world(split,seed,family)
                self.assertEqual(world,study_v6.sample_world(split,seed,family))
                blocked=frozenset((world.shock,)) if world.shock else frozenset()
                self.assertIsNotNone(independent_optimal_cost(world,blocked))

    def test_disjoint_seeds_and_family_shift(self):
        splits=study_v6.SEEDS
        for a in splits:
            for b in splits:
                if a!=b:self.assertFalse(set(splits[a])&set(splits[b]))
        self.assertFalse(set(study_v6.FAMILIES['train']) & set(study_v6.FAMILIES['shift_transfer']))

    def test_calibration_input_uses_ground_truth_for_metrics_only(self):
        w=study_v6.worlds('train',1)
        score=study_v6.calibration(w,self.model)
        self.assertGreater(score['labelled_edges'],0)
        self.assertLessEqual(score['positives'],len(w))
        self.assertTrue(0 <= score['brier'] <= 1)

    def test_policy_freeze_before_transfer_generation(self):
        events=[]
        original=study_v6.worlds
        def watcher(split,*args):
            events.append(split)
            return original(split,*args)
        with mock.patch.object(study_v6,'worlds',side_effect=watcher):
            result=study_v6.run(1,1,1,budgets=(300,))
        self.assertEqual(events,['train','validation','iid_transfer',
                                 'shift_transfer','no_shock_transfer'])
        self.assertEqual(len(result['pretransfer_receipt_sha256']),64)

    def test_replay_small(self):
        x=study_v6.run(1,1,1,budgets=(300,))
        y=study_v6.run(1,1,1,budgets=(300,))
        self.assertEqual(x,y)
        self.assertEqual(x['counts']['train'],3)
        self.assertIn('equivalent_to_salient',x['transfer']['iid_transfer']['budgets']['300'])

    def test_bad_split_and_budgets(self):
        for n in (0, -1, True, 1.5, 100):
            with self.assertRaises(ValueError):
                study_v6.worlds('train',n)
        for b in ((0,),(900,300),(300,300),(True,)):
            with self.assertRaises(ValueError):
                study_v6.run(1,1,1,budgets=b)
        with self.assertRaises(ValueError):
            study_v6.sample_world('train',study_v6.SEEDS['shift_transfer'][0],
                                  study_v6.FAMILIES['train'][0])

    def test_paired_seed_cluster_not_per_row_independence(self):
        w=study_v6.worlds('train',1)
        rows,_=study_v6.evaluate(w,self.model,900)
        comparison=study_v6.paired(rows,'learned_voi','never',draws=99)
        self.assertEqual(comparison['seed_clusters'],1)
        self.assertEqual(comparison['pairs'],3)
        self.assertEqual(len(comparison['descriptive_cluster_bootstrap_95pct']),2)

    def test_utility_replays_original_formula(self):
        from .study_v5 import utility as old
        row=run_policy(self.world,'never',self.model,900)
        reference=12
        self.assertAlmostEqual(utility(row,reference),old(dict(row,reference=reference)))
