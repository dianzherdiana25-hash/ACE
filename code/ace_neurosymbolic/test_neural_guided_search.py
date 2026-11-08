"""Unit tests for Neural-Guided A* Heuristic Program Search."""
from __future__ import annotations

import unittest

from ace_neurosymbolic.neural_guided_search import (
    ExhaustiveProgramSearch,
    Grammar,
    Hole,
    NeuralGuidedAStarSearch,
    PartialAST,
    ProductionRule,
    StatisticalFeatureEstimator,
    benchmark_speedup,
)


class TestNeuralGuidedSearch(unittest.TestCase):
    def setUp(self):
        self.grammar = Grammar()
        self.estimator = StatisticalFeatureEstimator()

    def test_partial_ast_and_hole_lifecycle(self):
        # 1. Hole creation
        hole_bool = PartialAST.make_hole(1, "BOOL", depth=1)
        self.assertTrue(hole_bool.is_hole)
        self.assertTrue(hole_bool.has_holes())
        self.assertFalse(hole_bool.is_complete())
        self.assertEqual(len(hole_bool.get_holes()), 1)
        self.assertEqual(hole_bool.get_holes()[0].target_type, "BOOL")

        # 2. Compound node with holes
        h_int1 = PartialAST.make_hole(2, "INT", depth=2)
        h_int2 = PartialAST.make_hole(3, "INT", depth=2)
        eq_node = PartialAST.make_compound("eq", "BOOL", [h_int1, h_int2])
        self.assertFalse(eq_node.is_hole)
        self.assertTrue(eq_node.has_holes())
        self.assertEqual(len(eq_node.get_holes()), 2)
        self.assertEqual(eq_node.size(), 3)
        self.assertEqual(eq_node.depth(), 2)

        # Incomplete AST cannot evaluate or convert to TypedASTNode
        with self.assertRaises(RuntimeError):
            eq_node.evaluate("ab")
        with self.assertRaises(ValueError):
            eq_node.to_typed_ast()

        # 3. Filling holes sequentially
        term_ca = PartialAST.make_terminal("count_a", "INT")
        ast_step1 = eq_node.fill_hole(2, term_ca)
        self.assertEqual(len(ast_step1.get_holes()), 1)
        self.assertEqual(ast_step1.get_holes()[0].hole_id, 3)

        term_cb = PartialAST.make_terminal("count_b", "INT")
        complete_ast = ast_step1.fill_hole(3, term_cb)
        self.assertFalse(complete_ast.has_holes())
        self.assertTrue(complete_ast.is_complete())
        self.assertEqual(complete_ast.to_code(), '(word.count("a") == word.count("b"))')

        # 4. Evaluation and conversion of complete AST
        self.assertTrue(complete_ast.evaluate("aabb"))
        self.assertFalse(complete_ast.evaluate("aab"))

        typed_node = complete_ast.to_typed_ast()
        self.assertEqual(typed_node.op, "eq")
        self.assertEqual(typed_node.return_type, "BOOL")
        self.assertEqual(len(typed_node.children), 2)
        self.assertEqual(typed_node.children[0].op, "count_a")
        self.assertEqual(typed_node.children[1].op, "count_b")

    def test_grammar_rules_and_instantiation(self):
        int_rules = self.grammar.get_rules_for_type("INT")
        bool_rules = self.grammar.get_rules_for_type("BOOL")

        self.assertGreater(len(int_rules), 5)
        self.assertGreater(len(bool_rules), 5)

        # Terminals vs compounds
        int_terms = self.grammar.get_rules_for_type("INT", allow_compounds=False)
        self.assertTrue(all(r.is_terminal for r in int_terms))

        counter = 0

        def gen_id():
            nonlocal counter
            counter += 1
            return counter

        # Instantiate compound rule
        eq_rule = next(r for r in bool_rules if r.name == "eq")
        instantiated = eq_rule.instantiate(gen_id, current_depth=1)
        self.assertEqual(instantiated.op, "eq")
        self.assertEqual(len(instantiated.children), 2)
        self.assertTrue(instantiated.children[0].is_hole)
        self.assertEqual(instantiated.children[0].hole.target_type, "INT")
        self.assertEqual(instantiated.children[1].hole.target_type, "INT")

    def test_statistical_feature_estimator(self):
        # Dataset where count('a') == count('b') defines positive class
        data = [
            ("ab", True), ("ba", True), ("aabb", True), ("bbaa", True),
            ("a", False), ("b", False), ("aab", False), ("abb", False),
        ]

        signals = self.estimator.extract_dataset_signals(data)
        self.assertEqual(signals["a_eq_b"], 1.0)
        self.assertEqual(signals["a_neq_b"], 0.0)

        priors = self.estimator.compute_rule_distribution(self.grammar, data)
        # Verify that 'eq', 'count_a', and 'count_b' have significantly higher prior probability than irrelevant ops
        self.assertGreater(priors["eq"], priors["lte"])
        self.assertGreater(priors["eq"], priors["gte"])
        self.assertGreater(priors["count_a"], priors["const_4"])
        self.assertGreater(priors["count_b"], priors["const_4"])

    def test_neural_guided_search_equality_task(self):
        # Target: count('a') == count('b')
        train_data = [
            ("ab", True), ("ba", True), ("aabb", True), ("bbaa", True), ("abab", True),
            ("a", False), ("b", False), ("aab", False), ("abb", False), ("aaab", False),
        ]

        searcher = NeuralGuidedAStarSearch(max_expansions=100)
        result = searcher.search(train_data, target_accuracy=1.0, func_name="eq_classifier")

        self.assertTrue(result.success)
        self.assertEqual(result.accuracy, 1.0)
        self.assertIsNotNone(result.candidate)
        self.assertIn("def eq_classifier(word: str) -> bool:", result.function_code)
        self.assertIn('word.count("a")', result.solution_expr)
        self.assertIn('word.count("b")', result.solution_expr)
        self.assertIn("==", result.solution_expr)
        # Verify search efficiency: expands under 30 nodes
        self.assertLessEqual(result.nodes_expanded, 30)

    def test_neural_guided_search_conjunction_task(self):
        # Target: starts_with('a') and ends_with('b')
        train_data = [
            ("ab", True), ("axxb", True), ("a123b", True), ("abb", True),
            ("ba", False), ("a", False), ("b", False), ("xb", False), ("ax", False),
        ]

        searcher = NeuralGuidedAStarSearch(max_expansions=100)
        result = searcher.search(train_data, target_accuracy=1.0)

        self.assertTrue(result.success)
        self.assertEqual(result.accuracy, 1.0)
        self.assertIn("startswith", result.solution_expr)
        self.assertIn("endswith", result.solution_expr)
        self.assertIn("and", result.solution_expr)
        self.assertLessEqual(result.nodes_expanded, 30)

    def test_neural_guided_search_threshold_task(self):
        # Target: len(word) >= 2
        train_data = [
            ("ab", True), ("xyz", True), ("1234", True), ("aa", True),
            ("", False), ("a", False), ("b", False), ("z", False),
        ]

        searcher = NeuralGuidedAStarSearch(max_expansions=100)
        result = searcher.search(train_data, target_accuracy=1.0)

        self.assertTrue(result.success)
        self.assertEqual(result.accuracy, 1.0)
        self.assertIn("len(word)", result.solution_expr)
        self.assertIn(">=", result.solution_expr)
        self.assertLessEqual(result.nodes_expanded, 30)

    def test_speedup_and_soundness_benchmark(self):
        """Verifies that Neural-Guided A* achieves >= 5x speedup over exhaustive search without compromising soundness."""
        train_data = [
            ("ab", True), ("ba", True), ("aabb", True), ("bbaa", True), ("abab", True),
            ("a", False), ("b", False), ("aab", False), ("abb", False), ("aaab", False),
        ]

        bench = benchmark_speedup(train_data, target_accuracy=1.0, max_exhaustive_expansions=1500)

        self.assertTrue(bench["both_sound"])
        self.assertTrue(bench["neural_guided"]["success"])
        self.assertEqual(bench["neural_guided"]["accuracy"], 1.0)
        self.assertTrue(bench["exhaustive"]["success"])
        self.assertEqual(bench["exhaustive"]["accuracy"], 1.0)

        # Speedup requirement: >= 5x
        speedup = bench["node_expansion_speedup"]
        self.assertGreaterEqual(speedup, 5.0)
        self.assertLessEqual(bench["neural_guided"]["nodes_expanded"], 25)
        self.assertGreaterEqual(bench["exhaustive"]["nodes_expanded"], 100)

    def test_edge_cases_and_soundness_preservation(self):
        searcher = NeuralGuidedAStarSearch(max_expansions=20)
        res_empty = searcher.search([], target_accuracy=1.0)
        self.assertFalse(res_empty.success)
        self.assertEqual(res_empty.nodes_expanded, 0)

        # Unsolvable / inconsistent task within budget: returns best partial or failure cleanly
        unsolvable_data = [("a", True), ("a", False)]
        res_unsolvable = searcher.search(unsolvable_data, target_accuracy=1.0)
        self.assertFalse(res_unsolvable.success)


if __name__ == "__main__":
    unittest.main()
