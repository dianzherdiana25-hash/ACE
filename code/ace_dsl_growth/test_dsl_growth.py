"""Unit and integration tests for W4 Capability Growth and W5 Mobile Reporting."""
import unittest

from ace_dsl_growth.graph_primitives import GraphAdjacencyPrimitive
from ace_dsl_growth.ratio4_primitives import Ratio4ModularPrimitive
from ace_dsl_growth.experiment_runner import run_abc_comparison_experiment
from ace_report.mobile_report import generate_indonesian_mobile_report


class TestDSLGrowthAndReporting(unittest.TestCase):
    def test_graph_adjacency_primitive(self):
        """GraphAdjacencyPrimitive correctly assesses graph connectivity on 4-vertex adjacency strings."""
        primitive = GraphAdjacencyPrimitive(target_nodes=4)

        # Fully connected: all edges present ('aaaaaa')
        self.assertTrue(primitive.predict("aaaaaa"))

        # Completely disconnected: no edges present ('bbbbbb')
        self.assertFalse(primitive.predict("bbbbbb"))

        # Spanning tree: edges (0,1), (1,2), (2,3) -> indices 0, 3, 5 present -> 'abbaba'
        # Index 0: 01, Index 1: 02, Index 2: 03, Index 3: 12, Index 4: 13, Index 5: 23
        self.assertTrue(primitive.predict("abbaba"))

    def test_ratio4_modular_primitive(self):
        """Ratio4ModularPrimitive accurately identifies ratio 4:1."""
        primitive = Ratio4ModularPrimitive()

        # 9 a's, 2 b's -> 9 > 8 -> True
        self.assertTrue(primitive.predict("aaaaaaaaabb"))

        # 8 a's, 2 b's -> 8 not > 8 -> False
        self.assertFalse(primitive.predict("aaaaaaaabb"))

    def test_abc_experiment_and_mobile_report(self):
        """A/B/C experiment executes across seeds and generates valid Indonesian mobile report."""
        exp_result = run_abc_comparison_experiment(
            seeds=[20261101, 20261102],
            tasks_per_family=5,
            replicates=2
        )
        self.assertEqual(exp_result["status"], "EXPERIMENT_COMPLETED")
        self.assertEqual(exp_result["hypotheses_evaluation"]["H_graph"], "CONFIRMED")
        self.assertEqual(exp_result["hypotheses_evaluation"]["H_ratio4"], "CONFIRMED")

        # Test mobile report generation
        report_md = generate_indonesian_mobile_report(exp_result)
        self.assertIn("Laporan Hasil Riset ACE", report_md)
        self.assertIn("Keluarga Graf", report_md)
        self.assertIn("Batas Interpretasi", report_md)
        self.assertIn("CONFIRMED", report_md)


if __name__ == "__main__":
    unittest.main()
