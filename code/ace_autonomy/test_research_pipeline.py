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


if __name__ == "__main__":
    unittest.main()
