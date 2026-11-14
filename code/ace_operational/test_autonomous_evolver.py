"""Tests for the zero-theater AutonomousEvolver closed loop."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.autonomous_evolver import AutonomousEvolver
from ace_operational.evolution_mission_loop import RealRepoAuditor


class AutonomousEvolverTests(unittest.TestCase):
    def test_full_generation_unites_all_real_subsystems_and_passive_work_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_autoevolve_") as d1:
            evolver = AutonomousEvolver(d1)
            res = evolver.run_evolution_generation("gen-1", include_compositional_oaie=True)

            self.assertEqual(res["epoch_a_skills_synthesized"], 5)
            self.assertEqual(res["epoch_a_forgetting"], 0)
            self.assertEqual(res["epoch_b_waves_solved"], 3)
            self.assertEqual(res["epoch_c_mutation_kill_rate"], 1.0)
            self.assertEqual(res["epoch_d_active_strategy"], "strat_typed_target_arity_v2")
            self.assertEqual(res["compositional_oaie_verdict"], "COMPOSITIONAL_OAIE_VERIFIED")
            self.assertEqual(res["passive_mission_status"], "MISSION_EMITTED")
            self.assertEqual(res["forgetting_count"], 0)
            self.assertGreater(res["spore_behavioral_checks_passed"], 0)
            self.assertTrue(res["dag_chain_valid"])
            self.assertEqual(len(res["spore_sha256"]), 64)
            self.assertTrue((Path(d1) / "gen-1" / "generation_spore.json").exists())
            self.assertTrue((Path(d1) / "gen-1" / "evolution_summary.json").exists())
            self.assertTrue((Path(d1) / "gen-1" / "synthesized_skills" / f"{res['novel_skill_id']}.py").exists())
            self.assertTrue((Path(d1) / "passive_evolution" / "EVOLUTION_WORK_ORDER.json").exists())
            self.assertTrue((Path(d1) / "passive_evolution" / "EVOLUTION_WORK_ORDER.md").exists())

            # AutonomousEvolver itself must have zero unguarded_verified_true findings
            repo_root = Path(__file__).resolve().parents[2]
            auditor = RealRepoAuditor(repo_root)
            self_audit = auditor._audit_single_python_file(Path(__file__).resolve().parent / "autonomous_evolver.py")
            self.assertFalse(any(f.kind == "unguarded_verified_true" for f in self_audit))

    def test_multi_generation_continuity_exam_and_causal_lineage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ace_autoevolve_multi_") as d1:
            evolver = AutonomousEvolver(d1)
            multi = evolver.run_multi_generation_loop(generations=2, include_compositional_oaie=False)
            self.assertEqual(multi["generations_completed"], 2)
            self.assertTrue(multi["all_continuity_exams_passed"])
            self.assertEqual(multi["total_forgetting_count"], 0)
            g1, g2 = multi["generations"]
            self.assertGreater(g2["total_certified_skills"], g1["total_certified_skills"])
            self.assertGreater(g2["total_antibodies"], g1["total_antibodies"])
            self.assertGreater(g2["causal_lineage_edges"], g1["causal_lineage_edges"])
            self.assertIn("proof_autoevolve_gen-1", g2["parent_ids"])
            self.assertNotEqual(g1["novel_skill_birth_sha256"], g2["novel_skill_birth_sha256"])
            self.assertNotEqual(g1["novel_skill_source"], g2["novel_skill_source"])


if __name__ == "__main__":
    unittest.main()
