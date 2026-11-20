"""Uji posterior, biaya, nilai sempurna, dan alasan berhenti."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import voi_limiter


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def experiment(identifier, accuracy, cost):
    miss = q(accuracy["denominator"] - accuracy["numerator"], accuracy["denominator"])
    return {"id": identifier, "source_ref": f"fixture/{identifier}", "cost": cost,
            "outcomes": {"A": {"a": accuracy, "b": miss}, "B": {"a": miss, "b": accuracy}}}


def fixture():
    return {"prior": {"a": q(1, 2), "b": q(1, 2)},
            "utility": {"first": {"a": 10, "b": 0}, "second": {"a": 0, "b": 10}},
            "experiments": [experiment("perfect", q(1), 6), experiment("cheap", q(4, 5), 1)],
            "budget": 4, "min_net_value": 0}


class ValueTests(unittest.TestCase):
    def test_value_of_sample_information_and_perfect_bound(self):
        report = voi_limiter.compare(fixture())
        self.assertEqual(report["best_without_additional_information"], ["first", "second"])
        self.assertEqual(report["starting_expected_utility"], q(5))
        self.assertEqual(report["perfect_information_bound"], q(5))
        self.assertEqual(report["recommended_experiment"], "cheap")
        cheap, perfect = report["evaluated"]
        self.assertEqual((cheap["gross_voi"], cheap["net_voi"]), (q(3), q(2)))
        self.assertEqual(cheap["outcomes"][0]["posterior"], {"a": q(4, 5), "b": q(1, 5)})
        self.assertEqual(cheap["outcomes"][0]["best_actions"], ["first"])
        self.assertFalse(perfect["feasible"])

    def test_threshold_equality_stops_and_does_not_force_a_test(self):
        raw = {**fixture(), "min_net_value": 2}
        result = voi_limiter.compare(raw)
        self.assertEqual(result["status"], "stop")
        self.assertIsNone(result["recommended_experiment"])

    def test_zero_probability_outcome_does_not_invent_posterior(self):
        raw = fixture()
        raw["experiments"] = [{"id": "constant", "source_ref": "fixture/constant", "cost": 0,
                              "outcomes": {"never": {"a": q(0), "b": q(0)},
                                           "always": {"a": q(1), "b": q(1)}}}]
        result = voi_limiter.compare(raw)["evaluated"][0]
        self.assertEqual(result["gross_voi"], q(0))
        self.assertIsNone(result["outcomes"][1]["posterior"])
        self.assertEqual(result["outcomes"][1]["best_actions"], [])

    def test_equal_value_and_cost_break_by_id_deterministically(self):
        raw = fixture()
        raw["experiments"] = [experiment("z", q(4, 5), 1), experiment("a", q(4, 5), 1)]
        self.assertEqual(voi_limiter.compare(raw)["recommended_experiment"], "a")
        self.assertEqual(voi_limiter.compare(raw), voi_limiter.compare({**raw, "experiments": raw["experiments"][::-1]}))

    def test_cost_alone_can_make_informative_option_net_negative(self):
        raw = {**fixture(), "budget": 10, "experiments": [experiment("useful", q(1), 8)]}
        report = voi_limiter.compare(raw)
        self.assertEqual(report["evaluated"][0]["net_voi"], q(-3))
        self.assertTrue(report["evaluated"][0]["feasible"])
        self.assertEqual(report["status"], "stop")

    def test_rejects_non_normalized_probabilities_and_malformed_utility(self):
        malformed = fixture()
        malformed["experiments"][1]["outcomes"]["A"]["a"] = q(1, 10)
        with self.assertRaisesRegex(voi_limiter.InformationError, "berjumlah 1"):
            voi_limiter.compare(malformed)
        malformed = fixture()
        del malformed["utility"]["first"]["a"]
        with self.assertRaises(voi_limiter.InformationError):
            voi_limiter.compare(malformed)

    def test_cli_matches_analysis(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "voi.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(voi_limiter.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), voi_limiter.compare(raw))

    def test_binary_test_sweep_agrees_with_independent_joint_utility_oracle(self):
        from fractions import Fraction

        for n in range(6):
            for correct in range(6):
                prior_a, accurate = Fraction(n, 5), Fraction(correct, 5)
                raw = {**fixture(), "prior": {"a": q(n, 5), "b": q(5 - n, 5)},
                       "experiments": [experiment("candidate", q(correct, 5), 0)]}
                report = voi_limiter.compare(raw)
                candidate, = report["evaluated"]
                oracle = 10 * (max(prior_a * accurate, (1 - prior_a) * (1 - accurate))
                               + max(prior_a * (1 - accurate), (1 - prior_a) * accurate))
                oracle -= 10 * max(prior_a, 1 - prior_a)
                with self.subTest(prior=n, accuracy=correct):
                    self.assertEqual(Fraction(**candidate["gross_voi"]), oracle)
                    self.assertLessEqual(oracle, Fraction(**report["perfect_information_bound"]))
                    self.assertGreaterEqual(oracle, 0)

    def test_prior_with_one_certain_state_gives_no_information_premium(self):
        raw = {**fixture(), "prior": {"a": q(1), "b": q(0)}}
        report = voi_limiter.compare(raw)
        self.assertEqual(report["perfect_information_bound"], q(0))
        self.assertEqual(report["best_without_additional_information"], ["first"])
        self.assertTrue(all(row["gross_voi"] == q(0) for row in report["evaluated"]))

    def test_decision_with_uniformly_dominating_option_gets_no_gain(self):
        raw = fixture()
        raw["utility"]["safe"] = {"a": 11, "b": 12}
        report = voi_limiter.compare(raw)
        self.assertEqual(report["status"], "stop")
        self.assertEqual(report["best_without_additional_information"], ["safe"])
        self.assertEqual(report["starting_expected_utility"], q(23, 2))
        self.assertEqual(report["perfect_information_bound"], q(0))

    def test_budget_zero_allows_zero_cost_information_of_positive_value(self):
        raw = {**fixture(), "budget": 0, "experiments": [experiment("free", q(3, 4), 0)]}
        report = voi_limiter.compare(raw)
        self.assertEqual(report["recommended_experiment"], "free")
        self.assertEqual(report["evaluated"][0]["net_voi"], q(5, 2))

    def test_negative_payoffs_do_not_turn_stop_into_a_forced_zero_result(self):
        raw = fixture()
        for actions in raw["utility"].values():
            for state in actions:
                actions[state] -= 20
        report = voi_limiter.compare(raw)
        self.assertEqual(report["starting_expected_utility"], q(-15))
        self.assertEqual(report["recommended_experiment"], "cheap")

    def test_duplicate_references_and_unavailable_experiments_fail_separately(self):
        raw = fixture()
        self.assertEqual(voi_limiter.compare({**raw, "experiments": []})["status"], "stop")
        addition = experiment("new", q(1, 2), 0)
        addition["source_ref"] = raw["experiments"][0]["source_ref"]
        with self.assertRaisesRegex(voi_limiter.InformationError, "ganda"):
            voi_limiter.compare({**raw, "experiments": [*raw["experiments"], addition]})
