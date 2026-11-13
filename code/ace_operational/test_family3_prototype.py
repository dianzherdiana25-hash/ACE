"""Tests for the family-3 prototype (text_transform).

Validity gate, determinism, and case/truth consistency only —
no solving, no discovery.
"""
import unittest

from ace_operational.curriculum_lab import _run_cases
from ace_operational.family3_prototype import (
    DEFECT_NAMES, TextAdapter, build_text_task, render_reference)


class TestBuildTextTask(unittest.TestCase):

    def test_contract_shape(self):
        task = build_text_task(seed=91000, level=1)
        for key in ("task_id", "family", "level", "seed",
                    "buggy_code", "reference_code", "shown_cases",
                    "shown_truth", "holdout_cases", "holdout_truth",
                    "defects"):
            self.assertIn(key, task)
        self.assertEqual(task["family"], "text_transform")
        self.assertEqual(len(task["defects"]), 1)
        self.assertEqual(len(task["shown_cases"]),
                         len(task["shown_truth"]))
        self.assertEqual(len(task["holdout_cases"]),
                         len(task["holdout_truth"]))

    def test_determinism(self):
        self.assertEqual(build_text_task(seed=91007, level=2),
                         build_text_task(seed=91007, level=2))

    def test_validity_gate_buggy_fails_shown(self):
        for seed in range(91000, 91020):
            for level in (1, 2):
                task = build_text_task(seed=seed, level=level)
                out = _run_cases(task["buggy_code"], "transform",
                                 [tuple(c) for c in
                                  task["shown_cases"]])
                self.assertNotEqual(
                    out, task["shown_truth"],
                    f"buggy passes all shown: seed {seed} L{level}")

    def test_truth_is_reference_output(self):
        task = build_text_task(seed=91003, level=1)
        for cases_key, truth_key in (("shown_cases", "shown_truth"),
                                     ("holdout_cases",
                                      "holdout_truth")):
            out = _run_cases(task["reference_code"], "transform",
                             [tuple(c) for c in task[cases_key]])
            self.assertEqual(out, task[truth_key])

    def test_buggy_differs_from_reference(self):
        task = build_text_task(seed=91005, level=2)
        self.assertNotEqual(task["buggy_code"],
                            task["reference_code"])
        self.assertEqual(len(task["defects"]), 2)
        for name in task["defects"]:
            self.assertIn(name, DEFECT_NAMES)

    def test_holdout_also_exposes(self):
        task = build_text_task(seed=91011, level=1)
        out = _run_cases(task["buggy_code"], "transform",
                         [tuple(c) for c in task["holdout_cases"]])
        self.assertNotEqual(out, task["holdout_truth"])

    def test_every_defect_class_reachable(self):
        seen = set()
        for seed in range(91000, 91060):
            seen.update(build_text_task(seed=seed, level=1)["defects"])
        self.assertEqual(seen, set(DEFECT_NAMES))


class TestAdapterShape(unittest.TestCase):

    def test_budget_and_passes(self):
        task = build_text_task(seed=91002, level=1)
        adapter = TextAdapter()
        budget = adapter.make_budget(task)
        total = len(task["shown_cases"])
        self.assertEqual(budget.score(task["reference_code"]), total)
        self.assertLess(budget.score(task["buggy_code"]), total)
        self.assertEqual(
            adapter.passes(task["reference_code"],
                           task["holdout_cases"],
                           task["holdout_truth"]),
            len(task["holdout_cases"]))

    def test_render_reference_deterministic(self):
        self.assertEqual(render_reference("lower", "-", 12),
                         render_reference("lower", "-", 12))
        self.assertIn("slug[:9]",
                      render_reference("lower", "-", 12))


if __name__ == "__main__":
    unittest.main()
