"""Independent analytic and Monte Carlo checks for causal R5 stress protocol."""
import hashlib
import json
import math
import random
import unittest
from dataclasses import replace
from ace_research_causal import stress as s


class StressTests(unittest.TestCase):
    def test_effect_decomposition_and_ground_truth(self):
        w=s.World(.5, .3, .8, 3.0, -.2, .7)
        self.assertAlmostEqual(w.tau,.7)
        self.assertAlmostEqual(s.do_mean(w,2), .7*2-.2*8)

    def test_analytic_do_matches_independent_simulator(self):
        w=s.World(.35,.7,-.8,2.,-.25,.7)
        for x in (-2.,2.):
            rng=random.Random(931+int(x))
            observed=[]
            for _ in range(16000):
                u=rng.gauss(0,1)
                mediator=w.a*x+rng.gauss(0,.3)
                y=w.b*x+w.c*mediator+w.gamma*x**3+w.d*u+rng.gauss(0,.5)
                observed.append(y)
            self.assertAlmostEqual(sum(observed)/len(observed),s.do_mean(w,x),delta=.055)

    def test_randomized_encouragement_reduced_form(self):
        w=s.World(.3,.7,.4,1.6,-.15,.6)
        rng=random.Random(231)
        estimates={}
        for z in (-1.5,1.5):
            xs,ys=[],[]
            for _ in range(14000):
                _,x,y,_=s.generate(w,rng,setting=z)
                xs.append(x);ys.append(y)
            estimates[z]=(sum(xs)/len(xs),sum(ys)/len(ys))
        delta_x=estimates[1.5][0]-estimates[-1.5][0]
        delta_y=estimates[1.5][1]-estimates[-1.5][1]
        true_delta=s.do_mean(w,1.5)-s.do_mean(w,-1.5)
        self.assertAlmostEqual(delta_x,w.compliance*3,delta=.08)
        self.assertAlmostEqual(delta_y,w.compliance*true_delta,delta=.10)

    def test_equal_training_budget_and_random_no_samples(self):
        w=s.make_world(410000,'strong_linear')
        data_r=s.sample(w,4,True)
        data_o=s.sample(w,5,False)
        self.assertEqual(len(data_r),s.TRAIN_ROWS)
        self.assertEqual(len(data_o),s.TRAIN_ROWS)
        for name in ('itt_linear','iv_linear','iv_cubic'):
            self.assertTrue(math.isfinite(s.estimate(data_r,name).contrast()))
        for name in ('obs_linear','obs_cubic'):
            self.assertTrue(math.isfinite(s.estimate(data_o,name).contrast()))
        self.assertIsInstance(s.random_fit(1),s.Fit)

    def test_balanced_instrument_and_bounded_assignments(self):
        w=s.make_world(410000,'strong_linear')
        rows=s.sample(w,8,True)
        self.assertEqual(sorted(row[0] for row in rows),sorted(s.SETTINGS*40))
        self.assertTrue(all(abs(row[0])<=1.5 for row in rows))
        self.assertEqual({row[0] for row in s.sample(w,8,False)},{0.0})

    def test_no_compliance_closed_gate(self):
        w=s.World(.4,.3,.5,1.,.0,0.)
        rows=s.sample(w,19,True)
        fit=s.estimate(rows,'iv_cubic')
        self.assertEqual(s.gated_action(rows,19,fit),0)

    def test_exact_zero_effect_regret(self):
        w=s.World(.4,-.4,.999,1.4,0,.6)
        w=replace(w,b=-w.a*w.c)
        for action in (-1,0,1):
            y=s.evaluate(w,s.random_fit(1),action)
            self.assertAlmostEqual(y['regret'],0,places=10)

    def test_wrong_sign_regret_is_double_abstention(self):
        w=s.World(0.,1.,.4,1.8,0.,.5)
        y_bad=s.evaluate(w,s.Fit(-1,0,.5),-1)
        y_abstain=s.evaluate(w,s.Fit(-1,0,.5),0)
        self.assertAlmostEqual(y_bad['regret'],2*y_abstain['regret'])

    def test_nonidentifiability_under_zero_compliance(self):
        # If C=0, randomized assignment never changes the actual treatment.
        w=s.World(.2,.8,.6,1.0,0,0)
        rows=s.sample(w,27,True)
        x_by_z={z:[row[1] for row in rows if row[0]==z] for z in s.SETTINGS}
        self.assertEqual(len(x_by_z[-1.5]),40)
        # Finite-sample correlations may remain by chance: no claim of exact zero.
        self.assertEqual(w.compliance,0)
        self.assertEqual(s.gated_action(rows,27,s.estimate(rows,'iv_cubic')),0)

    def test_transport_true_do_effect_invariant(self):
        w=s.make_world(450000,'confounder_shift')
        shifted=replace(w,d=-w.d)
        self.assertAlmostEqual(s.do_mean(w,2.),s.do_mean(shifted,2.))
        self.assertAlmostEqual(s.do_mean(w,-2.),s.do_mean(shifted,-2.))

    def test_no_result_leakage_to_estimators(self):
        w=s.make_world(440000,'nonlinear_transport')
        rows=s.sample(w,23,True)
        fit=s.estimate(rows,'iv_cubic')
        saved=fit.contrast()
        modified=replace(w,b=w.b+100.,gamma=w.gamma+50.)
        self.assertEqual(saved,s.estimate(rows,'iv_cubic').contrast())
        self.assertNotEqual(s.do_mean(modified,2.),s.do_mean(w,2.))

    def test_invalid_parameter_modes_fail(self):
        with self.assertRaises(ValueError): s.make_world(1,'invalid')
        with self.assertRaises(ValueError): s.estimate([], 'not_a_model')
        with self.assertRaises(ValueError): s.sample(s.make_world(1,'strong_linear'),1,True,159)
        for n in (1,301):
            with self.assertRaises(ValueError):s.experiment(n)

    def test_ols_exact_known_cubic(self):
        zs=s.SETTINGS
        X=[(1.,z,z**3) for z in zs]
        targets=[.7+2*z-.4*z**3 for z in zs]
        for got,want in zip(s.ols(X,targets),(.7,2.,-.4)):
            self.assertAlmostEqual(got,want,places=7)

    def test_deterministic_replay(self):
        x=json.dumps(s.experiment(2),sort_keys=True,allow_nan=False)
        y=json.dumps(s.experiment(2),sort_keys=True,allow_nan=False)
        self.assertEqual(hashlib.sha256(x.encode()).hexdigest(),
                         hashlib.sha256(y.encode()).hexdigest())

    def test_near_null_ground_truth_is_small(self):
        for i in range(25):
            w=s.make_world(430000+i,'near_null_effect')
            self.assertLessEqual(abs(w.tau),.035+1.e-10)
            self.assertLessEqual(abs(w.a),.04+1.e-10)

    def test_nonlinear_sign_flip_exists(self):
        for i in range(25):
            w=s.make_world(440000+i,'nonlinear_transport')
            # Sign of local derivative near zero differs from the tested do-contrast.
            self.assertLess(w.tau*(s.do_mean(w,2)-s.do_mean(w,-2)),0)


if __name__=='__main__':
    unittest.main()
