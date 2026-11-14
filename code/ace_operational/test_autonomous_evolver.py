"""Tests for the unified AutonomousEvolver (Epochs A-F closed loop)."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.autonomous_evolver import AutonomousEvolver


class AutonomousEvolverTests(unittest.TestCase):
    def test_full_generation_unites_all_six_epochs_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            evolver = AutonomousEvolver(d1)
            res = evolver.run_evolution_generation("gen-1")

            self.assertEqual(res["epoch_a_skills_synthesized"], 5)
            self.assertEqual(res["epoch_a_forgetting"], 0)
            self.assertEqual(res["epoch_b_waves_solved"], 3)
            self.assertEqual(res["epoch_c_mutation_kill_rate"], 1.0)
            self.assertEqual(res["epoch_d_active_strategy"], "strat_mdl_focused_v2")
            self.assertEqual(res["epoch_f_receipts_verified"], [True, True])
            self.assertTrue(res["dag_chain_valid"])
            self.assertEqual(len(res["spore_sha256"]), 64)
            self.assertTrue((Path(d1) / "gen-1" / "generation_spore.json").exists())
            self.assertTrue((Path(d1) / "gen-1" / "evolution_summary.json").exists())
            self.assertTrue((Path(d1) / "gen-1" / "synthesized_skills" / f"{res['novel_skill_id']}.py").exists())

    def test_multi_generation_continuity_exam(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            evolver = AutonomousEvolver(d1)
            multi = evolver.run_multi_generation_loop(generations=2)
            self.assertEqual(multi["generations_completed"], 2)
            self.assertTrue(multi["all_continuity_exams_passed"])
            self.assertEqual(multi["total_forgetting_count"], 0)
            g1, g2 = multi["generations"]
            self.assertGreater(g2["total_certified_skills"], g1["total_certified_skills"])
            self.assertGreater(g2["total_antibodies"], g1["total_antibodies"])
            self.assertNotEqual(g1["novel_skill_birth_sha256"], g2["novel_skill_birth_sha256"])
            self.assertNotEqual(g1["novel_skill_source"], g2["novel_skill_source"])


if __name__ == "__main__":
    unittest.main()
