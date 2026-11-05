"""Unit and adversarial tests for the E1.4u two-distinct-route constructor."""
import copy
import unittest
from itertools import combinations

from .e14_integrated_graph import BudgetContractError, graph_routes
from .e14u_primitive import (PAIR_SPACE, PAIR_WORDS, BASE_LENGTHS, SINGLE_SPACE,
                              program, predict, oracle, graph_from_routes,
                              fit, diagnose, query_pool, select_query,
                              guarded_predict)
from .e14u_dev import make_world, triple_oracle


class E14UPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.a=(1,2,1)
        self.b=(2,1,2)
        self.c=(2,2,2)
        self.pair=program('branch-pair',[self.a,self.b])
        self.double=graph_from_routes((self.a,self.b),(0,3))

    def test_new_constructor_witnesses_two_distinct_routes(self):
        self.assertEqual(oracle(self.double,self.pair),7)
        self.assertIsNone(oracle(graph_from_routes([self.a]),self.pair))
        self.assertIsNone(oracle(graph_from_routes([self.b]),self.pair))

    def test_single_path_control_can_detect_only_one_route(self):
        base=program('single-path',[self.a])
        self.assertEqual(oracle(graph_from_routes([self.a]),base),4)
        self.assertEqual(oracle(self.double,base),4)
        self.assertIsNone(oracle(graph_from_routes([self.b]),base))

    def test_two_route_conjunction_is_not_single_contiguous_motif(self):
        graphs=[self.double,graph_from_routes([self.a]),graph_from_routes([self.b])]
        demos=[{'input':g,'output':oracle(g,self.pair)} for g in graphs]
        self.assertEqual(fit(demos)['candidates'],[])
        self.assertIn(self.pair,fit(demos,extended=True)['candidates'])
        self.assertTrue(diagnose(demos)['trigger'])

    def test_ordering_of_motifs_canonical(self):
        self.assertEqual(program('branch-pair',[self.b,self.a]),self.pair)

    def test_identical_words_unsupported_explicitly(self):
        self.assertRaises(BudgetContractError,program,'branch-pair',[self.a,self.a])

    def test_invalid_programs_rejected(self):
        cases=[('other',[self.a]),('single-path',[]),('single-path',[self.a,self.b]),
               ('branch-pair',[self.a]),('branch-pair',[(1,True,1),self.b]),
               ('branch-pair',[(1,2),self.b]),('single-path',[(3,2,1)]),
               ('branch-pair',[[1,2,1],[1,float('nan'),2]])]
        for kind,words in cases:
            with self.subTest(kind=kind,words=words):
                self.assertRaises(BudgetContractError,program,kind,words)

    def test_query_pool_all_distinct_and_typed(self):
        graphs=query_pool()
        self.assertEqual(len(graphs),70)
        self.assertEqual(len({str(g) for g in graphs}),70)
        for g in graphs:
            routes,cost=graph_routes(g)
            self.assertEqual(len(routes),4)
            self.assertEqual(cost['edges'],16)
            self.assertEqual(cost['nodes'],14)

    def test_graph_builder_rejects_over_cap(self):
        self.assertRaises(BudgetContractError,graph_from_routes,[self.a]*5)
        self.assertRaises(BudgetContractError,graph_from_routes,[])
        self.assertRaises(BudgetContractError,graph_from_routes,[self.a,(1,2,1,2)])
        self.assertRaises(BudgetContractError,graph_from_routes,[self.a],tolls=[True])
        self.assertRaises(BudgetContractError,graph_from_routes,[self.a],tolls=[15])

    def test_pair_label_uses_max_cost_not_sum(self):
        g=graph_from_routes([self.a,self.b],[2,5])
        self.assertEqual(oracle(g,self.pair),9)

    def test_two_distinct_paths_with_identical_event_traces(self):
        g=graph_from_routes([self.a,self.a,self.b],[0,1,2])
        self.assertEqual(len(graph_routes(g)[0]),3)
        self.assertEqual(oracle(g,self.pair),6)

    def test_base_and_extended_fits_accounted(self):
        demos=[{'input':self.double,'output':7}]
        self.assertEqual(fit(demos)['candidate_fits'],56)
        self.assertEqual(fit(demos,extended=True)['candidate_fits'],28)

    def test_false_pair_detection_not_accepted(self):
        g=graph_from_routes([self.a,self.c],[0,0])
        row=guarded_predict([self.pair],g)
        self.assertTrue(row['covered'])
        self.assertIsNone(row['prediction'])

    def test_ambiguous_version_space_abstains_on_disagreement(self):
        g=graph_from_routes([self.a,self.b],[0,3])
        others=program('branch-pair',[self.a,self.c])
        row=guarded_predict([self.pair,others],g)
        self.assertFalse(row['covered'])

    def test_empty_version_space_abstains(self):
        self.assertEqual(guarded_predict([],self.double),
                         {'covered':False,'prediction':None})

    def test_bounded_demo_and_boolean_evidence_rejected(self):
        demo={'input':self.double,'output':7}
        cases=[[],[demo]*9,[{'input':self.double,'output':True}],
               [{'input':self.double,'output':-1}],
               [{'input':self.double,'output':7,'truth':[1,2,1]}]]
        for row in cases:
            with self.subTest(row=row):
                self.assertRaises(BudgetContractError,fit,row)

    def test_positive_and_negative_world_generation_no_truth_leak(self):
        w=make_world('pair',6)
        self.assertEqual(len(w['demonstrations']),3)
        self.assertIsNotNone(w['demonstrations'][0]['output'])
        self.assertTrue(all(x['output'] is None for x in w['demonstrations'][1:]))
        self.assertTrue(diagnose(w['demonstrations'])['trigger'])
        self.assertIn(w['truth'],diagnose(w['demonstrations'])['extended']['candidates'])

    def test_baseline_semantics_remain_representable(self):
        for i in range(len(PAIR_WORDS)):
            w=make_world('single',i)
            self.assertFalse(diagnose(w['demonstrations'])['trigger'])
            self.assertIn(w['truth'],fit(w['demonstrations'])['candidates'])

    def test_out_of_grammar_three_path_case_unresolved(self):
        for i in range(6):
            w=make_world('triple',i)
            self.assertTrue(diagnose(w['demonstrations'])['trigger'])
            self.assertEqual(diagnose(w['demonstrations'])['extended']['candidates'],[])

    def test_select_query_does_not_rebuy_sorted_existing_graph(self):
        candidates=[program('branch-pair',p) for p in PAIR_SPACE[:12]]
        g=select_query(candidates,[],mode='fixed')
        self.assertIsNotNone(g)
        shuffled=copy.deepcopy(g);shuffled['edges'].reverse()
        next_g=select_query(candidates,[shuffled],mode='fixed')
        self.assertNotEqual(next_g,g)

    def test_selector_refuses_unrecognized_strategy(self):
        self.assertRaises(BudgetContractError,select_query,[self.pair],[],mode='unknown')

    def test_every_pair_program_is_distinct(self):
        p=[program('branch-pair',words) for words in PAIR_SPACE]
        self.assertEqual(len(p),28)
        self.assertEqual(len(set(p)),28)

    def test_oracle_route_order_does_not_change_result(self):
        g=copy.deepcopy(self.double)
        g['edges'].reverse()
        self.assertEqual(oracle(g,self.pair),oracle(self.double,self.pair))

    def test_triple_requires_three_distinct_routes(self):
        triple=(self.a,self.b,self.c)
        self.assertIsNone(triple_oracle(self.double,triple))
        g=graph_from_routes(list(triple),[0,2,4])
        self.assertEqual(triple_oracle(g,triple),8)

    def test_distinct_routes_are_costed_without_duplicate_purchase(self):
        routes,cost=graph_routes(self.double)
        self.assertEqual(cost,{'nodes':8,'edges':8,'events':6})
        self.assertEqual(len(routes),2)


if __name__=='__main__':unittest.main()
