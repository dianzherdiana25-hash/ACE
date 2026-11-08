"""Unit tests for Continuous Researcher Agent Pipeline."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_autonomy.research_pipeline import ContinuousResearcherPipeline, DiscoveryProposal


class TestResearchPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.pipeline = ContinuousResearcherPipeline(self.workspace)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_continuous_scouting_loop(self):
        # 1. First capability scouted by researcher agent
        p1 = self.pipeline.scout_next_capability("agent_scout_01")
        self.assertEqual(p1.status, "PROPOSED")
        self.assertIn("CEGIS", p1.capability_name)

        # 2. Agent immediately scouts again without halting
        p2 = self.pipeline.scout_next_capability("agent_scout_01")
        self.assertEqual(p2.status, "PROPOSED")
        self.assertIn("Monte Carlo Tree Search", p2.capability_name)
        self.assertNotEqual(p1.proposal_id, p2.proposal_id)

        pending = self.pipeline.pending_implementations()
        self.assertEqual(len(pending), 2)

    def test_implementation_and_verification_lifecycle(self):
        p = self.pipeline.scout_next_capability("agent_scout_01")
        pid = p.proposal_id

        # Antigravity marks implemented with commit SHA
        p_impl = self.pipeline.mark_implemented(pid, "commit_sha_123456")
        self.assertEqual(p_impl.status, "IMPLEMENTED")
        self.assertEqual(p_impl.implementation_commit, "commit_sha_123456")

        # Antigravity marks verified with evaluation receipt
        p_ver = self.pipeline.mark_verified(pid, {"tests_passed": 12, "accuracy": 1.0})
        self.assertEqual(p_ver.status, "VERIFIED")
        self.assertEqual(p_ver.evaluation_receipt["accuracy"], 1.0)

        # Persistence across pipeline instances
        new_pipeline = ContinuousResearcherPipeline(self.workspace)
        self.assertEqual(len(new_pipeline.proposals), 1)
        self.assertEqual(new_pipeline.proposals[pid].status, "VERIFIED")

    def test_continuous_discovery_and_immediate_execution(self):
        """Simulates researcher agent discovering multiple capabilities sequentially,
        with immediate coordinator implementation and uninterrupted resumed searching.
        """
        # Step 1: Researcher scouts CEGIS
        cegis_prop = self.pipeline.scout_next_capability("scout_agent_alpha")
        self.assertEqual(cegis_prop.capability_name, "Counterexample-Guided Inductive Synthesis (CEGIS)")

        # Step 2: Coordinator immediately implements and verifies CEGIS
        from ace_synthesis.cegis import CEGISSynthesizer
        synth = CEGISSynthesizer(max_iterations=5)
        spec = [("ab", True), ("ba", False)]
        res = synth.synthesize(spec, "cegis_test")
        self.pipeline.mark_implemented(cegis_prop.proposal_id, "commit_cegis_v1")
        self.pipeline.mark_verified(cegis_prop.proposal_id, {"status": res.status})

        # Step 3: Researcher immediately searches again without pausing
        mcts_prop = self.pipeline.scout_next_capability("scout_agent_alpha")
        self.assertEqual(mcts_prop.capability_name, "Monte Carlo Tree Search (MCTS) Program Tree Exploration")

        # Step 4: Coordinator immediately implements and verifies MCTS
        from ace_mcts.program_mcts import MCTSProgramSearch
        mcts = MCTSProgramSearch(max_simulations=10)
        best = mcts.search(spec)
        self.pipeline.mark_implemented(mcts_prop.proposal_id, "commit_mcts_v1")
        self.pipeline.mark_verified(mcts_prop.proposal_id, {"accuracy": best.accuracy})

        # Step 5: Researcher immediately searches again for 3rd capability
        interp_prop = self.pipeline.scout_next_capability("scout_agent_alpha")
        self.assertEqual(interp_prop.capability_name, "Abstract Interpretation Invariant Analyzer")

        # Check registry state
        all_proposals = self.pipeline.proposals
        self.assertEqual(len(all_proposals), 3)
        self.assertEqual(all_proposals[cegis_prop.proposal_id].status, "VERIFIED")
        self.assertEqual(all_proposals[mcts_prop.proposal_id].status, "VERIFIED")
        self.assertEqual(all_proposals[interp_prop.proposal_id].status, "PROPOSED")

    def test_audit_and_enforce_agent_missions(self):
        """Enforces that idle or mission-less agents are flagged for immediate termination."""
        from ace_autonomy.research_pipeline import audit_and_enforce_agent_missions

        active_agents = [
            {"conversationId": "ag_active_1", "role": "Capability Researcher", "state": "running"},
            {"conversationId": "ag_idle_2", "role": "Completed Scout", "state": "idle"},
            {"conversationId": "ag_unassigned_3", "role": "Orphaned Runner", "state": "running"},
        ]
        assigned_missions = {"ag_active_1"}

        audit = audit_and_enforce_agent_missions(active_agents, assigned_missions)
        self.assertFalse(audit["clean_state"])
        self.assertEqual(audit["valid_active_count"], 1)
        self.assertEqual(len(audit["termination_targets"]), 2)

        target_ids = {t["id"] for t in audit["termination_targets"]}
        self.assertEqual(target_ids, {"ag_idle_2", "ag_unassigned_3"})

    def test_neural_guided_search_pipeline_integration(self):
        """Tests end-to-end integration of Neural-Guided A* search in discovery pipeline."""
        # Advance until Neural-Guided A* is scouted
        found = None
        for _ in range(len(self.pipeline.CURRICULUM_TOPICS)):
            p = self.pipeline.scout_next_capability("neurosymbolic_scout")
            if "Neural-Guided A*" in p.capability_name:
                found = p
                break

        self.assertIsNotNone(found)
        self.assertIn("code/ace_neurosymbolic/neural_guided_search.py", found.suggested_implementation)

        # Execute synthesis using NeuralGuidedAStarSearch
        from ace_neurosymbolic.neural_guided_search import NeuralGuidedAStarSearch
        searcher = NeuralGuidedAStarSearch(max_expansions=100)
        data = [("ab", True), ("ba", True), ("a", False), ("b", False)]
        res = searcher.search(data, target_accuracy=1.0)
        self.assertTrue(res.success)

        # Mark implemented & verified
        p_impl = self.pipeline.mark_implemented(found.proposal_id, "commit_neurosymbolic_v1")
        self.assertEqual(p_impl.status, "IMPLEMENTED")
        p_ver = self.pipeline.mark_verified(
            found.proposal_id,
            {
                "accuracy": res.accuracy,
                "nodes_expanded": res.nodes_expanded,
                "speedup_factor": 5.0,
            }
        )
        self.assertEqual(p_ver.status, "VERIFIED")

    def test_differentiable_sketch_pipeline_integration(self):
        """Tests integration of Differentiable Program Sketching in discovery pipeline."""
        found = None
        for _ in range(len(self.pipeline.CURRICULUM_TOPICS)):
            p = self.pipeline.scout_next_capability("neurosymbolic_scout")
            if "Differentiable Neurosymbolic" in p.capability_name:
                found = p
                break

        self.assertIsNotNone(found)
        self.assertIn("code/ace_neurosymbolic/sketch_synthesizer.py", found.suggested_implementation)

        # Run synthesis via DifferentiableSketchSynthesizer
        from ace_neurosymbolic.sketch_synthesizer import (
            LogicalConjunctionSketch,
            DifferentiableSketchSynthesizer,
        )
        sketch = LogicalConjunctionSketch()
        train_data = [
            ("ab", True), ("axxb", True), ("a123b", True),
            ("ba", False), ("a", False), ("b", False),
        ]
        synth = DifferentiableSketchSynthesizer(learning_rate=2.0, max_steps=20, num_restarts=2, seed=99)
        res = synth.synthesize(sketch, train_data, target_accuracy=1.0)
        self.assertTrue(res.success)
        self.assertGreaterEqual(res.search_space_compression, 10.0)

        # Mark implemented & verified
        p_impl = self.pipeline.mark_implemented(found.proposal_id, "commit_sketch_v1")
        self.assertEqual(p_impl.status, "IMPLEMENTED")
        p_ver = self.pipeline.mark_verified(
            found.proposal_id,
            {
                "accuracy": res.accuracy,
                "total_steps": res.total_steps,
                "search_space_compression": res.search_space_compression,
            }
        )
        self.assertEqual(p_ver.status, "VERIFIED")


if __name__ == "__main__":
    unittest.main()

