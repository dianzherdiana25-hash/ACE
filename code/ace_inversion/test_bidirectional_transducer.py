"""Unit tests for Bidirectional Program Inversion & Category-Theoretic Lenses."""
from __future__ import annotations

from typing import Any
import unittest
from ace_inversion.bidirectional_transducer import (
    ASTTransducerLens,
    BijectiveLens,
    DelimiterLens,
    FieldLens,
    Lens,
    ListMapLens,
    verify_lens_laws,
)


class TestBidirectionalTransducer(unittest.TestCase):
    def test_field_lens_and_laws(self):
        lens = FieldLens("count", default=0)

        sources = [
            {"count": 10, "name": "task_A", "active": True},
            {"count": 0, "name": "task_B", "active": False},
            {"count": 99, "name": "task_C", "active": True},
        ]
        views = [5, 42, -1]

        # 1. Get & Put functionality
        self.assertEqual(lens.get(sources[0]), 10)
        updated = lens.put(42, sources[0])
        self.assertEqual(updated["count"], 42)
        self.assertEqual(updated["name"], "task_A")  # Preserves un-viewed fields

        # 2. Category-theoretic lens laws verification
        laws = verify_lens_laws(lens, sources, views)
        self.assertTrue(laws["well_behaved"])
        self.assertTrue(laws["get_put_passed"])
        self.assertTrue(laws["put_get_passed"])
        self.assertTrue(laws["put_put_passed"])

    def test_lens_composition(self):
        # Nested source: {"program": {"params": {"max_depth": 5, "beam": 10}, "id": "p1"}}
        l1 = FieldLens("program")
        l2 = FieldLens("params")
        l3 = FieldLens("max_depth")

        composed = l1.compose(l2).compose(l3)

        source = {"program": {"params": {"max_depth": 5, "beam": 10}, "id": "p1"}}
        self.assertEqual(composed.get(source), 5)

        # Update max_depth to 8
        updated = composed.put(8, source)
        self.assertEqual(composed.get(updated), 8)
        self.assertEqual(updated["program"]["params"]["beam"], 10)  # Untouched
        self.assertEqual(updated["program"]["id"], "p1")  # Untouched

        # Lens laws on composition
        test_sources = [
            {"program": {"params": {"max_depth": 3, "beam": 4}, "id": "p_alpha"}},
            {"program": {"params": {"max_depth": 10, "beam": 20}, "id": "p_beta"}},
        ]
        laws = verify_lens_laws(composed, test_sources, [1, 15])
        self.assertTrue(laws["well_behaved"])

    def test_delimiter_lens_bijectivity(self):
        lens = DelimiterLens(",")

        raw = "alpha,beta,gamma"
        tokens = lens.get(raw)
        self.assertEqual(tokens, ["alpha", "beta", "gamma"])

        # Exact roundtrip 1: put(get(s)) == s
        self.assertEqual(lens.put(tokens), raw)

        # Exact roundtrip 2: get(put(v)) == v
        new_tokens = ["x", "y", "z", "w"]
        self.assertEqual(lens.get(lens.put(new_tokens)), new_tokens)

        laws = verify_lens_laws(lens, ["1,2,3", "a,b", ""], [["10", "20"], ["foo"]])
        self.assertTrue(laws["well_behaved"])

    def test_ast_transducer_lens_bijectivity(self):
        lens = ASTTransducerLens()

        expressions = [
            "(+ 1 2)",
            "(* (+ 2 3) (- 10 4))",
            "(if (> x 0) x (- 0 x))",
            "(map (lambda x (+ x 1)) (list 1 2 3))",
        ]

        for expr in expressions:
            ast = lens.get(expr)
            self.assertIsInstance(ast, dict)
            self.assertIn("op", ast)
            self.assertIn("args", ast)

            # Round-trip bijectivity f^{-1}(f(x)) == x
            reconstructed = lens.put(ast)
            self.assertEqual(reconstructed, expr)

        # Modify AST and format back
        ast_add = lens.get("(+ 1 2)")
        ast_add["op"] = "-"
        ast_add["args"][0] = 100
        new_expr = lens.put(ast_add)
        self.assertEqual(new_expr, "(- 100 2)")

        # Verify full lens laws
        views = [
            {"op": "+", "args": [4, 5]},
            {"op": "max", "args": [10, 20]},
        ]
        laws = verify_lens_laws(lens, expressions, views)
        self.assertTrue(laws["well_behaved"])

    def test_violation_detection_on_ill_behaved_lens(self):
        # A flawed lens that violates Put-Get (ignores view update)
        class BrokenLens(Lens[dict, Any]):
            def get(self, s):
                return s.get("x")
            def put(self, v, s):
                return s  # Does not update view!

        broken = BrokenLens()
        sources = [{"x": 1}, {"x": 2}]
        views = [10, 20]

        laws = verify_lens_laws(broken, sources, views)
        self.assertFalse(laws["well_behaved"])
        self.assertFalse(laws["put_get_passed"])
        self.assertGreater(laws["put_get_violations"], 0)


if __name__ == "__main__":
    unittest.main()
