"""Unit tests for Differentiable Neurosymbolic Program Sketching."""
from __future__ import annotations

import unittest
import numpy as np

from ace_neurosymbolic.sketch_synthesizer import (
    DifferentiableSketchSynthesizer,
    GumbelSoftmax,
    LogicalConjunctionSketch,
    ProgramSketch,
    RelationalComparisonSketch,
    SmoothInterpreter,
    compare_with_unrelaxed_enumeration,
)


class TestSketchSynthesizer(unittest.TestCase):
    def setUp(self):
        self.gumbel = GumbelSoftmax(tau_0=2.0, gamma=0.92, tau_min=0.08, seed=42)

    def test_gumbel_softmax_annealing_and_sampling(self):
        # 1. Temperature annealing schedule
        t0 = self.gumbel.current_temperature(0)
        t5 = self.gumbel.current_temperature(5)
        t20 = self.gumbel.current_temperature(20)
        t100 = self.gumbel.current_temperature(100)

        self.assertAlmostEqual(t0, 2.0)
        self.assertLess(t5, t0)
        self.assertLess(t20, t5)
        self.assertEqual(t100, 0.08)  # Clamped to tau_min

        # 2. Gumbel softmax sample normalization
        logits = np.array([1.0, 2.0, -1.0, 0.5])
        sample = self.gumbel.sample(logits, tau=1.0)
        self.assertEqual(len(sample), 4)
        self.assertAlmostEqual(float(np.sum(sample)), 1.0, places=5)
        self.assertTrue(np.all(sample >= 0.0))

        # 3. Deterministic softmax
        prob = self.gumbel.deterministic_softmax(logits, tau=1.0)
        self.assertAlmostEqual(float(np.sum(prob)), 1.0, places=5)
        self.assertEqual(int(np.argmax(prob)), 1)  # Index 1 has largest logit (2.0)

    def test_smooth_interpreter_semantics(self):
        # Relational operations
        self.assertEqual(SmoothInterpreter.eval_relational_op("eq", 2.0, 2.0), 1.0)
        self.assertEqual(SmoothInterpreter.eval_relational_op("eq", 2.0, 3.0), 0.0)
        self.assertEqual(SmoothInterpreter.eval_relational_op("neq", 2.0, 3.0), 1.0)
        self.assertEqual(SmoothInterpreter.eval_relational_op("lte", 2.0, 3.0), 1.0)
        self.assertEqual(SmoothInterpreter.eval_relational_op("gte", 4.0, 2.0), 1.0)

        # Logic operations
        self.assertEqual(SmoothInterpreter.eval_logic_op("and", 1.0, 1.0), 1.0)
        self.assertEqual(SmoothInterpreter.eval_logic_op("and", 1.0, 0.0), 0.0)
        self.assertEqual(SmoothInterpreter.eval_logic_op("or", 1.0, 0.0), 1.0)
        self.assertEqual(SmoothInterpreter.eval_logic_op("or", 0.0, 0.0), 0.0)

    def test_sketch_structure_and_ast_building(self):
        sketch_rel = RelationalComparisonSketch()
        self.assertEqual(sketch_rel.name, "RelationalComparisonSketch")
        self.assertEqual(len(sketch_rel.slots), 3)
        self.assertEqual(sketch_rel.discrete_search_space_size, 4 * 10 * 10)  # 400

        # Build concrete AST
        ast = sketch_rel.build_concrete_ast([0, 0, 1])  # eq(count_a, count_b)
        self.assertEqual(ast.op, "eq")
        self.assertEqual(ast.return_type, "BOOL")
        self.assertEqual(ast.children[0].op, "count_a")
        self.assertEqual(ast.children[1].op, "count_b")
        self.assertTrue(ast.evaluate("aabb"))
        self.assertFalse(ast.evaluate("aab"))

        sketch_conj = LogicalConjunctionSketch()
        self.assertEqual(sketch_conj.discrete_search_space_size, 2 * 10 * 10)  # 200
        ast_conj = sketch_conj.build_concrete_ast([0, 0, 3])  # and(starts_a, ends_b)
        self.assertEqual(ast_conj.op, "and")
        self.assertTrue(ast_conj.evaluate("axxb"))
        self.assertFalse(ast_conj.evaluate("axxa"))

    def test_differentiable_conjunction_synthesis(self):
        train_data = [
            ("ab", True), ("axxb", True), ("a123b", True), ("abb", True),
            ("ba", False), ("a", False), ("b", False), ("xb", False), ("ax", False),
        ]

        sketch = LogicalConjunctionSketch()
        synth = DifferentiableSketchSynthesizer(learning_rate=2.0, max_steps=30, num_restarts=3, seed=42)
        res = synth.synthesize(sketch, train_data, target_accuracy=1.0, func_name="conj_predict")

        self.assertTrue(res.success)
        self.assertEqual(res.accuracy, 1.0)
        self.assertIsNotNone(res.candidate)
        self.assertIn("def conj_predict(word: str) -> bool:", res.function_code)
        self.assertGreater(len(res.loss_history), 0)
        self.assertGreater(len(res.temperature_history), 0)

    def test_differentiable_relational_synthesis(self):
        # Target: len(word) >= 2
        train_data = [
            ("ab", True), ("xyz", True), ("1234", True), ("aa", True),
            ("", False), ("a", False), ("b", False), ("z", False),
        ]

        sketch = RelationalComparisonSketch()
        synth = DifferentiableSketchSynthesizer(learning_rate=2.0, max_steps=30, num_restarts=1, seed=0)
        res = synth.synthesize(sketch, train_data, target_accuracy=1.0)

        self.assertTrue(res.success)
        self.assertEqual(res.accuracy, 1.0)
        self.assertIsNotNone(res.candidate)
        self.assertLessEqual(res.total_steps, 30)

    def test_search_space_compression_benchmark(self):
        """Verifies >= 10x search space compression vs unrelaxed discrete enumeration."""
        train_data = [
            ("ab", True), ("axxb", True), ("a123b", True), ("abb", True),
            ("ba", False), ("a", False), ("b", False), ("xb", False), ("ax", False),
        ]

        sketch = LogicalConjunctionSketch()
        bench = compare_with_unrelaxed_enumeration(sketch, train_data, target_accuracy=1.0)

        self.assertTrue(bench["differentiable_success"])
        self.assertEqual(bench["differentiable_accuracy"], 1.0)
        self.assertEqual(bench["discrete_search_space"], 200)

        # Discrete space is 200; differentiable takes <= 20 steps => >= 10x compression
        self.assertGreaterEqual(bench["search_space_compression"], 10.0)
        self.assertTrue(bench["compression_meets_target"])

    def test_edge_cases(self):
        synth = DifferentiableSketchSynthesizer(max_steps=5, num_restarts=1)
        sketch = LogicalConjunctionSketch()

        # Empty dataset
        res_empty = synth.synthesize(sketch, [])
        self.assertFalse(res_empty.success)
        self.assertEqual(res_empty.total_steps, 0)

        # Inconsistent dataset
        inconsistent = [("a", True), ("a", False)]
        res_inc = synth.synthesize(sketch, inconsistent)
        self.assertFalse(res_inc.success)


if __name__ == "__main__":
    unittest.main()
