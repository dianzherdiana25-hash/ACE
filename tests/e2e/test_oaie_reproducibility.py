"""E2E Test Suite: OAIE Progression, Reproducibility, and Lineage Governance (Requirement 10).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (lineage registration, ancestor traversal, bitvector registry caching)
Tier 2: Boundary & Corner Cases (lineage DAG cycle detection, missing parents, invalid rollbacks)
Tier 3: Cross-Feature Interactions (stagnation detection: duplicate source SHA, semantic bitvector equivalence, negative result retention)
Tier 4: Real-World Scenarios (multi-tier strategy repair ladder: plateau detection and strategy escalation)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_host_controller.lineage import (
    CandidateNode,
    LineageCycleError,
    LineageGraph,
    LineageNotFoundError,
)
from ace_self_dev.models import PersistentResearchState
from ace_self_dev.stagnation_detector import (
    BitvectorRegistry,
    DEFAULT_STRATEGY_LIMITS,
    StagnationDetector,
    StagnationType,
)


class TestOAIEReproducibilityE2E(unittest.TestCase):
    """End-to-end verification of OAIE capability progression, lineage DAGs, and anti-stagnation."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_e2e_oaie_"))
        self.registry_path = self.temp_dir / "bitvectors.json"
        self.detector = StagnationDetector(
            patience_k=3,
            min_improvement=0.0010,
            registry_path=str(self.registry_path),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_lineage_registration_and_ancestor_traversal(self):
        """Verify candidate registration in lineage DAG and accurate ancestor path tracking."""
        graph = LineageGraph(root_id="G0_root")
        graph.register_candidate("G0_root", None, "sha_genesis", 0)
        graph.update_status("G0_root", "ACCEPTED", holdout_score=0.50)

        c1 = graph.register_candidate("G1_cand_01", "G0_root", "sha_c1", 1)
        self.assertEqual(c1.lineage_depth, 1)
        self.assertEqual(graph.get_ancestors("G1_cand_01"), ["G0_root"])

        c2 = graph.register_candidate("G2_cand_02", "G1_cand_01", "sha_c2", 2)
        self.assertEqual(c2.lineage_depth, 2)
        self.assertEqual(graph.get_ancestors("G2_cand_02"), ["G1_cand_01", "G0_root"])

        # Update status and active head
        graph.update_status("G2_cand_02", "ACCEPTED", holdout_score=0.85)
        self.assertEqual(graph.active_head_id, "G2_cand_02")

    def test_tier1_bitvector_registry_caching_and_lookup(self):
        """Verify BitvectorRegistry records output bitvectors and performs O(1) lookup."""
        reg = BitvectorRegistry(persistence_path=self.registry_path)
        bv_hash = hashlib.sha256("10101011".encode("utf-8")).hexdigest()
        reg.register(
            task_id="task_parity",
            bitvector_hash=bv_hash,
            candidate_id="cand_101",
            cycle_id=1,
            score=0.88,
            bitvector="10101011",
        )

        self.assertTrue(reg.has("task_parity", bv_hash))
        match = reg.lookup("task_parity", bv_hash)
        self.assertIsNotNone(match)
        self.assertEqual(match["candidate_id"], "cand_101")
        self.assertEqual(match["score"], 0.88)

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_lineage_cycle_detection_raises_error(self):
        """Verify that attempting to create a circular dependency in lineage raises LineageCycleError."""
        graph = LineageGraph(root_id="root")
        graph.register_candidate("root", None, "sha_root", 0)
        graph.register_candidate("node_a", "root", "sha_a", 1)
        graph.register_candidate("node_b", "node_a", "sha_b", 2)

        # Artificially force node_a's parent to node_b to create a cycle
        graph.nodes["node_a"].parent_id = "node_b"

        with self.assertRaises(LineageCycleError):
            graph.get_ancestors("node_b")

    def test_tier2_lineage_missing_parent_and_duplicate_registration_rejected(self):
        """Verify missing parent raises LineageNotFoundError and duplicate ID raises ValueError."""
        graph = LineageGraph()
        with self.assertRaises(LineageNotFoundError):
            graph.register_candidate("cand_orphan", "non_existent_parent", "sha_xyz", 1)

        graph.register_candidate("node_1", None, "sha_1", 0)
        with self.assertRaises(ValueError):
            graph.register_candidate("node_1", None, "sha_duplicate", 0)

    def test_tier2_invalid_rollback_target_rejected(self):
        """Verify rolling back to a non-existent or non-ancestor candidate is rejected."""
        graph = LineageGraph(root_id="root")
        graph.register_candidate("root", None, "sha_root", 0)
        graph.update_status("root", "ACCEPTED")
        graph.register_candidate("cand_active", "root", "sha_active", 1)
        graph.update_status("cand_active", "ACCEPTED")

        with self.assertRaises(LineageNotFoundError):
            graph.rollback_to("non_existent_cand")

        # Candidate that is not an ancestor
        graph.register_candidate("divergent_cand", "root", "sha_div", 1)
        with self.assertRaises(ValueError):
            graph.rollback_to("divergent_cand")

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_stagnation_detector_catches_syntactic_duplication(self):
        """Verify StagnationDetector detects duplicate source SHA against completed cycles."""
        state = PersistentResearchState(
            schema_version="2.0",
            active_generation_id="G1_cand_01",
            completed_cycles=[
                {
                    "cycle_id": 1,
                    "candidate_id": "cand_01",
                    "source_sha": "sha_duplicate_target",
                    "decision": "ACCEPTED",
                }
            ],
        )

        is_dup, match_cand, match_cycle = self.detector.check_duplicate_source_sha(
            "sha_duplicate_target", state
        )
        self.assertTrue(is_dup)
        self.assertEqual(match_cand, "cand_01")
        self.assertEqual(match_cycle, 1)

        is_dup_fresh, _, _ = self.detector.check_duplicate_source_sha("sha_completely_new", state)
        self.assertFalse(is_dup_fresh)

    def test_tier3_stagnation_detector_catches_semantic_equivalence(self):
        """Verify StagnationDetector identifies candidates producing identical bitvectors."""
        bv_hash = hashlib.sha256("00110011".encode("utf-8")).hexdigest()
        self.detector.registry.register(
            task_id="task_k1",
            bitvector_hash=bv_hash,
            candidate_id="cand_prior",
            cycle_id=2,
            score=0.75,
        )

        is_equiv, match_info = self.detector.check_semantic_equivalence("task_k1", bv_hash)
        self.assertTrue(is_equiv)
        self.assertEqual(match_info["candidate_id"], "cand_prior")

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_patience_window_detects_plateau_stagnation(self):
        """Verify patience window detects lack of improvement over K cycles to trigger repair ladder escalation."""
        # Setup 4 cycles with plateau scores (0.70, 0.70, 0.70, 0.70)
        state = PersistentResearchState(
            schema_version="2.0",
            active_generation_id="G1_plateau",
            completed_cycles=[
                {"cycle_id": 1, "target_task_id": "task_k2", "holdout_score": 0.70},
                {"cycle_id": 2, "target_task_id": "task_k2", "holdout_score": 0.70},
                {"cycle_id": 3, "target_task_id": "task_k2", "holdout_score": 0.70},
                {"cycle_id": 4, "target_task_id": "task_k2", "holdout_score": 0.70},
            ],
        )

        is_stagnated, consecutive_no_imp, best_score, history = self.detector.check_patience_window(
            state, task_id="task_k2", patience_k=3
        )
        self.assertTrue(is_stagnated, "Patience window must detect plateau stagnation!")
        self.assertEqual(consecutive_no_imp, 3)
        self.assertEqual(best_score, 0.70)

    def test_tier4_strategy_limits_ladder_defined(self):
        """Verify the 5-tier strategy repair ladder limits are defined for autonomous escalation."""
        self.assertIn("LINEAR_MUTATION", DEFAULT_STRATEGY_LIMITS)
        self.assertIn("SYNTHESIZE_COMPOSITE_MECHANISM", DEFAULT_STRATEGY_LIMITS)
        self.assertIn("SYNTHESIZE_GATED_EXPRESSION_TREE", DEFAULT_STRATEGY_LIMITS)
        self.assertIn("RELATIONAL_MULTI_CLAUSE", DEFAULT_STRATEGY_LIMITS)
        self.assertIn("MULTI_TASK_DISPATCH", DEFAULT_STRATEGY_LIMITS)


if __name__ == "__main__":
    unittest.main()
