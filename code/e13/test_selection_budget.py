import unittest
from dataclasses import replace
from unittest.mock import patch

from .evaluator.bank import development_bank
from .evaluator.selection_budget import CPU_US, FIT_STEPS, TOTAL_STEPS, evaluate_arm
from .isolation import fit_isolated


class SelectionBudgetTests(unittest.TestCase):
    def test_fit_and_predict_share_caps_with_identical_fit_request(self):
        episode = development_bank()[0][0]
        rows = [evaluate_arm(episode, policy) for policy in ("structured", "enumerative", "beam")]
        for row in rows:
            self.assertLessEqual(row["fit_steps"], FIT_STEPS)
            self.assertLessEqual(row["fit_steps"] + row["predict_steps"], TOTAL_STEPS)
            self.assertLessEqual(row["total_cpu_us"], CPU_US)
            self.assertEqual(sum(score["total"] for score in row["scores"].values()), 12)

    def test_no_predictions_are_credited_if_cpu_budget_is_spent_during_fit(self):
        episode = development_bank()[0][0]
        fit = fit_isolated(episode.fit_request, policy="structured")
        used = replace(fit, metrics=replace(fit.metrics, cpu_us=CPU_US))
        with patch("e13.evaluator.selection_budget.fit_isolated", return_value=used):
            row = evaluate_arm(episode, "structured")
        self.assertTrue(row["cap_reached"])
        self.assertEqual(row["predict_steps"], 0)
        self.assertEqual(sum(score["failures"] for score in row["scores"].values()), 12)
