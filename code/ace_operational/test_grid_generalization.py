"""Stage F universe evidence: new defect classes are real, the
universe builds deterministically, and arms differ only as designed."""
from __future__ import annotations

import unittest

from ace_operational.grid_generalization import ALL_DEFECTS, \
    CATALOG_DEFECTS, NEW_DEFECTS, _apply, _passes, _run, build_universe
from ace_operational.curriculum_lab import _GRID_SETS, \
    _NAVIGATE_REFERENCE


class NewDefectTests(unittest.TestCase):
    def test_new_classes_are_disjoint_from_catalog(self):
        self.assertFalse(set(NEW_DEFECTS) & set(CATALOG_DEFECTS))
        self.assertEqual(len(ALL_DEFECTS), 8)

    def test_each_new_defect_is_behaviourally_real(self):
        cases = [tuple(c) for c in _GRID_SETS[0]]
        truth = [_run(_NAVIGATE_REFERENCE, c) for c in cases]
        for name in NEW_DEFECTS:
            buggy = _apply(_NAVIGATE_REFERENCE, (name,))
            self.assertLess(_passes(buggy, cases, truth), len(cases),
                            f"{name} changes no behaviour")


class UniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.universe = build_universe()

    def test_deterministic(self):
        again = build_universe()
        self.assertEqual([t["task_id"] for t in again["tasks"]],
                         [t["task_id"] for t in self.universe["tasks"]])
        self.assertEqual(again["generation_failures"],
                         self.universe["generation_failures"])

    def test_subsets_present_and_holdout_isolated(self):
        subsets = {}
        for task in self.universe["tasks"]:
            subsets.setdefault(task["subset"], []).append(task)
        for name in ("train", "new_only", "mixed", "catalog_control"):
            self.assertIn(name, subsets)
        for task in subsets["train"]:
            self.assertTrue(
                set(task["defects"]) <= set(CATALOG_DEFECTS))
        for task in subsets["new_only"]:
            self.assertTrue(set(task["defects"]) <= set(NEW_DEFECTS))
            self.assertTrue(task["defects"])
        for task in subsets["mixed"]:
            self.assertEqual(len(set(task["defects"])
                                 & set(CATALOG_DEFECTS)), 1)
            self.assertEqual(len(set(task["defects"])
                                 & set(NEW_DEFECTS)), 1)

    def test_shown_and_holdout_are_disjoint_and_complete(self):
        for task in self.universe["tasks"]:
            shown = {tuple(c) for c in task["shown_cases"]}
            holdout = {tuple(c) for c in task["holdout_cases"]}
            self.assertFalse(shown & holdout)
            self.assertEqual(len(shown) + len(holdout), 20)

    def test_holdout_is_discriminative(self):
        # Every task's holdout must contain >= 3 cases the buggy
        # program fails — the v2 invalidation lesson (null control
        # solved 64/114 on non-discriminative holdouts).
        from ace_operational.grid_generalization import _run
        for task in self.universe["tasks"]:
            failing = sum(
                1 for case, want in zip(task["holdout_cases"],
                                        task["holdout_truth"])
                if _run(task["buggy_code"], tuple(case)) != want)
            self.assertGreaterEqual(failing, 3, task["task_id"])


if __name__ == "__main__":
    unittest.main()
