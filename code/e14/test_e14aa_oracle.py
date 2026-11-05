"""Hand-derived arithmetic and topology cases for independent labels."""
import copy
import unittest
from e14.e14_shared_budget import BudgetContractError
from e14.e14aa_oracle import value,graph_label
from e14.e14u_primitive import graph_from_routes
from e14.e14v_topology import fork


class IndependentOracleTests(unittest.TestCase):
    def test_two_predicates_signed_and_boundary(self):
        spec={'terms':[{'kind':'periodic','p':3,'r':1,'a':2},
                       {'kind':'threshold','t':4,'a':-1}]}
        self.assertEqual(value(spec,(5,9)),15)
        self.assertEqual(value(spec,(5,8)),13)
        self.assertEqual(value(spec,(4,4)),8)

    def test_distinct_outside_grammar_perturbations(self):
        self.assertEqual(value({'outsider':{'kind':'needle','lo':5,'hi':9,'a':3}},(5,9)),17)
        self.assertEqual(value({'outsider':{'kind':'needle','lo':5,'hi':9,'a':3}},(4,9)),13)
        self.assertEqual(value({'outsider':{'kind':'squared_gap','a':2}},(5,9)),46)
        self.assertEqual(value({'outsider':{'kind':'lo_parity','a':-2}},(5,9)),12)

    def test_graph_labels_on_disjoint_and_shared_prefix_topology(self):
        pair=((1,1,1),(1,1,2));spec={'terms':[{'kind':'periodic','p':3,'r':1,'a':2}]}
        for graph in (graph_from_routes(pair,(1,5)),fork(pair,(1,5))):
            self.assertEqual(graph_label(graph,pair,spec),16)

    def test_no_matching_pair_is_none(self):
        self.assertIsNone(graph_label(graph_from_routes(((1,1,1),)),
                                     ((1,1,1),(2,2,2)),{}))

    def test_schema_and_boolean_integer_tampering_fails(self):
        cases=[({'terms':[{'kind':'periodic','p':0,'r':0,'a':1}]},(4,5)),
               ({'terms':[{'kind':'threshold','t':True,'a':1}]},(4,5)),
               ({'terms':[],'secret':'x'},(4,5)),({},(5,4)),({},(True,5)),
               ({'outsider':{'kind':'unknown'}},(4,5))]
        for spec,xy in cases:
            with self.subTest(spec=spec,xy=xy):
                with self.assertRaises(BudgetContractError):value(spec,xy)

    def test_graph_cycles_offroute_and_duplicate_edges_fail(self):
        pair=((1,1,1),(1,1,2));graph=graph_from_routes(pair,(1,5))
        for mutation in ('cycle','duplicate','offroute'):
            current=copy.deepcopy(graph)
            if mutation=='cycle':current['edges'][0][1]=0
            elif mutation=='duplicate':current['edges'].append(current['edges'][0])
            else:current={'nodes':4,'start':0,'goal':3,
                          'edges':[[0,3,0,4],[1,2,1,0]]}
            with self.subTest(mutation=mutation):
                with self.assertRaises(BudgetContractError):graph_label(current,pair,{})


if __name__=='__main__':unittest.main()
