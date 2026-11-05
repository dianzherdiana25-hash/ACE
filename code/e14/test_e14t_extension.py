"""Bounded grammar expansion controls, including out-of-base short motif."""
import unittest

from .e14_integrated_graph import graph_oracle
from .e14_shared_budget import BudgetContractError
from .e14t_extension import diagnosis, predict, selective_prediction, version_space


def chain(word):
    color = 0
    edges = [[0,1,color,1]]
    for i,event in enumerate(word,1):
        color ^= (event == 2)
        edges.append([i,i+1,color,1])
    return {"nodes":len(word)+2,"start":0,"goal":len(word)+1,"edges":edges}


class GrammarExpansion(unittest.TestCase):
    def test_out_of_base_motif_has_extended_solution(self):
        truth = (1,2,1,2,2)
        graph = chain(truth)
        evidence = [{"input":graph,"output":graph_oracle(graph,truth)}]
        row = diagnosis(evidence)
        self.assertTrue(row["trigger"])
        self.assertEqual(row["status"],"extended_consistent")
        self.assertIn(truth,row["extended"]["motifs"])
        self.assertEqual(row["base"]["candidate_fits"],896)
        self.assertEqual(row["extended"]["candidate_fits"],992)

    def test_in_base_word_does_not_trigger(self):
        truth = (1,2,1,1,2,2,1)
        g = chain(truth)
        row = diagnosis([{"input":g,"output":graph_oracle(g,truth)}])
        self.assertFalse(row["trigger"])
        self.assertIn(truth,row["base"]["motifs"])
        self.assertIsNone(row["extended"])

    def test_contradictory_labels_remain_unresolved(self):
        g = chain((1,2,1,1,2))
        row = diagnosis([{"input":g,"output":6},{"input":g,"output":7}])
        self.assertEqual(row["status"],"unresolved")
        self.assertEqual(row["extended"]["motifs"],[])

    def test_negative_label_is_not_zero(self):
        g = chain((1,2,1,2,2))
        self.assertIsNone(graph_oracle(g,(2,2,2,2,2)))
        self.assertNotEqual(graph_oracle(g,(2,2,2,2,2)),0)

    def test_selective_abstention_on_ambiguous_motifs(self):
        g = chain((1,2,1,2,2))
        r = selective_prediction([(1,2,1,2,2),(2,2,2,2,2)],g)
        self.assertFalse(r["covered"])
        self.assertIsNone(r["prediction"])

    def test_selective_prediction_when_consensus(self):
        g = chain((1,2,1,2,2))
        r = selective_prediction([(1,2,1,2,2),(1,2,1,2,2)],g)
        self.assertTrue(r["covered"])
        self.assertEqual(r["prediction"],6)

    def test_rejects_bad_graph_and_boolean_oracle_label(self):
        g = chain((1,2,1,2,2))
        for demos in ([],[{"input":g,"output":True}],
                      [{"input":g,"output":None,"target":[1,2]}],
                      [{"input":{**g,"nodes":99},"output":None}]):
            with self.subTest(demos=demos):
                self.assertRaises(BudgetContractError,version_space,demos,extend=True)

    def test_extension_cost_explicitly_exceeds_base(self):
        g = chain((1,2,1,2,2))
        demos = [{"input":g,"output":None}]
        base = version_space(demos)
        extended = version_space(demos,extend=True)
        self.assertEqual(extended["candidate_fits"]-base["candidate_fits"],96)

if __name__ == "__main__":
    unittest.main()
