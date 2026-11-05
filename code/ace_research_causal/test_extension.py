"""Focused and adversarial stdlib-only checks for R5 nonlinear extension."""
import json
import math
import random
import unittest
from dataclasses import replace

from ace_research_causal import extension as e


class ExtensionTests(unittest.TestCase):
    def test_unknown_intervention_is_rejected(self):
        w = e.world(600000, confounded=True)
        with self.assertRaises(ValueError):
            e.observe(w, 'none', random.Random(1))
        with self.assertRaises(ValueError):
            e.truth(w, 'none')
        with self.assertRaises(ValueError):
            e.prediction(e.random_model(1), 'none')

    def test_exhausted_budget_is_fail_closed(self):
        q = e.Budget(e.world(1, confounded=True), 123, 1)
        q.ask('obs')
        with self.assertRaises(RuntimeError):
            q.ask('joint')
        self.assertEqual(q.used, 1)

    def test_quadratic_ols_exact(self):
        data = [(x, 2 + 3*x - 4*x*x) for x in (-2, -1, 0, 1, 2)]
        for got, want in zip(e.fit_quad(data), (2, 3, -4)):
            self.assertAlmostEqual(got, want, places=5)

    def test_outcome_basis_exact(self):
        coefs = (3., -2., 1., 4., -.8, 2.)
        data = []
        for x in (-2., -1., 0., 1., 2.):
            for m in (-2., -1., 0., 1., 2.):
                y = sum(z*c for z,c in zip(e.y_features(x,m), coefs))
                data.append((x,m,y))
        for got, want in zip(e.fit_y(data), coefs):
            self.assertAlmostEqual(got, want, places=5)

    def test_do_mean_matches_independent_simulation_all_directions(self):
        for direction in (0,1):
            w = replace(e.world(600002+direction,confounded=True,cubic=True),
                        direction=direction)
            for mode in ('x', 'm', 'joint'):
                rng=random.Random(321+direction)
                observed=[]
                for _ in range(20000):
                    u=rng.gauss(0,1)
                    root=u+rng.gauss(0,.25)
                    child_noise=rng.gauss(0,.2)
                    if mode=='joint':
                        x,m=.9,-.8
                    elif direction==0:
                        x=.9 if mode=='x' else root
                        m=e.mediator(w,x)+child_noise if mode=='x' else -.8
                    else:
                        m=-.8 if mode=='m' else root
                        x=e.mediator(w,m)+child_noise if mode=='m' else .9
                    observed.append(e.outcome(w,x,m,u,0))
                true=e.truth(w,mode,.9,-.8)
                self.assertAlmostEqual(sum(observed)/len(observed),true,delta=.09)

    def test_oracle_quadratic_model_has_exact_target_means(self):
        for d in (0,1):
            w = replace(e.world(600002+d,confounded=True,cubic=False),direction=d)
            model = e.Estimator(d,w.a,w.q,1+.25**2,.2**2,
                                (0,w.b,w.c,w.t,w.p,w.r))
            for mode in ('x', 'm', 'joint'):
                self.assertAlmostEqual(e.truth(w,mode,1.5,-1.5),
                                       e.prediction(model,mode,1.5,-1.5),places=9)

    def test_shift_rewires_without_mutating_coefficients(self):
        w=e.world(600000,confounded=True)
        other=e.rewired(w)
        self.assertEqual(w.direction,1-other.direction)
        self.assertEqual(replace(w,direction=other.direction),other)

    def test_train_budgets_matched_and_direction_not_input(self):
        for seed in (600004,600005):
            w=e.world(seed,confounded=True)
            for arm in ('causal','causal_joint_only','obs_oracle_direction','obs_fixed_direction'):
                model,spent=e.train(w,seed*37+1,arm)
                self.assertEqual(spent,120)
                self.assertTrue(all(math.isfinite(v) for v in model.y_coef))

    def test_pooled_and_joint_only_share_mechanism(self):
        w=e.world(600007,confounded=True)
        a,_=e.train(w,55,'causal')
        b,_=e.train(w,55,'causal_joint_only')
        self.assertEqual((a.direction,a.a,a.q,a.root_var,a.child_var),
                         (b.direction,b.a,b.q,b.root_var,b.child_var))

    def test_intervention_query_ranges_are_disjoint_from_eval_points(self):
        self.assertGreater(e.TEST_VALUE, e.INTERVENTION_RANGE)
        for direction in (0,1):
            w=replace(e.world(600000,confounded=True),direction=direction)
            rng=random.Random(5)
            for mode in ('x','m','joint'):
                for _ in range(100):
                    x,m,_=e.observe(w,mode,rng)
                    if mode in ('x','joint'):
                        self.assertLessEqual(abs(x),e.INTERVENTION_RANGE)
                    if mode in ('m','joint'):
                        self.assertLessEqual(abs(m),e.INTERVENTION_RANGE)

    def test_metric_regret_is_nonnegative(self):
        w=e.world(600001,confounded=True)
        for k in range(20):
            z=e.metrics(w,e.random_model(k))
            self.assertGreaterEqual(z['planning_regret'],0)

    def test_counterfactual_average_delta(self):
        for direction in (0,1):
            w=replace(e.world(600000,confounded=True,cubic=True),direction=direction)
            true_ate=e.truth(w,'x',1.5,0)-e.truth(w,'x',-1.5,0)
            # Same exogenous unit draw is used for both potential outcomes.
            rng=random.Random(10+direction)
            deltas=[]
            for _ in range(15000):
                u=rng.gauss(0,1)
                root=u+rng.gauss(0,.25)
                noise=rng.gauss(0,.2)
                yy=[]
                for x in (-1.5,1.5):
                    m=e.mediator(w,x)+noise if direction==0 else root
                    yy.append(e.outcome(w,x,m,u,0))
                deltas.append(yy[1]-yy[0])
            self.assertAlmostEqual(sum(deltas)/len(deltas),true_ate,delta=.05)

    def test_replay_is_byte_deterministic(self):
        a=json.dumps(e.experiment(3),sort_keys=True,allow_nan=False)
        b=json.dumps(e.experiment(3),sort_keys=True,allow_nan=False)
        self.assertEqual(a,b)

    def test_seeds_disjoint_and_cubic_outside_learner_basis(self):
        self.assertEqual(e.world(800001,confounded=True,cubic=False).h,0)
        self.assertNotEqual(e.world(800001,confounded=True,cubic=True).h,0)
        self.assertNotEqual(e.world(600000,confounded=True),
                            e.world(700000,confounded=False))

    def test_ineligible_budget_rejected(self):
        with self.assertRaises(ValueError):
            e.train(e.world(1,confounded=False),1,'causal',119)
        with self.assertRaises(ValueError):
            e.experiment(1)
        with self.assertRaises(ValueError):
            e.experiment(1001)


if __name__ == '__main__':
    unittest.main()
