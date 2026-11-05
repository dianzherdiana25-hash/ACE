"""Prescore E1.4v engineering tests; no claim of independent scientific result."""
import tempfile
import unittest
from pathlib import Path

from .e14_integrated_graph import DurableGraphBudget, audit_journal, graph_routes, purchase
from .e14_shared_budget import BudgetContractError
from .e14u_primitive import PAIR_SPACE, graph_from_routes
from .e14v_operator import ALL, LEGACY, graph_score, infer_weights, pairs_of, pool, predict, proof, select, survivor_ids
from .e14v_study import COEFFICIENTS, MODES, SEED, challenge, evaluate, source_evidence, study, unknown_score, world


class ParameterInference(unittest.TestCase):
    def setUp(self):
        self.pair=PAIR_SPACE[0]
        self.a,self.b=self.pair

    def test_candidate_space_not_three_explicit_names(self):
        self.assertEqual((len(ALL),len(LEGACY)),(476,140))
        self.assertIn(('pair-affine',self.pair,(2,3)),ALL)

    def test_single_graph_cannot_prove_two_coefficients(self):
        g=graph_from_routes(self.pair,(1,3))
        target=('pair-affine',self.pair,(2,1))
        obs=[(g,graph_score(g,target))]
        self.assertIsNone(infer_weights(self.pair,obs))
        self.assertEqual(proof(target,obs)['status'],'underidentified')

    def test_algebraic_induction_without_named_operator(self):
        target=('pair-affine',self.pair,(2,3))
        graphs=(graph_from_routes(self.pair,(0,6)),graph_from_routes(self.pair,(7,1)))
        obs=[(g,graph_score(g,target)) for g in graphs]
        self.assertEqual(infer_weights(self.pair,obs),(2,3))
        self.assertEqual(proof(target,obs)['status'],'rank-verified')

    def test_conflicting_labels_never_prove_operator(self):
        target=('pair-affine',self.pair,(1,2))
        graphs=(graph_from_routes(self.pair,(0,6)),graph_from_routes(self.pair,(7,1)))
        obs=[(g,graph_score(g,target)) for g in graphs]
        obs.append((graphs[0],999))
        self.assertIsNone(infer_weights(self.pair,obs))

    def test_negative_label_distinct_from_zero(self):
        g=graph_from_routes([self.a])
        self.assertIsNone(graph_score(g,('pair-affine',self.pair,(2,1))))
        self.assertNotEqual(graph_score(g,('pair-affine',self.pair,(2,1))),0)

    def test_graph_limit_and_weight_semantics(self):
        g=graph_from_routes(self.pair,(0,3))
        routes=graph_routes(g)[0]
        self.assertEqual(len(pairs_of(routes,self.pair)),1)
        lo,hi=pairs_of(routes,self.pair)[0]
        self.assertEqual(graph_score(g,('pair-affine',self.pair,(2,3))),2*lo+3*hi)

    def test_bad_representation_fails_closed(self):
        g=graph_from_routes(self.pair)
        for c in [('pair-affine',self.pair,(-1,1)),('pair-affine',self.pair,(0,0)),
                  ('single',(self.a,),[1,2]),('bad',self.pair,(1,2))]:
            with self.subTest(c=c):
                self.assertRaises(BudgetContractError,graph_score,g,c)

    def test_selector_rejects_already_purchased_query(self):
        ids=tuple(range(len(ALL)))
        g=select(ids,[],mode='active',seed=SEED)
        other=select(ids,[g],mode='active',seed=SEED)
        self.assertNotEqual(g,other)
        self.assertIn(g,pool()[0])

    def test_source_acquisition_uses_same_first_graph_across_truths(self):
        a=world(0,(2,1));b=world(1,(3,2))
        with tempfile.TemporaryDirectory() as t:
            x,_=source_evidence(a,Path(t)/'s.sqlite')
            y,_=source_evidence(b,Path(t)/'s.sqlite')
        self.assertEqual(x[0][0],y[0][0])


class BoundedEvaluation(unittest.TestCase):
    def test_source_budget_and_independent_replay(self):
        w=world(0,(2,1))
        with tempfile.TemporaryDirectory() as t:
            rows,cost=source_evidence(w,Path(t)/'j.sqlite')
            journal=DurableGraphBudget(Path(t)/'j.sqlite',w['id']+':source')
            self.assertEqual(cost['source_purchased'],len(rows))
            self.assertLessEqual(len(rows),4)
            self.assertEqual(audit_journal(journal.snapshot(),w['oracle'])['auditor_oracle_calls'],len(rows))

    def test_affine_unknown_coefficient_can_be_learned(self):
        w=world(0,(2,1))
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'j.sqlite';rows,_=source_evidence(w,db)
            result=evaluate(w,rows,db,'affine-verified')
            self.assertEqual(result['exact'],1)
            self.assertEqual(result['wrong_accepted'],0)

    def test_challenge_buys_a_distinct_label(self):
        w=world(0,(2,1))
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'j.sqlite';rows,_=source_evidence(w,db)
            result=evaluate(w,rows,db,'affine-challenge')
        self.assertEqual(result['challenge_pass'],True)
        self.assertEqual(result['target_replayed'],result['target_purchased'])
        self.assertLessEqual(result['target_purchased'],4)

    def test_outside_affine_family_is_not_misreported_as_supported(self):
        w=world(0,'product')
        self.assertEqual(w['truth'][0],'unrepresented')
        g=graph_from_routes(w['pair'],(2,5))
        self.assertEqual(unknown_score(g,w['pair'],'product'),(4+2)*(4+5))

    def test_all_source_and_target_interventions_are_separately_counted(self):
        r=study(indices=(0,),operators=((2,1),'product'))
        self.assertEqual((r['worlds'],r['arms']),(2,8))
        self.assertEqual(len(MODES),4)
        for a in r['rows']:
            self.assertLessEqual(a['target_purchased'],4)
            self.assertEqual(a['target_replayed'],a['target_purchased'])
        for s in r['source']:
            self.assertLessEqual(s['source_purchased'],4)
            self.assertEqual(s['source_purchased'],s['source_replayed'])

    def test_identical_world_reproduces_deterministic_measurements(self):
        a=study(indices=(0,),operators=((2,1),))
        b=study(indices=(0,),operators=((2,1),))
        self.assertEqual(a,b)

    def test_new_probes_disjoint_from_offer_pool(self):
        w=world(0,(2,1))
        known=set(pool()[2]);keys=[tuple(sorted(map(tuple,g['edges']))) for g in w['probes']]
        self.assertEqual(len(set(keys)),6)
        self.assertFalse(set(keys)&known)

if __name__=='__main__':unittest.main()

class ProofRecovery(unittest.TestCase):
    def test_target_can_buy_rank_witness_after_underidentified_source(self):
        w=world(0,(2,1))
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'proof.sqlite'
            source,_=source_evidence(w,db,limit=1)
            self.assertEqual(len(source),1)
            result=evaluate(w,source,db,'affine-verified')
            self.assertEqual(result['accepted'],1)
            self.assertEqual(result['exact'],1)
            self.assertGreaterEqual(result['target_purchased'],1)
