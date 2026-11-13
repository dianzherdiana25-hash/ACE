"""A/B/C v3 build step 1 (PR #147): the lifted
`solve_task` solver — uncapped behaviour solves through
the adapter like the old nested loop, and the
score-call budget actually binds."""
import unittest

from ace_operational.operator_discovery import solve_task
from ace_operational.pricing_adapter import PricingAdapter, \
    build_pricing_task


class TestSolveTask(unittest.TestCase):

    def setUp(self):
        self.adapter = PricingAdapter()
        self.task = build_pricing_task(seed=42, level=1)

    def test_uncapped_solves_single_defect(self):
        solved = solve_task(self.task, self.adapter)
        cases = [tuple(c) for c in self.task["holdout_cases"]]
        passed = self.adapter.passes(
            solved, cases, self.task["holdout_truth"])
        self.assertEqual(passed, len(cases))

    def test_budget_cap_binds(self):
        capped = solve_task(self.task, self.adapter,
                            max_score_calls=1)
        self.assertIsInstance(capped, str)
        # One scoring call = only the start was scored;
        # nothing could be selected over it.
        self.assertEqual(capped, self.task["buggy_code"])

    def test_zero_cap_returns_start(self):
        out = solve_task(self.task, self.adapter,
                         max_score_calls=0)
        self.assertEqual(out, self.task["buggy_code"])


if __name__ == "__main__":
    unittest.main()
