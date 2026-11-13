"""B-3 substrate tests, mirroring test_grid_substrate's
three: variants change code and parse; the reference
produces NO variants (operators fire only on defect
signatures); the solver repairs single AND pair defects.
"""
import ast
import unittest

from ace_operational.curriculum_lab import generate_task, \
    verify_candidate
from ace_operational.pricing_substrate import pricing_variants, \
    solve_pricing
from ace_operational.reasoning_lab import Budget


def _budget_for(task):
    return Budget(1_000_000, entrypoint="total",
                  shown_cases=[tuple(c)
                               for c in task["shown_cases"]],
                  shown_expected=_shown_truth(task))


def _shown_truth(task):
    namespace: dict = {}
    exec(compile(task["reference_code"], "<ref>", "exec"), namespace)
    fn = namespace["total"]
    return [fn(*tuple(c)) for c in task["shown_cases"]]


class TestPricingSubstrate(unittest.TestCase):

    def test_variants_change_code_and_parse(self):
        task = generate_task("pricing", 1, seed=42)
        variants = pricing_variants(task["buggy_code"])
        self.assertTrue(variants)
        for text in variants:
            self.assertNotEqual(text, task["buggy_code"])
            ast.parse(text)

    def test_reference_produces_no_variants(self):
        for seed in (1, 2, 3, 42, 777):
            task = generate_task("pricing", 1, seed=seed)
            self.assertEqual(
                pricing_variants(task["reference_code"]), [],
                f"reference at seed {seed} produced variants")

    def test_solver_repairs_single_and_pair(self):
        for level, seed in ((1, 42), (2, 43), (3, 44), (3, 45)):
            task = generate_task("pricing", level, seed=seed)
            budget = _budget_for(task)
            solved = solve_pricing(
                task, budget,
                shown_total=len(task["shown_cases"]))
            result = verify_candidate(task, solved)
            self.assertEqual(result["passed"], result["total"],
                             f"L{level} seed {seed}: {result}")


if __name__ == "__main__":
    unittest.main()
