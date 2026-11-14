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

            self.assertEqual(res["epoch_a_skills_synthesized"], 4)
            self.assertEqual(res["epoch_a_forgetting"], 0)
            self.assertEqual(res["epoch_b_waves_solved"], 3)
            self.assertEqual(res["epoch_c_mutation_kill_rate"], 1.0)
            self.assertEqual(res["epoch_d_active_strategy"], "strat_mdl_focused_v2")
            self.assertEqual(res["epoch_f_receipts_verified"], [True, True])
            self.assertTrue(res["dag_chain_valid"])
            self.assertEqual(len(res["spore_sha256"]), 64)
            self.assertTrue((Path(d1) / "gen-1" / "generation_spore.json").exists())
            self.assertTrue((Path(d1) / "gen-1" / "evolution_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
