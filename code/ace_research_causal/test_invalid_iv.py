"""R5 invalid-instrument falsification and cost-policy invariants."""
from __future__ import annotations
from dataclasses import replace
import json
import math
import random
import unittest
from . import invalid_iv as s


class InvalidIVTests(unittest.TestCase):
    def test_worlds_respect_mechanism_controls(self):
        for group,start in s.GROUPS.items():
            for i in range(10):
                w=s.world(start+i,group)
                self.assertTrue(0<w.compliance<1)
                self.assertEqual(w.direct_z==0,group not in ('direct_exclusion','both_invalid'))
                self.assertEqual(w.heterogeneity==0,group not in ('selected_compliance','both_invalid'))

    def test_exclusion_violation_direct_effect_in_y(self):
        w=s.World(0.,0.,0.,.8,0.,.75)
        rows=s.sample(w,13,'encourage')
        # Treatment has no effect; all randomized Z->Y association is direct.
        reduced=s.ols([(1.,z) for z,x,y in rows],[y for z,x,y in rows])[1]
        self.assertAlmostEqual(reduced,.8,delta=.15)

    def test_countermodel_observational_indistinguishability(self):
        # Perfect compliance X=Z: worlds (tau, direct_z) and (tau+delta, direct_z-delta)
        # have identical (Z,X,Y) even with infinite data.
        rng=random.Random(7)
        for _ in range(100):
            z=rng.choice((-1.,1.)); noise=rng.gauss(0,1.)
            a=.4*z+(-.8)*z+noise
            b=(-.4)*z+0*z+noise
            self.assertEqual(a,b)

    def test_compliance_selector_can_depend_on_hidden_u(self):
        w=s.world(630000,'selected_compliance')
        self.assertNotAlmostEqual(s.probability(w,-2),s.probability(w,2))
        w2=replace(w,selection_slope=0)
        self.assertAlmostEqual(s.probability(w2,-2),s.probability(w2,2))

    def test_exogeneity_of_randomized_assignment_in_generator(self):
        w=s.world(620000,'direct_exclusion')
        rows=s.sample(w,4,'encourage')
        self.assertEqual(sum(z for z,x,y in rows),0)
        self.assertEqual(sum(z*z for z,x,y in rows),s.ROWS)

    def test_no_hidden_u_sent_to_learner(self):
        w=s.world(630000,'selected_compliance')
        rows=s.sample(w,3,'encourage')
        self.assertEqual(len(rows),160)
        self.assertTrue(all(len(row)==3 for row in rows))

    def test_ground_truth_do_ate_with_heterogeneity_independent_sim(self):
        w=s.world(630001,'selected_compliance')
        rng=random.Random(99)
        diffs=[]
        for _ in range(12000):
            u=rng.gauss(0,1)
            diffs.append((w.tau+w.heterogeneity*u)*2)
        self.assertAlmostEqual(sum(diffs)/len(diffs),2*w.tau,delta=.07)

    def test_linear_ols_recovery(self):
        xs=[-2.,-1.,0.,1.,2.]
        rows=[(0.,x,3+2*x) for x in xs]
        v,_=s.regress(rows,'obs')
        self.assertAlmostEqual(v,2,places=6)

    def test_identification_failure_but_no_false_claim_of_instrument_test(self):
        # Data from a perfectly compliant instrument cannot separate direct effect and tau.
        world=s.World(tau=.25,confounding=0.,heterogeneity=0.,direct_z=-.8,
                      selection_slope=0.,compliance=.999999)
        rows=s.sample(world,9,'encourage')
        fitted,first=s.regress(rows,'iv')
        self.assertGreater(first,.9)
        self.assertLess(fitted,0)  # true tau positive, inferred negative.

    def test_cost_sensitive_optimum(self):
        w=s.World(.6,1.,0.,0.,0.,.7)
        for cost in s.COSTS:
            values=[s.score(w,w.tau,action,cost)['regret'] for action in (-1,0,1)]
            self.assertGreaterEqual(min(values),-1e-9)
            self.assertAlmostEqual(min(values),0)

    def test_cost_gated_abstention_and_missing_instrument(self):
        self.assertEqual(s.act(.7,.5,'boot_cost',(1.,)*s.BOOT,first=.01),0)
        self.assertEqual(s.act(.7,.5,'boot_cost',(1.,)*s.BOOT,first=.5),1)
        self.assertEqual(s.act(-.7,.5,'boot_cost',(-1.,)*s.BOOT,first=.5),-1)
        self.assertEqual(s.act(.7,1.,'boot_cost',(1.,)*s.BOOT,first=.5),0)
        self.assertEqual(s.act(math.nan,0,'always'),0)

    def test_abstention_not_equivalent_to_success(self):
        w=s.World(.8,1.,0.,0.,0.,.7)
        self.assertGreater(s.score(w,0,0,0.)['regret'],0)
        self.assertEqual(s.score(w,0,0,1.)['regret'],0)

    def test_matched_budget_and_separate_intervention_kind(self):
        w=s.world(610000,'valid')
        for mode in ('encourage','observe','do'):
            self.assertEqual(len(s.sample(w,11,mode)),s.ROWS)
        with self.assertRaises(ValueError):s.sample(w,11,'do',159)
        with self.assertRaises(ValueError):s.one(w,random.Random(11),'invalid',1.)

    def test_replay_is_deterministic(self):
        j1=json.dumps(s.experiment(2),sort_keys=True,allow_nan=False)
        j2=json.dumps(s.experiment(2),sort_keys=True,allow_nan=False)
        self.assertEqual(j1,j2)

    def test_gated_error_rate_nullable_when_no_acceptance(self):
        w=s.world(610000,'valid')
        cases=[s.run_world(610000+i,'valid') for i in range(2)]
        for record in cases:
            for cost in s.COSTS:
                record[str(cost)]['iv_boot_cost']=s.score(w,0.,0,cost)
        summary=s.summarize(cases)
        for cost in s.COSTS:
            gated=summary[str(cost)]['policies']['iv_boot_cost']
            self.assertEqual(gated['accepted_count'],0)
            self.assertIsNone(gated['conditional_wrong_rate'])

    def test_unexpected_parameter_rejected(self):
        with self.assertRaises(ValueError):s.world(1,'bad')
        with self.assertRaises(ValueError):s.regress([],'bad')
        with self.assertRaises(ValueError):s.act(1.,.33,'always')
        with self.assertRaises(ValueError):s.act(1.,0.,'invalid')
        with self.assertRaises(ValueError):s.score(s.world(610000,'valid'),1.,2,0.)
        with self.assertRaises(ValueError):s.experiment(1)
        with self.assertRaises(ValueError):s.experiment(251)


if __name__=='__main__':
    unittest.main()
