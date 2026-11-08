"""Unit tests for MCTS Program Tree Exploration."""
from __future__ import annotations

import unittest
from ace_mcts.program_mcts import MCTSProgramSearch, MCTSNode


class TestMCTS(unittest.TestCase):
    def test_mcts_search_convergence(self):
        # Target: count('a') == count('b')
        train_data = [
            ("ab", True), ("ba", True), ("aabb", True), ("bbaa", True),
            ("a", False), ("b", False), ("aab", False), ("abb", False)
        ]

        mcts = MCTSProgramSearch(max_simulations=40, seed=42)
        best = mcts.search(train_data, target_accuracy=1.0)

        self.assertIsNotNone(best)
        self.assertGreaterEqual(best.accuracy, 0.75)
        self.assertIn("def mcts_fn(word: str) -> bool:", best.to_python_function("mcts_fn"))


if __name__ == "__main__":
    unittest.main()
