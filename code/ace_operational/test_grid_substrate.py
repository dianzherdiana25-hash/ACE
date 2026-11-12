"""Stage C tests: the structural grid substrate."""
from __future__ import annotations

import unittest

from ace_operational.curriculum_lab import (InvalidTaskError, generate_task,
                                            verify_candidate)
from ace_operational.grid_substrate import grid_variants, solve_grid
from ace_operational.reasoning_lab import Budget


def _budget_for(task, limit=400):
    shown = [tuple(c) for c in task["shown_cases"]]
    expected = {tuple(c): e for c, e in zip(task["cases"], task["expected"])}
    return (Budget(limit=limit, entrypoint=task["entrypoint"],
                   shown_cases=shown,
                   shown_expected=[expected[c] for c in shown]),
            len(shown))


class GridSubstrateTests(unittest.TestCase):
    def test_variants_change_code_and_parse(self):
        task = generate_task("grid", 2, seed=3)
        variants = grid_variants(task["buggy_code"])
        self.assertTrue(variants)
        for variant in variants:
            self.assertNotEqual(variant, task["buggy_code"])
            compile(variant, "<v>", "exec")

    def test_reference_has_no_variants(self):
        task = generate_task("grid", 1, seed=1)
        self.assertEqual(grid_variants(task["reference_code"]), [])

    def test_solver_repairs_single_and_pair_defects(self):
        solved = attempted = 0
        for level in (1, 2, 3):
            for seed in range(1, 11):
                try:
                    task = generate_task("grid", level, seed=seed)
                except InvalidTaskError:
                    continue
                attempted += 1
                budget, total = _budget_for(task)
                code = solve_grid(task, budget, shown_total=total)
                out = verify_candidate(task, code)
                solved += 1 if out["passed"] == out["total"] else 0
        self.assertGreater(attempted, 20)
        self.assertEqual(solved, attempted)


if __name__ == "__main__":
    unittest.main()
