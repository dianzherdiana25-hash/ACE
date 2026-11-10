"""E2E Test Suite: Memory Retention, Capability Transfer, and Continual Learning (Requirement 7).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (experience recording, vectorization, cosine similarity retrieval, persistent reload)
Tier 2: Boundary & Corner Cases (empty memory queries, orthogonal vectors, zero-token inputs, corrupted storage)
Tier 3: Cross-Feature Interactions (decision filtering, cross-task capability transfer)
Tier 4: Real-World Scenarios (multi-cycle knowledge transfer without catastrophic forgetting)
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_cognition.evolutionary_memory import (
    EvolutionaryMemory,
    MemoryEntry,
    _compute_vector,
    _cosine_similarity,
    _tokenize,
)


class TestMemoryContinualLearningE2E(unittest.TestCase):
    """End-to-end verification of associative memory retention and capability transfer."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_e2e_memory_"))
        self.memory_path = self.temp_dir / "evolutionary_memory.json"
        self.memory = EvolutionaryMemory(storage_path=str(self.memory_path))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_record_and_retrieve_experience(self):
        """Verify recording experience vectorizes code snippet and persists to disk."""
        code = "def parity_check(n: int) -> int:\n    return n % 2\n"
        entry = self.memory.record_experience(
            cycle_id=1,
            task_id="task_parity",
            hypothesis_id="hyp_parity_01",
            source_code=code,
            score=0.92,
            decision="ACCEPTED",
            metadata={"strategy": "modulo_congruence"},
        )

        self.assertIsInstance(entry, MemoryEntry)
        self.assertEqual(len(self.memory.entries), 1)
        self.assertTrue(self.memory_path.exists())

        # Query with structurally similar code
        similar = self.memory.query_similar("def check_mod(x: int) -> int:\n    return x % 2\n", top_k=1)
        self.assertEqual(len(similar), 1)
        matched_entry, similarity_score = similar[0]
        self.assertEqual(matched_entry.entry_id, entry.entry_id)
        self.assertGreater(similarity_score, 0.40)

    def test_tier1_persistence_survives_reload(self):
        """Verify memory instances reloaded from disk retain all historical entries."""
        for c in range(1, 4):
            self.memory.record_experience(
                cycle_id=c,
                task_id=f"task_{c}",
                hypothesis_id=f"hyp_{c}",
                source_code=f"def func_{c}(x):\n    return x + {c}\n",
                score=0.75 + c * 0.05,
                decision="ACCEPTED" if c > 1 else "REJECTED",
            )

        # Create fresh instance pointing to same file
        reloaded_memory = EvolutionaryMemory(storage_path=str(self.memory_path))
        self.assertEqual(len(reloaded_memory.entries), 3)
        self.assertEqual(reloaded_memory.entries[0].cycle_id, 1)
        self.assertEqual(reloaded_memory.entries[2].cycle_id, 3)

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_empty_query_returns_no_results(self):
        """Verify querying with empty or unmatchable strings returns empty list."""
        self.memory.record_experience(
            cycle_id=1,
            task_id="task_01",
            hypothesis_id="hyp_01",
            source_code="def alpha(): return 1",
            score=0.8,
            decision="ACCEPTED",
        )
        empty_res = self.memory.query_similar("", min_similarity=0.1)
        self.assertEqual(empty_res, [])

    def test_tier2_orthogonal_vectors_yield_zero_similarity(self):
        """Verify completely disjoint token distributions return exactly 0.0 cosine similarity."""
        vec_a = {"alpha": 1.0, "beta": 0.5}
        vec_b = {"gamma": 1.0, "delta": 0.5}
        sim = _cosine_similarity(vec_a, vec_b)
        self.assertEqual(sim, 0.0)

    def test_tier2_self_similarity_is_one(self):
        """Verify vector cosine similarity with itself equals 1.0."""
        tokens = _tokenize("def compute(x: int, y: int) -> int:\n    return x * y + 42")
        vec = _compute_vector(tokens)
        sim = _cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_tier2_corrupted_storage_file_fails_safely(self):
        """Verify loading from a corrupted or non-JSON storage file initializes cleanly with 0 entries."""
        self.memory_path.write_text("CORRUPTED_NON_JSON_DATA", encoding="utf-8")
        corrupted_memory = EvolutionaryMemory(storage_path=str(self.memory_path))
        self.assertEqual(len(corrupted_memory.entries), 0)

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_decision_filtering_separates_accepted_from_rejected_motifs(self):
        """Verify query_similar filters by acceptance decision to prevent reusing falsified code."""
        # Record one accepted and one rejected entry with identical code structure
        self.memory.record_experience(
            cycle_id=1,
            task_id="task_fail",
            hypothesis_id="hyp_fail",
            source_code="def candidate(x): return x * 3",
            score=0.20,
            decision="REJECTED",
        )
        self.memory.record_experience(
            cycle_id=2,
            task_id="task_pass",
            hypothesis_id="hyp_pass",
            source_code="def candidate(x): return x * 3",
            score=0.88,
            decision="ACCEPTED",
        )

        # Filter strictly for ACCEPTED candidates
        accepted_results = self.memory.query_similar("def candidate(x): return x * 3", decision_filter="ACCEPTED")
        self.assertEqual(len(accepted_results), 1)
        self.assertEqual(accepted_results[0][0].decision, "ACCEPTED")

        # Filter strictly for REJECTED candidates
        rejected_results = self.memory.query_similar("def candidate(x): return x * 3", decision_filter="REJECTED")
        self.assertEqual(len(rejected_results), 1)
        self.assertEqual(rejected_results[0][0].decision, "REJECTED")

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_continual_learning_cross_task_capability_transfer(self):
        """Simulate continual learning: a motif discovered on Task A is retrieved to solve Task B."""
        # Cycle 1: Discover modular stride motif on Task A
        task_a_code = (
            "def stride_filter(length: int, stride_val: int) -> int:\n"
            "    return (length % 3 == 0) and (stride_val > 1)\n"
        )
        self.memory.record_experience(
            cycle_id=1,
            task_id="task_A_congruence",
            hypothesis_id="hyp_stride_01",
            source_code=task_a_code,
            score=0.94,
            decision="ACCEPTED",
            metadata={"domain": "arithmetic_modular"},
        )

        # Cycle 5: Facing Task B (unknown family, but requires stride filtering)
        task_b_query = (
            "def evaluate_candidate(length: int, stride_val: int) -> int:\n"
            "    # Need stride filter logic\n"
            "    return (length % 3 == 0) and (stride_val > 1)\n"
        )
        retrieved = self.memory.query_similar(task_b_query, top_k=1, min_similarity=0.30)
        self.assertEqual(len(retrieved), 1)
        transferred_entry, transfer_sim = retrieved[0]

        # Verify capability transfer
        self.assertEqual(transferred_entry.task_id, "task_A_congruence")
        self.assertIn("stride_filter", transferred_entry.source_code)
        self.assertGreater(transfer_sim, 0.60)


if __name__ == "__main__":
    unittest.main()
