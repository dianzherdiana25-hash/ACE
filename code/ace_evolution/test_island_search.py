"""Unit tests for Evolutionary Island Program Search."""
from __future__ import annotations

import unittest
from ace_evolution.island_search import EvolutionaryIslandSearch, TypedASTNode, ProgramCandidate


class TestIslandSearch(unittest.TestCase):
    def test_typed_ast_evaluation(self):
        # Build AST: word.count('a') == 2 * word.count('b')
        ca = TypedASTNode("count_a", "INT")
        cb = TypedASTNode("count_b", "INT")
        two = TypedASTNode("int_const", "INT", val=2)
        mul = TypedASTNode("mul", "INT", children=[two, cb])
        eq = TypedASTNode("eq", "BOOL", children=[ca, mul])

        self.assertTrue(eq.evaluate("aab"))
        self.assertFalse(eq.evaluate("ab"))
        self.assertEqual(eq.depth(), 3)
        self.assertIn("==", eq.to_code())

    def test_program_candidate_dataset_evaluation(self):
        root = TypedASTNode("starts_with", "BOOL", val="a")
        cand = ProgramCandidate(root)
        rows = [("a", True), ("ab", True), ("b", False), ("ba", False)]
        acc = cand.evaluate_dataset(rows)
        self.assertEqual(acc, 1.0)
        self.assertGreater(cand.score, 0.99)
        self.assertTrue(len(cand.behavior_hash()) > 0)

        func_code = cand.to_python_function("starts_a")
        self.assertIn("def starts_a(word: str) -> bool:", func_code)
        self.assertIn("ADVISOR_AGENT", func_code)

    def test_evolutionary_search_simple_target(self):
        # Target: starts with 'a' and ends with 'b'
        search = EvolutionaryIslandSearch(num_islands=2, island_population=15, max_depth=3, seed=123)
        train_data = [
            ("ab", True), ("aab", True), ("abb", True), ("aabb", True),
            ("ba", False), ("b", False), ("a", False), ("bb", False)
        ]
        best = search.search(train_data, max_generations=15, target_accuracy=1.0)
        self.assertGreaterEqual(best.accuracy, 0.75)


if __name__ == "__main__":
    unittest.main()
