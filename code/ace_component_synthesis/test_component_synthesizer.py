"""Unit tests for SyGuS-style Type-Directed Component-Based Program Synthesizer.

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

import unittest
from ace_component_synthesis.component_synthesizer import (
    Component,
    ComponentLibrary,
    ComponentNode,
    ComponentSynthesizer,
    ObservationalEquivalenceStore,
    SynthesisResult,
    compute_forward_valuation,
    TYPE_INT,
    TYPE_BOOL,
    TYPE_STR,
)


class TestComponentSynthesizer(unittest.TestCase):
    def setUp(self):
        self.library = ComponentLibrary.default()

    def test_component_library_arithmetic_and_string(self):
        """Test integer arithmetic (+, -, *, mod) and string operators (count, len)."""
        add = self.library.get("add")
        sub = self.library.get("sub")
        mul = self.library.get("mul")
        mod = self.library.get("mod")
        count = self.library.get("count")
        str_len = self.library.get("len")

        self.assertEqual(add.evaluate([7, 3]), 10)
        self.assertEqual(sub.evaluate([7, 3]), 4)
        self.assertEqual(mul.evaluate([7, 3]), 21)
        self.assertEqual(mod.evaluate([7, 3]), 1)
        self.assertEqual(count.evaluate(["banana", "an"]), 2)
        self.assertEqual(str_len.evaluate(["antigravity"]), 11)

        # Division by zero safety
        with self.assertRaises(ZeroDivisionError):
            mod.evaluate([5, 0])

    def test_component_library_boolean_and_relational(self):
        """Test boolean logic (and, or, not, startswith, endswith, contains) and relationals."""
        op_and = self.library.get("and")
        op_or = self.library.get("or")
        op_not = self.library.get("not")
        op_sw = self.library.get("startswith")
        op_ew = self.library.get("endswith")
        op_in = self.library.get("contains")

        self.assertTrue(op_and.evaluate([True, True]))
        self.assertFalse(op_and.evaluate([True, False]))
        self.assertTrue(op_or.evaluate([False, True]))
        self.assertFalse(op_not.evaluate([True]))

        self.assertTrue(op_sw.evaluate(["automaton", "auto"]))
        self.assertFalse(op_sw.evaluate(["automaton", "mat"]))
        self.assertTrue(op_ew.evaluate(["automaton", "on"]))
        self.assertTrue(op_in.evaluate(["automaton", "toma"]))

        eq = self.library.get("eq")
        neq = self.library.get("neq")
        lt = self.library.get("lt")
        gt = self.library.get("gt")
        lte = self.library.get("lte")
        gte = self.library.get("gte")

        self.assertTrue(eq.evaluate([42, 42]))
        self.assertFalse(eq.evaluate([42, 43]))
        self.assertTrue(neq.evaluate([10, 20]))
        self.assertTrue(lt.evaluate([3, 5]))
        self.assertFalse(gt.evaluate([3, 5]))
        self.assertTrue(lte.evaluate([5, 5]))
        self.assertTrue(gte.evaluate([5, 5]))

    def test_component_node_ast_methods_and_callable(self):
        """Test AST representation, size, depth, code generation, and compilation to callable."""
        # Build: (x + 2) * y
        x_node = ComponentNode("x", TYPE_INT, node_type="VAR", val="x")
        two_node = ComponentNode("2", TYPE_INT, node_type="CONST", val=2)
        add_comp = self.library.get("add")
        add_node = ComponentNode("add", TYPE_INT, node_type="OP", children=[x_node, two_node], component=add_comp)

        y_node = ComponentNode("y", TYPE_INT, node_type="VAR", val="y")
        mul_comp = self.library.get("mul")
        root_node = ComponentNode("mul", TYPE_INT, node_type="OP", children=[add_node, y_node], component=mul_comp)

        self.assertEqual(root_node.depth(), 3)
        self.assertEqual(root_node.size(), 5)
        self.assertEqual(root_node.evaluate({"x": 3, "y": 4}), 20)
        self.assertEqual(root_node.to_code(), "((x + 2) * y)")

        # Serialization to dictionary
        d = root_node.to_dict()
        self.assertEqual(d["name"], "mul")
        self.assertEqual(d["size"], 5)
        self.assertEqual(len(d["children"]), 2)

        # Compilation to callable
        fn = root_node.compile_to_callable(["x", "y"])
        self.assertEqual(fn(3, 4), 20)
        self.assertEqual(fn(0, 5), 10)

        # Export to TypedASTNode
        typed_ast = root_node.to_typed_ast()
        self.assertIsNotNone(typed_ast)

    def test_forward_valuation_and_zero_division_resilience(self):
        """Test forward valuation vector generation and graceful error handling."""
        envs = [{"x": 10, "y": 2}, {"x": 15, "y": 3}, {"x": 20, "y": 4}]
        x_node = ComponentNode("x", TYPE_INT, node_type="VAR", val="x")
        y_node = ComponentNode("y", TYPE_INT, node_type="VAR", val="y")

        add_node = ComponentNode("add", TYPE_INT, node_type="OP", children=[x_node, y_node], component=self.library.get("add"))
        val = compute_forward_valuation(add_node, envs)
        self.assertEqual(val, (12, 18, 24))

        # Test error resilience: division by zero
        zero_node = ComponentNode("0", TYPE_INT, node_type="CONST", val=0)
        bad_mod_node = ComponentNode("mod", TYPE_INT, node_type="OP", children=[x_node, zero_node], component=self.library.get("mod"))
        bad_val = compute_forward_valuation(bad_mod_node, envs)
        self.assertIsNone(bad_val)

    def test_observational_equivalence_pruning(self):
        """Test OE store identifying semantic equivalence classes and pruning syntactic duplicates."""
        store = ObservationalEquivalenceStore()
        envs = [{"x": 5}, {"x": 10}, {"x": 15}]

        x_node = ComponentNode("x", TYPE_INT, node_type="VAR", val="x")
        val_x = compute_forward_valuation(x_node, envs)
        self.assertTrue(store.register(x_node, val_x))
        self.assertEqual(store.retained_count, 1)
        self.assertEqual(store.pruned_count, 0)

        # Syntactic duplicate 1: x + 0
        zero_node = ComponentNode("0", TYPE_INT, node_type="CONST", val=0)
        x_plus_0 = ComponentNode("add", TYPE_INT, node_type="OP", children=[x_node, zero_node], component=self.library.get("add"))
        val_x_plus_0 = compute_forward_valuation(x_plus_0, envs)
        self.assertFalse(store.register(x_plus_0, val_x_plus_0))
        self.assertEqual(store.retained_count, 1)
        self.assertEqual(store.pruned_count, 1)

        # Syntactic duplicate 2: x * 1
        one_node = ComponentNode("1", TYPE_INT, node_type="CONST", val=1)
        x_mul_1 = ComponentNode("mul", TYPE_INT, node_type="OP", children=[x_node, one_node], component=self.library.get("mul"))
        val_x_mul_1 = compute_forward_valuation(x_mul_1, envs)
        self.assertFalse(store.register(x_mul_1, val_x_mul_1))
        self.assertEqual(store.retained_count, 1)
        self.assertEqual(store.pruned_count, 2)

        # Novel expression: x + 1
        x_plus_1 = ComponentNode("add", TYPE_INT, node_type="OP", children=[x_node, one_node], component=self.library.get("add"))
        val_x_plus_1 = compute_forward_valuation(x_plus_1, envs)
        self.assertTrue(store.register(x_plus_1, val_x_plus_1))
        self.assertEqual(store.retained_count, 2)
        self.assertEqual(store.pruned_count, 2)
        self.assertEqual(store.equivalence_classes_count(), 2)

    def test_end_to_end_arithmetic_synthesis(self):
        """Test synthesizing arithmetic expressions (x + y, x * 2, and (x - y)) from I/O specification."""
        synth = ComponentSynthesizer(max_level=3)

        # 1. Synthesize: x + y
        spec_add = [
            ({"x": 2, "y": 3}, 5),
            ({"x": 10, "y": 20}, 30),
            ({"x": -4, "y": 7}, 3),
            ({"x": 0, "y": 0}, 0),
        ]
        res_add = synth.synthesize(spec_add)
        self.assertEqual(res_add.status, "SUCCESS")
        self.assertIsNotNone(res_add.program)
        fn_add = res_add.program.compile_to_callable(["x", "y"])
        self.assertEqual(fn_add(50, 25), 75)
        self.assertEqual(res_add.provenance, "ADVISOR_AGENT")

        # 2. Synthesize: x * 2
        spec_double = [
            ({"x": 3}, 6),
            ({"x": 7}, 14),
            ({"x": 12}, 24),
            ({"x": 0}, 0),
        ]
        res_double = synth.synthesize(spec_double)
        self.assertEqual(res_double.status, "SUCCESS")
        fn_double = res_double.program.compile_to_callable(["x"])
        self.assertEqual(fn_double(21), 42)

    def test_end_to_end_boolean_relational_synthesis(self):
        """Test synthesizing relational and parity expressions (e.g. x % 2 == 0 or x > y)."""
        synth = ComponentSynthesizer(max_level=3)

        # Target: x > y
        spec_gt = [
            ({"x": 5, "y": 2}, True),
            ({"x": 1, "y": 4}, False),
            ({"x": 3, "y": 3}, False),
            ({"x": 10, "y": -2}, True),
        ]
        res_gt = synth.synthesize(spec_gt)
        self.assertEqual(res_gt.status, "SUCCESS")
        fn_gt = res_gt.program.compile_to_callable(["x", "y"])
        self.assertTrue(fn_gt(100, 50))
        self.assertFalse(fn_gt(20, 80))

        # Target: (x % 2) == 0 (even parity predicate)
        spec_even = [
            ({"x": 2}, True),
            ({"x": 3}, False),
            ({"x": 4}, True),
            ({"x": 5}, False),
            ({"x": 8}, True),
            ({"x": 9}, False),
        ]
        res_even = synth.synthesize(spec_even)
        self.assertEqual(res_even.status, "SUCCESS")
        fn_even = res_even.program.compile_to_callable(["x"])
        self.assertTrue(fn_even(100))
        self.assertFalse(fn_even(101))

    def test_end_to_end_string_predicate_synthesis(self):
        """Test synthesizing string prefix/suffix predicates."""
        synth = ComponentSynthesizer(max_level=3)

        # Target: word.startswith("a")
        spec_sw = [
            ("apple", True),
            ("airplane", True),
            ("banana", False),
            ("cherry", False),
            ("ant", True),
        ]
        res_sw = synth.synthesize(spec_sw, default_var_name="word")
        self.assertEqual(res_sw.status, "SUCCESS")
        fn_sw = res_sw.program.compile_to_callable(["word"])
        self.assertTrue(fn_sw("avatar"))
        self.assertFalse(fn_sw("grape"))

    def test_stratified_composition_pruning_efficiency(self):
        """Verify that OE pruning eliminates redundant states and logs accurate metrics."""
        synth = ComponentSynthesizer(max_level=2)
        # Target: x * y (generated after add, sub, and constant permutations, exercising OE pruning)
        spec = [
            ({"x": 2, "y": 3}, 6),
            ({"x": 4, "y": 5}, 20),
            ({"x": 3, "y": 7}, 21),
        ]
        res = synth.synthesize(spec)
        self.assertEqual(res.status, "SUCCESS")
        self.assertGreater(res.candidates_generated, 0)
        # Pruned expressions must be strictly positive due to arithmetic identities and symmetries
        self.assertGreater(res.candidates_pruned_oe, 0)
        self.assertGreater(res.candidates_retained, 0)
        self.assertGreater(res.equivalence_classes, 0)

    def test_unsat_termination(self):
        """Test synthesizer handles impossible specifications with UNSAT within bounds."""
        synth = ComponentSynthesizer(max_level=1, timeout_sec=2.0)
        # Deep function requiring multi-level composition not reachable at level 1
        spec_complex = [
            ({"x": 1, "y": 2}, 9999),
            ({"x": 2, "y": 3}, 8888),
        ]
        res = synth.synthesize(spec_complex)
        self.assertIn(res.status, ("UNSAT", "TIMEOUT"))
        self.assertIsNone(res.program)


if __name__ == "__main__":
    unittest.main()
