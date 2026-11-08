"""Unit test suite for ACE Equality Saturation & E-Graphs AST Rewriting Engine.

Tests:
1. UnionFind path compression and union-by-rank.
2. ENode hashing, equality, and canonicalization.
3. Delayed congruence closure (Nelson-Oppen / Downey-Sethi-Tarjan).
4. Pattern parsing and multi-level e-class matching.
5. Non-destructive equality saturation with zero cyclic blowup on commutative rules.
6. Algebraic parsimony optimization and shortest-path AST extraction.
7. Boolean logic optimization (double negation, identity, idempotence).
8. Dynamic constant folding over arithmetic expressions.
9. Confluence under rule permutation.
10. Semantic preservation: original and extracted AST evaluate identically on test strings.
"""
from __future__ import annotations

import random
import unittest

from ace_evolution.island_search import TypedASTNode
from ace_egraph.equality_saturation import (
    ASTDepthCost,
    ASTSizeCost,
    EClass,
    EGraph,
    ENode,
    EqualitySaturation,
    Extractor,
    Pattern,
    RewriteRule,
    UnionFind,
    build_ace_dsl_rewrites,
)


class TestEqualitySaturation(unittest.TestCase):
    """Test suite for E-Graph and Equality Saturation."""

    def test_union_find_operations(self):
        """Tests disjoint-set operations, path compression, and rank updates."""
        uf = UnionFind()
        s0 = uf.make_set()
        s1 = uf.make_set()
        s2 = uf.make_set()
        s3 = uf.make_set()

        self.assertEqual(len(uf), 4)
        self.assertNotEqual(uf.find(s0), uf.find(s1))

        # Union s0 and s1
        r01 = uf.union(s0, s1)
        self.assertEqual(uf.find(s0), r01)
        self.assertEqual(uf.find(s1), r01)
        self.assertNotEqual(uf.find(s2), r01)

        # Union s2 and s3
        r23 = uf.union(s2, s3)
        self.assertEqual(uf.find(s2), r23)

        # Union both components
        r_all = uf.union(s0, s3)
        for s in [s0, s1, s2, s3]:
            self.assertEqual(uf.find(s), r_all)

    def test_enode_canonicalization_and_hash(self):
        """Tests that ENode properly canonicalizes child IDs under union-find."""
        uf = UnionFind()
        c0 = uf.make_set()
        c1 = uf.make_set()
        c2 = uf.make_set()

        enode1 = ENode(op="add", children=(c0, c1), return_type="INT")
        enode2 = ENode(op="add", children=(c0, c2), return_type="INT")

        # Initially different
        self.assertNotEqual(enode1, enode2)

        # Union c1 and c2
        uf.union(c1, c2)

        # Canonicalize
        canon1 = enode1.canonicalize(uf)
        canon2 = enode2.canonicalize(uf)
        self.assertEqual(canon1, canon2)
        self.assertEqual(hash(canon1), hash(canon2))

    def test_egraph_congruence_closure(self):
        """Verifies Nelson-Oppen congruence closure invariant.
        
        If a == c, then f(a, b) == f(c, b).
        """
        egraph = EGraph()

        # Build leaf symbols a, b, c
        a = egraph.add_ast(TypedASTNode("count_a", "INT"))
        b = egraph.add_ast(TypedASTNode("count_b", "INT"))
        c = egraph.add_ast(TypedASTNode("len", "INT"))

        # Build f(a, b) and f(c, b)
        fab = egraph.add_node(ENode(op="add", children=(a, b), return_type="INT"))
        fcb = egraph.add_node(ENode(op="add", children=(c, b), return_type="INT"))

        self.assertNotEqual(egraph.find(fab), egraph.find(fcb))

        # Union a and c
        egraph.union(a, c)

        # Before rebuild, they might not be congruent in memo yet
        self.assertFalse(egraph.clean)

        # Execute delayed congruence closure rebuild
        repairs = egraph.rebuild()
        self.assertTrue(egraph.clean)
        self.assertGreaterEqual(repairs, 1)

        # Now f(a, b) and f(c, b) must be congruent in the exact same e-class!
        self.assertEqual(egraph.find(fab), egraph.find(fcb))

    def test_pattern_parsing_and_matching(self):
        """Tests s-expression pattern parsing and e-class pattern matching."""
        p1 = Pattern.parse("(add ?x 0)")
        self.assertEqual(p1.op, "add")
        self.assertEqual(len(p1.children), 2)
        self.assertTrue(p1.children[0].is_var)
        self.assertEqual(p1.children[0].var_name, "x")
        self.assertEqual(p1.children[1].op, "int_const")
        self.assertEqual(p1.children[1].val, 0)

        # Match in EGraph
        egraph = EGraph()
        ast = TypedASTNode("add", "INT", children=[
            TypedASTNode("count_a", "INT"),
            TypedASTNode("int_const", "INT", val=0),
        ])
        root_id = egraph.add_ast(ast)

        matches = list(p1.match_class(egraph, root_id, {}))
        self.assertEqual(len(matches), 1)
        subst = matches[0]
        self.assertIn("x", subst)

        # x must point to e-class containing count_a
        x_class = subst["x"]
        self.assertTrue(any(n.op == "count_a" for n in egraph.classes[x_class].nodes))

    def test_non_destructive_saturation_and_zero_cyclic_blowup(self):
        """Verifies that bidirectional commutative rules do not cause infinite loops or cyclic blowup."""
        commute_rule = RewriteRule(
            name="commute-add",
            lhs=Pattern.parse("(add ?x ?y)"),
            rhs=Pattern.parse("(add ?y ?x)"),
        )
        eq_sat = EqualitySaturation(rules=[commute_rule])

        egraph = EGraph()
        ast = TypedASTNode("add", "INT", children=[
            TypedASTNode("count_a", "INT"),
            TypedASTNode("count_b", "INT"),
        ])
        root_id = egraph.add_ast(ast)

        # Run saturation
        report = eq_sat.run(egraph, root_id, max_iterations=20)

        # Saturated must be True (fixed-point reached!)
        self.assertTrue(report.saturated)
        self.assertLessEqual(report.iterations, 3)

        # Root class must contain both add(a, b) and add(b, a)
        root_class = egraph.classes[egraph.find(root_id)]
        self.assertEqual(len(root_class.nodes), 2)

    def test_algebraic_simplification_and_extraction(self):
        """Tests multi-step algebraic simplification: mul(add(x, 0), 1) -> x."""
        # AST: (count_a + 0) * 1
        ca = TypedASTNode("count_a", "INT")
        zero = TypedASTNode("int_const", "INT", val=0)
        one = TypedASTNode("int_const", "INT", val=1)
        add_node = TypedASTNode("add", "INT", children=[ca, zero])
        root_ast = TypedASTNode("mul", "INT", children=[add_node, one])

        eq_sat = EqualitySaturation()
        optimal_ast, report = eq_sat.rewrite(root_ast)

        # Optimized AST must be simplified directly to count_a
        self.assertEqual(optimal_ast.op, "count_a")
        self.assertEqual(len(optimal_ast.children), 0)
        self.assertLess(report.final_cost, report.initial_cost)

    def test_boolean_logic_simplification(self):
        """Tests boolean simplification: not(not(and(starts_with('a'), True))) -> starts_with('a')."""
        sw = TypedASTNode("starts_with", "BOOL", val="a")
        true_node = TypedASTNode("bool_const", "BOOL", val=True)
        and_node = TypedASTNode("and", "BOOL", children=[sw, true_node])
        not1 = TypedASTNode("not", "BOOL", children=[and_node])
        root_ast = TypedASTNode("not", "BOOL", children=[not1])

        eq_sat = EqualitySaturation()
        optimal_ast, report = eq_sat.rewrite(root_ast)

        self.assertEqual(optimal_ast.op, "starts_with")
        self.assertEqual(optimal_ast.val, "a")
        self.assertEqual(len(optimal_ast.children), 0)

    def test_constant_folding(self):
        """Tests dynamic constant folding: 10 + (3 * 4) -> 22."""
        ten = TypedASTNode("int_const", "INT", val=10)
        three = TypedASTNode("int_const", "INT", val=3)
        four = TypedASTNode("int_const", "INT", val=4)
        mul_node = TypedASTNode("mul", "INT", children=[three, four])
        root_ast = TypedASTNode("add", "INT", children=[ten, mul_node])

        eq_sat = EqualitySaturation()
        optimal_ast, report = eq_sat.rewrite(root_ast)

        self.assertEqual(optimal_ast.op, "int_const")
        self.assertEqual(optimal_ast.val, 22)

    def test_confluence_under_rule_permutation(self):
        """Verifies confluence: rule reordering converges to the same simplified AST."""
        # AST: (count_a - count_a) + (len * 1) -> 0 + len -> len
        ca1 = TypedASTNode("count_a", "INT")
        ca2 = TypedASTNode("count_a", "INT")
        sub_node = TypedASTNode("sub", "INT", children=[ca1, ca2])

        len_node = TypedASTNode("len", "INT")
        one = TypedASTNode("int_const", "INT", val=1)
        mul_node = TypedASTNode("mul", "INT", children=[len_node, one])

        root_ast = TypedASTNode("add", "INT", children=[sub_node, mul_node])

        rules_order1 = build_ace_dsl_rewrites()
        rules_order2 = list(reversed(rules_order1))

        eq1 = EqualitySaturation(rules=rules_order1)
        eq2 = EqualitySaturation(rules=rules_order2)

        opt1, _ = eq1.rewrite(root_ast)
        opt2, _ = eq2.rewrite(root_ast)

        self.assertEqual(opt1.op, "len")
        self.assertEqual(opt2.op, "len")
        self.assertEqual(opt1.to_code(), opt2.to_code())

    def test_semantic_preservation_on_evaluation(self):
        """Verifies that original and extracted simplified AST evaluate identically across diverse inputs."""
        # AST: or(and(starts_with("a"), starts_with("a")), False) -> starts_with("a")
        sw1 = TypedASTNode("starts_with", "BOOL", val="a")
        sw2 = TypedASTNode("starts_with", "BOOL", val="a")
        and_node = TypedASTNode("and", "BOOL", children=[sw1, sw2])
        false_node = TypedASTNode("bool_const", "BOOL", val=False)
        root_ast = TypedASTNode("or", "BOOL", children=[and_node, false_node])

        eq_sat = EqualitySaturation()
        optimal_ast, _ = eq_sat.rewrite(root_ast)

        test_words = ["", "a", "ab", "b", "ba", "aaa", "bbb"]
        for word in test_words:
            orig_eval = root_ast.evaluate(word)
            opt_eval = optimal_ast.evaluate(word)
            self.assertEqual(orig_eval, opt_eval, f"Semantic mismatch on word '{word}'")


if __name__ == "__main__":
    unittest.main()
