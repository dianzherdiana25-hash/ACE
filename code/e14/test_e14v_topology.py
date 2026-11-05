import unittest
from itertools import islice
from .e14_integrated_graph import graph_routes
from .e14_shared_budget import BudgetContractError
from .e14p_graph import paths,minimum
from .e14u_primitive import PAIR_SPACE,PAIR_WORDS
from .e14v_operator import ALL,graph_score
from .e14v_topology import expected_equivalent_graphs,fork,structurally_new_probes

class StructuralShift(unittest.TestCase):
    def test_shared_fork_typed_limits(self):
        g=fork(PAIR_WORDS[:4],(0,1,2,3))
        routes,cost=graph_routes(g)
        self.assertEqual((len(routes),cost['nodes'],cost['edges'],cost['events']),(4,11,13,12))
        self.assertEqual({e for e,c in routes},set(PAIR_WORDS[:4]))

    def test_shared_prefix_makes_distinct_graph_topology(self):
        left,right=expected_equivalent_graphs(PAIR_WORDS[:4],(0,2,4,6))
        self.assertNotEqual(left,right)
        self.assertEqual(graph_routes(left)[0],graph_routes(right)[0])

    def test_thirty_structures_have_consistent_algebra(self):
        for idx,g in enumerate(structurally_new_probes(81818,count=30)):
            with self.subTest(graph=idx):
                raw=graph_routes(g)[0]
                self.assertEqual(sorted(raw),sorted(paths(g)))
                for candidate in ALL:
                    if candidate[0]=='single':
                        self.assertEqual(graph_score(g,candidate),minimum(paths(g),candidate[1][0]))
                    else:
                        self.assertGreaterEqual(graph_score(g,candidate) or 0,0)

    def test_deterministic_non_target_aware_probes(self):
        self.assertEqual(structurally_new_probes(7007,8),structurally_new_probes(7007,8))
        self.assertNotEqual(structurally_new_probes(7007,8),structurally_new_probes(7008,8))

    def test_invalid_fork_input_rejected(self):
        for words,tolls in ((PAIR_WORDS[:1],[0]),(PAIR_WORDS[:2],[0,True]),
                            (PAIR_WORDS[:2],[0,-1]),([PAIR_WORDS[0],[1,2,True]],[0,1])):
            with self.subTest(words=words,tolls=tolls):
                self.assertRaises(BudgetContractError,fork,words,tolls)

    def test_pair_semantics_topology_invariance(self):
        a,b=PAIR_SPACE[5]
        for tolls in ((0,3),(2,9),(7,1)):
            left,right=expected_equivalent_graphs((a,b),tolls)
            for w in ((0,1),(1,0),(1,1),(2,3),(3,2)):
                c=('pair-affine',(a,b),w)
                self.assertEqual(graph_score(left,c),graph_score(right,c))

if __name__=='__main__':unittest.main()
