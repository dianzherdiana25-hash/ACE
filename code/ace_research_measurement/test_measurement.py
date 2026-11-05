"""Focused public-development tests: run with python -m unittest ... -v."""
from dataclasses import replace
import json
import unittest

from .experiment import make_rows, memorizer_control, score_gamer_control, run
from .measurement import measure, semantic_fingerprint


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.rows = make_rows()

    def test_deterministic(self):
        self.assertEqual(run(), run())

    def test_positive_control_has_ood_and_composition(self):
        result = measure(self.rows)
        self.assertGreater(result["evaluation"]["novel"]["family_macro_delta"], 0)
        self.assertGreater(result["evaluation"]["compositional"]["family_macro_delta"], 0)
        self.assertEqual(result["claim_gate"], "NOT_CONFIRMED")

    def test_memorizer_does_not_transfer(self):
        result = measure(memorizer_control(self.rows))
        self.assertEqual(result["evaluation"]["novel"]["family_macro_delta"], 0)
        self.assertEqual(result["evaluation"]["all"]["micro_delta"], 0)

    def test_goodhart_detects_macro_inversion(self):
        result = measure(score_gamer_control(make_rows(unbalanced=True)))
        self.assertGreater(result["evaluation"]["all"]["micro_delta"], 0)
        self.assertLess(result["evaluation"]["all"]["family_macro_delta"], 0)
        self.assertIn("GOODHART_MICRO_MACRO_INVERSION", result["signals"])

    def test_renamed_duplicate_is_rejected(self):
        duplicate = replace(self.rows[0], case_id="renamed", split="evaluation", novel=False)
        with self.assertRaisesRegex(ValueError, "semantic duplicate"):
            measure(self.rows + [duplicate])

    def test_renamed_identical_eval_rejected(self):
        original = next(r for r in self.rows if r.split == "evaluation")
        with self.assertRaisesRegex(ValueError, "semantic duplicate"):
            measure(self.rows + [replace(original, case_id="alias")])

    def test_false_novel_tag_rejected(self):
        target = next(i for i, r in enumerate(self.rows) if r.split == "evaluation" and r.family == "add")
        rows = self.rows[:]
        rows[target] = replace(rows[target], novel=True)
        with self.assertRaisesRegex(ValueError, "novel task shares"):
            measure(rows)

    def test_negative_and_boolean_cost_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid nonnegative"):
            measure([replace(self.rows[0], baseline_ops=-1), *self.rows[1:]])
        with self.assertRaisesRegex(ValueError, "invalid nonnegative"):
            measure([replace(self.rows[0], candidate_labels=True), *self.rows[1:]])

    def test_noncanonical_semantic_fingerprint_rejected(self):
        with self.assertRaisesRegex(ValueError, "canonical lowercase"):
            measure([replace(self.rows[0], fingerprint="A" * 64), *self.rows[1:]])

    def test_empty_eval_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing evaluation"):
            measure([r for r in self.rows if r.split != "evaluation"])

    def test_order_independent_result(self):
        self.assertEqual(measure(self.rows), measure(list(reversed(self.rows))))

    def test_canonical_semantics_independent_of_key_order(self):
        self.assertEqual(semantic_fingerprint({"x": 2, "a": 1}),
                         semantic_fingerprint({"a": 1, "x": 2}))

    def test_new_family_does_not_imply_confirmatory_claim(self):
        self.assertEqual(measure(self.rows)["status"], "PUBLIC_SYNTHETIC_DIAGNOSTIC_ONLY")


if __name__ == "__main__":
    unittest.main()
