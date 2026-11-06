"""Executable invariants, negative control and replay checks."""
import math
import random
import unittest
from . import study as s

class StudyTests(unittest.TestCase):
    def test_true_intervention_formulas(self):
        w=s.World(2,-1,3,4)
        self.assertEqual(s.mean_do(w,'x',2,0),10)
        self.assertEqual(s.mean_do(w,'m',0,2),6)
        self.assertEqual(s.mean_do(w,'joint',2,4),10)

    def test_counterfactual_unit_noise_invariance(self):
        w=s.World(2,-1,3,4)
        u,ex,em,ey=.8,.3,-.7,.2
        x=u+ex
        m=w.a*x+em
        y=w.b*x+w.c*m+w.d*u+ey
        xp=x+2
        mp=w.a*xp+em
        yp=w.b*xp+w.c*mp+w.d*u+ey
        self.assertAlmostEqual(yp-y,2*(w.b+w.c*w.a))

    def test_observational_nonidentifiability(self):
        def scm_a(u, intervention=None):
            x = u if intervention is None else intervention
            return x, x  # X -> Y
        def scm_b(u, intervention=None):
            x = u if intervention is None else intervention
            return x, u  # U -> Y only
        self.assertEqual([scm_a(u) for u in (-1, 1)],
                         [scm_b(u) for u in (-1, 1)])
        self.assertNotEqual([scm_a(u, intervention=1) for u in (-1, 1)],
                            [scm_b(u, intervention=1) for u in (-1, 1)])

    def test_budget_hard_stop(self):
        q=s.Sampler(s.World(1,1,1,1),1,2)
        q.query('obs'); q.query('x')
        with self.assertRaises(RuntimeError): q.query('joint')
        self.assertEqual(q.used,2)

    def test_reject_invalid_modes(self):
        with self.assertRaises(ValueError): s.sample(s.World(1,1,1,1),'invalid',random.Random(1))
        with self.assertRaises(ValueError): s.mean_do(s.World(0,0,0,0),'invalid',1,0)

    def test_ols_exact(self):
        rows=[(1,x,m) for x,m in [(-2,-2),(-2,2),(2,-2),(2,2)]]
        coeff=s.ls(rows,[3+2*x-4*m for _,x,m in rows])
        for val,goal in zip(coeff,(3,2,-4)):
            self.assertAlmostEqual(val,goal,places=6)

    def test_shift_only_one_edge(self):
        w=s.World(0,1,2,3); new=s.shift(w,17)
        self.assertEqual(sum(a!=b for a,b in zip((w.a,w.b,w.c),(new.a,new.b,new.c))),1)
        self.assertEqual(w.d,new.d)

    def test_oracle_zero_error(self):
        w=s.World(1.2,-.7,1.1,1.5)
        output=s.evaluate(w,s.Model(w.a,w.b,w.c))
        for key in ('mse','plan_regret','cf_delta_mse','unseen_do_m_mse'):
            self.assertAlmostEqual(output[key],0)
        self.assertEqual(output['edge_f1'],1)

    def test_equal_training_cost(self):
        w=s.make_world(50001)
        self.assertEqual(s.train(w,1,'obs',s.TRAIN)[1],s.TRAIN)
        self.assertEqual(s.train(w,1,'causal',s.TRAIN)[1],s.TRAIN)

    def test_replay_and_split_separation(self):
        self.assertEqual(s.run_world(60000,True),s.run_world(60000,True))
        r=s.experiment(2)
        self.assertLess(r['protocol']['seed_confounded'][1],r['protocol']['seed_unconfounded'][0])
        self.assertEqual(r,s.experiment(2))

    def test_finite_fit(self):
        for arm in ('obs','causal'):
            fit,_=s.train(s.make_world(222),12,arm,s.TRAIN)
            self.assertTrue(all(math.isfinite(v) for v in (fit.a,fit.b,fit.c,fit.intercept)))

if __name__=='__main__':
    unittest.main()
