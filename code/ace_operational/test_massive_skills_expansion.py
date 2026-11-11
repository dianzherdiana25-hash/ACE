"""Unit tests for Massive Skills Expansion Engine."""
import sys
from pathlib import Path

_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest
from ace_operational.massive_skills_expansion import MassiveSkillsExpander
from ace_operational.store import OperationalStore


class TestMassiveSkillsExpansion(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("/tmp/test_massive_expansion_workspace")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.store = OperationalStore(workspace=self.tmp_dir)
        self.expander = MassiveSkillsExpander(self.store)

    def test_verify_metacognitive_self_model(self):
        res = self.expander.verify_metacognitive_self_model()
        self.assertTrue(res["passed"])
        self.assertEqual(res["metrics"]["functional_self_model"], "ESTABLISHED_BOUNDED")
        self.assertEqual(res["metrics"]["phenomenal_consciousness"], "PHENOMENAL_CONSCIOUSNESS_UNKNOWN")

    def test_verify_graph_optimization_search(self):
        res = self.expander.verify_graph_optimization_search()
        self.assertTrue(res["passed"])
        self.assertEqual(len(res["order"]), 5)

    def test_verify_streaming_data_etl(self):
        res = self.expander.verify_streaming_data_etl()
        self.assertTrue(res["passed"])
        self.assertEqual(res["unique_count"], 3)

    def test_verify_ast_complexity_analyzer(self):
        res = self.expander.verify_ast_complexity_analyzer()
        self.assertTrue(res["passed"])
        self.assertGreaterEqual(res["complexity_score"], 4)

    def test_run_mass_expansion_end_to_end(self):
        res = self.expander.run_mass_expansion()
        self.assertEqual(res["total_skills_added"], 5)
        self.assertEqual(len(self.store.list_skills()), 5)
        frontier = {c["capability_id"]: c for c in self.store.list_frontier()}
        self.assertIn("cap_metacognitive_self_model", frontier)
        self.assertIn("cap_graph_optimization_search", frontier)
        self.assertIn("cap_streaming_data_etl", frontier)
        self.assertIn("cap_ast_complexity_analyzer", frontier)
        self.assertIn("cap_autonomous_research_agenda_planner", frontier)


if __name__ == "__main__":
    unittest.main()
