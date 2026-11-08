"""Unit tests for ACE Multi-Objective Pareto DSL Optimizer (NSGA-II)."""
from __future__ import annotations

import math
import random
import unittest

from ace_evolution.island_search import TypedASTNode
from ace_evolution.pareto_dsl_optimizer import (
    CandidateT,
    CurriculumStage,
    DSLGrammarWeights,
    GrammarCandidate,
    HierarchicalSubGrammar,
    MacroPrimitive,
    Objectives,
    OptimizationCurriculum,
    ParetoDSLOptimizer,
    ParetoOptimizationResult,
    ProgramParetoCandidate,
    WeightedASTGenerator,
    calculate_crowding_distance,
    compute_hypervolume_2d,
    crowded_comparison,
    fast_non_dominated_sort,
    tournament_selection,
)


class DummyCandidate:
    """Mock candidate for deterministic unit testing of sorting and distances."""

    def __init__(self, accuracy: float, parsimony: float, latency: float):
        self.objectives = Objectives(accuracy=accuracy, parsimony=parsimony, latency=latency)
        self.rank: int = -1
        self.crowding_distance: float = 0.0


class TestObjectives(unittest.TestCase):
    def test_strict_dominance(self):
        # A is strictly better in all 3 objectives
        a = Objectives(accuracy=0.9, parsimony=3.0, latency=0.01)
        b = Objectives(accuracy=0.7, parsimony=5.0, latency=0.05)
        self.assertTrue(a.dominates(b))
        self.assertFalse(b.dominates(a))

    def test_partial_dominance(self):
        # A is strictly better in accuracy, identical in parsimony and latency
        a = Objectives(accuracy=0.85, parsimony=4.0, latency=0.02)
        b = Objectives(accuracy=0.80, parsimony=4.0, latency=0.02)
        self.assertTrue(a.dominates(b))
        self.assertFalse(b.dominates(a))

    def test_tradeoff_no_dominance(self):
        # A has higher accuracy but worse parsimony than B
        a = Objectives(accuracy=0.95, parsimony=10.0, latency=0.01)
        b = Objectives(accuracy=0.80, parsimony=2.0, latency=0.01)
        self.assertFalse(a.dominates(b))
        self.assertFalse(b.dominates(a))

    def test_identical_equality(self):
        # Identical candidates do not dominate each other
        a = Objectives(accuracy=0.80, parsimony=4.0, latency=0.02)
        b = Objectives(accuracy=0.80, parsimony=4.0, latency=0.02)
        self.assertFalse(a.dominates(b))
        self.assertFalse(b.dominates(a))

    def test_to_dict_format(self):
        obj = Objectives(accuracy=0.87654321, parsimony=3.14159, latency=0.000123456)
        d = obj.to_dict()
        self.assertIn("accuracy", d)
        self.assertIn("parsimony", d)
        self.assertIn("latency", d)
        self.assertEqual(d["accuracy"], 0.876543)


class TestFastNonDominatedSort(unittest.TestCase):
    def test_empty_population(self):
        self.assertEqual(fast_non_dominated_sort([]), [])

    def test_single_front_mutually_non_dominated(self):
        # 3 candidates with trade-offs between accuracy and parsimony
        c1 = DummyCandidate(accuracy=1.0, parsimony=9.0, latency=0.01)
        c2 = DummyCandidate(accuracy=0.8, parsimony=5.0, latency=0.01)
        c3 = DummyCandidate(accuracy=0.6, parsimony=2.0, latency=0.01)

        fronts = fast_non_dominated_sort([c1, c2, c3])  # type: ignore
        self.assertEqual(len(fronts), 1)
        self.assertEqual(len(fronts[0]), 3)
        for c in [c1, c2, c3]:
            self.assertEqual(c.rank, 0)

    def test_multiple_fronts(self):
        # c1 dominates c2, and c2 dominates c3
        c1 = DummyCandidate(accuracy=0.9, parsimony=2.0, latency=0.01)
        c2 = DummyCandidate(accuracy=0.8, parsimony=4.0, latency=0.02)
        c3 = DummyCandidate(accuracy=0.7, parsimony=6.0, latency=0.03)

        fronts = fast_non_dominated_sort([c2, c3, c1])  # type: ignore
        self.assertEqual(len(fronts), 3)
        self.assertIn(c1, fronts[0])
        self.assertIn(c2, fronts[1])
        self.assertIn(c3, fronts[2])
        self.assertEqual(c1.rank, 0)
        self.assertEqual(c2.rank, 1)
        self.assertEqual(c3.rank, 2)


class TestCrowdingDistance(unittest.TestCase):
    def test_boundary_points_infinite(self):
        c1 = DummyCandidate(accuracy=0.5, parsimony=2.0, latency=0.01)
        c2 = DummyCandidate(accuracy=0.7, parsimony=4.0, latency=0.02)
        c3 = DummyCandidate(accuracy=0.9, parsimony=6.0, latency=0.03)

        front = [c1, c2, c3]
        calculate_crowding_distance(front)  # type: ignore

        # Boundary points on accuracy (c1 and c3) must have infinite distance
        self.assertEqual(c1.crowding_distance, float("inf"))
        self.assertEqual(c3.crowding_distance, float("inf"))
        # Intermediate point must have positive finite distance
        self.assertFalse(math.isinf(c2.crowding_distance))
        self.assertGreater(c2.crowding_distance, 0.0)

    def test_two_elements_infinite(self):
        c1 = DummyCandidate(accuracy=0.6, parsimony=3.0, latency=0.01)
        c2 = DummyCandidate(accuracy=0.8, parsimony=5.0, latency=0.02)
        front = [c1, c2]
        calculate_crowding_distance(front)  # type: ignore
        self.assertEqual(c1.crowding_distance, float("inf"))
        self.assertEqual(c2.crowding_distance, float("inf"))

    def test_zero_range_handling(self):
        # All candidates have identical accuracy and latency; only parsimony varies
        c1 = DummyCandidate(accuracy=0.8, parsimony=2.0, latency=0.01)
        c2 = DummyCandidate(accuracy=0.8, parsimony=4.0, latency=0.01)
        c3 = DummyCandidate(accuracy=0.8, parsimony=6.0, latency=0.01)
        front = [c1, c2, c3]
        calculate_crowding_distance(front)  # type: ignore
        self.assertEqual(c1.crowding_distance, float("inf"))
        self.assertEqual(c3.crowding_distance, float("inf"))
        self.assertGreaterEqual(c2.crowding_distance, 0.0)


class TestCrowdedComparison(unittest.TestCase):
    def test_rank_preference(self):
        c1 = DummyCandidate(accuracy=0.9, parsimony=3.0, latency=0.01)
        c1.rank = 0
        c1.crowding_distance = 1.0

        c2 = DummyCandidate(accuracy=0.8, parsimony=4.0, latency=0.02)
        c2.rank = 1
        c2.crowding_distance = 100.0  # Larger distance but worse rank

        self.assertEqual(crowded_comparison(c1, c2), -1)  # c1 preferred  # type: ignore
        self.assertEqual(crowded_comparison(c2, c1), 1)   # type: ignore

    def test_crowding_distance_tiebreak(self):
        c1 = DummyCandidate(accuracy=0.9, parsimony=3.0, latency=0.01)
        c1.rank = 0
        c1.crowding_distance = 2.5

        c2 = DummyCandidate(accuracy=0.85, parsimony=2.0, latency=0.01)
        c2.rank = 0
        c2.crowding_distance = 1.2

        self.assertEqual(crowded_comparison(c1, c2), -1)  # c1 preferred (larger distance)  # type: ignore
        self.assertEqual(crowded_comparison(c2, c1), 1)   # type: ignore

    def test_identical_tied(self):
        c1 = DummyCandidate(accuracy=0.9, parsimony=3.0, latency=0.01)
        c1.rank = 0
        c1.crowding_distance = 2.0

        c2 = DummyCandidate(accuracy=0.9, parsimony=3.0, latency=0.01)
        c2.rank = 0
        c2.crowding_distance = 2.0

        self.assertEqual(crowded_comparison(c1, c2), 0)  # type: ignore


class TestDSLGrammarWeights(unittest.TestCase):
    def test_vector_roundtrip(self):
        gw1 = DSLGrammarWeights()
        gw1.terminal_int["count_a"] = 3.5
        gw1.compound_int["mul"] = 2.2
        gw1.structural["terminal_prob"] = 0.42

        vec = gw1.to_vector()
        gw2 = DSLGrammarWeights.from_vector(vec)

        self.assertAlmostEqual(gw2.terminal_int["count_a"], 3.5)
        self.assertAlmostEqual(gw2.compound_int["mul"], 2.2)
        self.assertAlmostEqual(gw2.structural["terminal_prob"], 0.42)

    def test_normalization(self):
        gw = DSLGrammarWeights(
            terminal_int={"count_a": -5.0, "count_b": float("nan"), "len": 1.0, "int_const": 1.0},
            structural={"terminal_prob": 1.5, "bool_cmp_prob": -0.2},
        )
        self.assertGreaterEqual(gw.terminal_int["count_a"], 0.001)
        self.assertGreaterEqual(gw.terminal_int["count_b"], 0.001)
        self.assertLessEqual(gw.structural["terminal_prob"], 0.95)
        self.assertGreaterEqual(gw.structural["bool_cmp_prob"], 0.05)

    def test_mutation_and_crossover(self):
        rng = random.Random(123)
        parent1 = DSLGrammarWeights()
        parent2 = DSLGrammarWeights()
        parent2.terminal_int["count_a"] = 5.0

        mutated = parent1.mutate(rng, rate=1.0, scale=0.5)
        self.assertNotEqual(parent1.to_vector(), mutated.to_vector())

        child = parent1.crossover(parent2, rng, alpha=0.5)
        self.assertEqual(len(child.to_vector()), len(parent1.to_vector()))


class TestWeightedASTGenerator(unittest.TestCase):
    def test_generation_types_and_depth(self):
        rng = random.Random(42)
        gw = DSLGrammarWeights()
        generator = WeightedASTGenerator(gw)

        int_node = generator.generate("INT", depth=1, max_depth=3, rng=rng)
        self.assertEqual(int_node.return_type, "INT")
        self.assertLessEqual(int_node.depth(), 3)
        val = int_node.evaluate("aab")
        self.assertIsInstance(val, int)

        bool_node = generator.generate("BOOL", depth=1, max_depth=3, rng=rng)
        self.assertEqual(bool_node.return_type, "BOOL")
        self.assertLessEqual(bool_node.depth(), 3)
        bval = bool_node.evaluate("aab")
        self.assertIsInstance(bval, (bool, int))


class TestParetoCandidates(unittest.TestCase):
    def test_program_pareto_candidate_evaluation(self):
        root = TypedASTNode("starts_with", "BOOL", val="a")
        cand = ProgramParetoCandidate(root)
        dataset = [("a", True), ("ab", True), ("b", False), ("ba", False)]
        objs = cand.evaluate(dataset, deterministic_latency=True)

        self.assertEqual(objs.accuracy, 1.0)
        self.assertEqual(objs.parsimony, 1.0)
        self.assertGreater(objs.latency, 0.0)

    def test_grammar_candidate_evaluation(self):
        gw = DSLGrammarWeights()
        cand = GrammarCandidate(gw)
        dataset = [("a", True), ("b", False)]
        objs = cand.evaluate(dataset, samples=4, max_depth=2, rng=random.Random(1), deterministic_latency=True)

        self.assertGreaterEqual(objs.accuracy, 0.0)
        self.assertGreaterEqual(objs.parsimony, 1.0)
        self.assertGreater(objs.latency, 0.0)
        self.assertIsNotNone(cand.best_program)


class TestHypervolumeAndKneePoint(unittest.TestCase):
    def test_compute_hypervolume_2d(self):
        c1 = DummyCandidate(accuracy=1.0, parsimony=10.0, latency=0.01)
        c2 = DummyCandidate(accuracy=0.5, parsimony=2.0, latency=0.01)
        hv = compute_hypervolume_2d([c1, c2], ref_accuracy=0.0, ref_parsimony=20.0)  # type: ignore
        self.assertGreater(hv, 0.0)

    def test_find_knee_point(self):
        optimizer = ParetoDSLOptimizer(seed=42)
        c_acc = DummyCandidate(accuracy=1.0, parsimony=30.0, latency=0.1)
        c_knee = DummyCandidate(accuracy=0.98, parsimony=3.0, latency=0.001)
        c_cheap = DummyCandidate(accuracy=0.50, parsimony=1.0, latency=0.0001)
        front = [c_acc, c_knee, c_cheap]

        knee = optimizer.find_knee_point(front)  # type: ignore
        self.assertIs(knee, c_knee)


class TestNSGAIIOptimization(unittest.TestCase):
    def test_optimize_grammar_weights(self):
        optimizer = ParetoDSLOptimizer(
            population_size=6,
            crossover_rate=0.7,
            mutation_rate=0.3,
            max_depth=3,
            samples_per_grammar=4,
            seed=7,
            deterministic_latency=True,
        )
        train_data = [("a", True), ("ab", True), ("b", False), ("ba", False)]
        result = optimizer.optimize_grammar_weights(train_data, generations=3)

        self.assertIsInstance(result, ParetoOptimizationResult)
        self.assertGreater(len(result.pareto_front), 0)
        self.assertGreater(len(result.all_fronts), 0)
        self.assertIsNotNone(result.knee_point)
        self.assertEqual(len(result.history), 3)

        d = result.to_dict()
        self.assertIn("pareto_front_size", d)
        self.assertIn("hypervolume_2d", d)

    def test_optimize_programs(self):
        optimizer = ParetoDSLOptimizer(
            population_size=10,
            crossover_rate=0.6,
            mutation_rate=0.4,
            max_depth=3,
            seed=42,
            deterministic_latency=True,
        )
        # Prefix 'a' target
        train_data = [
            ("a", True), ("ab", True), ("aab", True), ("aaa", True),
            ("b", False), ("ba", False), ("bb", False), ("bba", False),
        ]
        result = optimizer.optimize_programs(train_data, generations=4)
        self.assertGreater(len(result.pareto_front), 0)
        self.assertGreaterEqual(result.best_by_accuracy.objectives.accuracy, 0.75)


class TestOptimizationCurriculum(unittest.TestCase):
    def test_curriculum_stages_ordering(self):
        curriculum = OptimizationCurriculum()
        self.assertEqual(len(curriculum.stages), 8)
        for i, stage in enumerate(curriculum.stages):
            self.assertEqual(stage.level, i)
            self.assertGreater(len(stage.train_data), 0)
            self.assertGreater(len(stage.val_data), 0)

    def test_prepare_next_curriculum_transfer(self):
        curriculum = OptimizationCurriculum()
        prior = DSLGrammarWeights()
        prior.terminal_int["count_a"] = 1.0

        stage1, weights1 = curriculum.prepare_next_curriculum(0, prior)
        self.assertEqual(stage1.level, 1)
        self.assertEqual(stage1.stage_id, "CURR_S1_PARITY")
        # Parity transfer emphasizes count_a and mod
        self.assertGreater(weights1.terminal_int["count_a"], 1.0)
        self.assertGreater(weights1.compound_int["mod"], 1.0)

    def test_dyck_balanced_primitive(self):
        node = TypedASTNode("dyck_balanced", "BOOL")
        self.assertTrue(node.evaluate(""))
        self.assertTrue(node.evaluate("ab"))
        self.assertTrue(node.evaluate("aabb"))
        self.assertTrue(node.evaluate("abab"))
        self.assertFalse(node.evaluate("ba"))
        self.assertFalse(node.evaluate("a"))
        self.assertFalse(node.evaluate("b"))
        self.assertFalse(node.evaluate("abba"))  # prefix abb has depth -1

    def test_prepare_next_curriculum_dyck_transfer(self):
        curriculum = OptimizationCurriculum()
        prior = DSLGrammarWeights()

        stage4, weights4 = curriculum.prepare_next_curriculum(3, prior)
        self.assertEqual(stage4.level, 4)
        self.assertEqual(stage4.stage_id, "CURR_S4_DYCK_CONTEXT_FREE")
        self.assertGreaterEqual(weights4.terminal_bool["dyck_balanced"], 4.0)

    def test_prepare_next_curriculum_stage5_transfer(self):
        curriculum = OptimizationCurriculum()
        prior = DSLGrammarWeights()

        stage5, weights5 = curriculum.prepare_next_curriculum(4, prior)
        self.assertEqual(stage5.level, 5)
        self.assertEqual(stage5.stage_id, "CURR_S5_CONTEXT_SENSITIVE")
        self.assertGreaterEqual(weights5.terminal_bool["graph_bfs"], 4.0)
        self.assertGreaterEqual(weights5.compound_bool_logic["and"], 3.0)

    def test_prepare_next_curriculum_stage6_transfer(self):
        curriculum = OptimizationCurriculum()
        prior = DSLGrammarWeights()

        stage6, weights6 = curriculum.prepare_next_curriculum(5, prior)
        self.assertEqual(stage6.level, 6)
        self.assertEqual(stage6.stage_id, "CURR_S6_PROGRAM_INDUCTION")
        self.assertGreaterEqual(weights6.terminal_bool["graph_bfs"], 3.0)


class TestHierarchicalSubGrammar(unittest.TestCase):
    def test_macro_primitive_creation_and_eval(self):
        # Build macro AST: word.count('a') == word.count('b')
        ca = TypedASTNode("count_a", "INT")
        cb = TypedASTNode("count_b", "INT")
        eq = TypedASTNode("eq", "BOOL", children=[ca, cb])

        macro = MacroPrimitive(
            name="macro_balanced",
            return_type="BOOL",
            ast=eq,
            description="Checks if count_a == count_b",
        )
        self.assertEqual(macro.name, "macro_balanced")
        d = macro.to_dict()
        self.assertIn("code", d)
        self.assertEqual(d["size"], 3)

        node = macro.to_node()
        self.assertTrue(node.evaluate("ab"))
        self.assertTrue(node.evaluate("aabb"))
        self.assertFalse(node.evaluate("aab"))
        self.assertEqual(node.size(), 1)  # Compressed abstraction representation
        self.assertIn("macro_balanced(word)", node.to_code())

    def test_hierarchical_subgrammar_induction(self):
        hsg = HierarchicalSubGrammar()
        ca = TypedASTNode("count_a", "INT")
        two = TypedASTNode("int_const", "INT", val=2)
        mod = TypedASTNode("mod", "INT", children=[ca, two])
        zero = TypedASTNode("int_const", "INT", val=0)
        even_parity = TypedASTNode("eq", "BOOL", children=[mod, zero])

        macro = hsg.induce_macro_from_ast("macro_even_a", even_parity, weight=5.0)
        self.assertIn("macro_even_a", hsg.grammar.terminal_bool)
        self.assertEqual(hsg.grammar.terminal_bool["macro_even_a"], 5.0)
        self.assertIn("macro_even_a", hsg.grammar.macros)

        # Test sampling with WeightedASTGenerator
        rng = random.Random(42)
        generator = WeightedASTGenerator(hsg.grammar)
        sampled = generator.generate("BOOL", depth=1, max_depth=2, rng=rng)
        self.assertIsInstance(sampled, TypedASTNode)

    def test_multilayer_program_evaluation(self):
        # Layer 1 Macro: graph reachability
        macro_graph = MacroPrimitive("macro_graph", "BOOL", TypedASTNode("graph_bfs", "BOOL"))
        # Layer 1 Macro: balance
        ca = TypedASTNode("count_a", "INT")
        cb = TypedASTNode("count_b", "INT")
        macro_bal = MacroPrimitive("macro_bal", "BOOL", TypedASTNode("eq", "BOOL", children=[ca, cb]))

        # Layer 2 Coordinator AST: macro_graph and macro_bal
        coord = TypedASTNode("and", "BOOL", children=[macro_graph.to_node(), macro_bal.to_node()])
        self.assertEqual(coord.size(), 3)
        self.assertTrue(coord.evaluate("abbaba"))
        self.assertFalse(coord.evaluate("bbbaaa"))  # disconnected


if __name__ == "__main__":
    unittest.main()
