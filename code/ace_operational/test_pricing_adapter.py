"""P2 smoke tests: the pricing adapter serves the
discovery core end-to-end. These are machinery tests, not
measurements — the G3 application's numbers come from its
own preregistered run."""
import unittest

from ace_operational.operator_discovery import run_discovery
from ace_operational.pricing_adapter import PRICING_ADAPTER, \
    build_pricing_task


class TestPricingAdapter(unittest.TestCase):

    def test_task_contract(self):
        task = build_pricing_task(seed=101, level=1)
        for key in ("buggy_code", "shown_cases", "shown_truth",
                    "holdout_cases", "holdout_truth", "defects",
                    "task_id"):
            self.assertIn(key, task)
        self.assertEqual(len(task["shown_cases"]),
                         len(task["shown_truth"]))
        self.assertEqual(len(task["holdout_cases"]),
                         len(task["holdout_truth"]))
        self.assertTrue(task["defects"])
        self.assertTrue(
            set(task["defects"]) <= {"threshold_boundary",
                                      "tax_basis", "member_basis"})
        shown = {tuple(c) for c in task["shown_cases"]}
        holdout = {tuple(c) for c in task["holdout_cases"]}
        self.assertFalse(shown & holdout)

    def test_budget_scores_reference_full_and_buggy_less(self):
        task = build_pricing_task(seed=7, level=1)
        budget = PRICING_ADAPTER.make_budget(task)
        self.assertEqual(budget.score(task["reference_code"]),
                         len(task["shown_cases"]))
        self.assertLess(budget.score(task["buggy_code"]),
                        len(task["shown_cases"]))

    def test_passes_counts_holdout(self):
        task = build_pricing_task(seed=7, level=1)
        cases = [tuple(c) for c in task["holdout_cases"]]
        self.assertEqual(
            PRICING_ADAPTER.passes(task["reference_code"], cases,
                                   task["holdout_truth"]),
            len(cases))
        self.assertLess(
            PRICING_ADAPTER.passes(task["buggy_code"], cases,
                                   task["holdout_truth"]),
            len(cases))

    def test_discovery_smoke_on_pricing_pool(self):
        pool = [build_pricing_task(seed=s, level=1)
                for s in (201, 202, 203, 204, 205, 206)]
        evaluation = [build_pricing_task(seed=s, level=1)
                      for s in (301, 302, 303, 304)]
        report = run_discovery(pool=pool, evaluation=evaluation,
                               control=[],
                               adapter=PRICING_ADAPTER)
        self.assertIn("by_class", report)
        self.assertTrue(report["by_class"])
        for entry in report["by_class"].values():
            self.assertGreaterEqual(entry["eval_solved_extended"],
                                    entry["eval_solved_baseline"])


if __name__ == "__main__":
    unittest.main()
