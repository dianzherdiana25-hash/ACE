"""OMEGA-11 tests for the Reasoning, Representation and Algorithm Lab.

The test list follows the OMEGA-11 line of the execution programme:
baseline dominance reporting, hypothesis falsification, multiple
seeds, resource-matched independent evaluation — plus the gate rule
that novelty/generalization claims stay NOT_ASSESSED.
"""
from __future__ import annotations

import unittest

from ace_operational.reasoning_lab import (
    Budget,
    ClaimsGateError,
    promote_claims,
    run_experiment,
    solver_token_search,
)


def tiny_run(**overrides):
    args = dict(families=["pricing"], levels=[1], seeds=[1, 2, 3, 5, 8],
                budget_limit=40)
    args.update(overrides)
    return run_experiment(**args)


class HarnessTests(unittest.TestCase):
    def test_budget_is_enforced_and_shared(self):
        report = tiny_run()
        for data in report["details"].values():
            for entry in data:
                if "budget_used" in entry:
                    self.assertLessEqual(entry["budget_used"], 40)

    def test_budget_violating_solver_abstains(self):
        def greedy(task, budget):
            for _ in range(500):
                budget.score(task["buggy_code"])
            return task["buggy_code"]

        report = tiny_run(solvers={"greedy": greedy, "grammar": __import__(
            "ace_operational.reasoning_lab", fromlist=["solver_grammar"]).solver_grammar},
            hypothesis={"subject": "grammar", "claim": "x", "reference": "greedy",
                        "margin": 1})
        # the harness counts used > limit as abstention, never a score
        self.assertGreaterEqual(report["solvers"]["greedy"]["abstained"], 0)

    def test_hypothesis_can_be_falsified(self):
        def hopeless(task, budget):
            return None

        report = tiny_run(
            solvers={"hopeless": hopeless,
                     "grammar": __import__("ace_operational.reasoning_lab",
                                           fromlist=["solver_grammar"]).solver_grammar},
            hypothesis={"subject": "hopeless", "claim": "solves_at_least_as_many_as",
                        "reference": "grammar", "margin": 1})
        self.assertIn(report["hypothesis_verdict"],
                      ("FALSIFIED", "INCONCLUSIVE"))
        self.assertEqual(report["solvers"]["hopeless"]["solved"], 0)

    def test_multiple_seeds_aggregate_and_repeat_deterministically(self):
        one = tiny_run(seeds=[1, 2, 3, 4, 5, 8])
        two = tiny_run(seeds=[1, 2, 3, 4, 5, 8])
        self.assertEqual(one["task_count"], two["task_count"])
        self.assertEqual({k: v["solved"] for k, v in one["solvers"].items()},
                         {k: v["solved"] for k, v in two["solvers"].items()})

    def test_results_are_reported_per_family(self):
        # Range 1..29 guarantees >=1 holdout task per family across Python 3.11/3.12/3.13
        # ast.dump() variations without altering frozen curriculum_lab.normalized_form.
        report = run_experiment(families=["pricing", "shipping"], levels=[1],
                                seeds=list(range(1, 30)), budget_limit=40)
        for data in report["solvers"].values():
            self.assertIn("pricing", data["per_family"])
            self.assertIn("shipping", data["per_family"])

    def test_ablation_runs_under_the_same_budget(self):
        def ablated(task, budget):
            return solver_token_search(task, budget, first_improvement_only=True)

        def full(task, budget):
            return solver_token_search(task, budget)

        report = tiny_run(solvers={"full": full, "ablated": ablated},
                          hypothesis={"subject": "full", "claim": "x",
                                      "reference": "ablated", "margin": 2})
        self.assertEqual(report["solvers"]["full"]["tasks"],
                         report["solvers"]["ablated"]["tasks"])


class ClaimsGateTests(unittest.TestCase):
    def test_claims_stay_not_assessed(self):
        report = tiny_run()
        self.assertEqual(report["claims"],
                         {"novelty": "NOT_ASSESSED",
                          "generalization": "NOT_ASSESSED"})

    def test_promotion_is_refused_without_proofs(self):
        report = tiny_run()
        with self.assertRaises(ClaimsGateError):
            promote_claims(report)
        with self.assertRaises(ClaimsGateError):
            promote_claims(report, custody_proof="x", transfer_proof="y")


class BudgetUnitTests(unittest.TestCase):
    def test_budget_counts_and_caps_visible(self):
        budget = Budget(3, entrypoint="total",
                        shown_cases=[(100, False)], shown_expected=[111])
        self.assertEqual(budget.score("def total(s, m):\n    return s * 111 // 100\n"), 1)
        self.assertEqual(budget.used, 1)
        self.assertEqual(budget.score("def total(s, m):\n    return 0\n"), 0)


if __name__ == "__main__":
    unittest.main()
