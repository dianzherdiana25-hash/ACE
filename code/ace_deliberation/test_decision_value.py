"""Verifier titik impas dan sensitivitas payoff terhadap peluang."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import decision_value as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def action(identifier, yes, no, cost):
    return {"id": identifier, "utility_yes": yes, "utility_no": no, "fixed_cost": cost,
            "source_ref": f"fixture/payoff/{identifier}"}


def fixture():
    return {
        "decision_id": "design", "utility_unit": "poin-uji", "baseline": "keep",
        "forecast": {"ref": "fixture/p/1", "point": q(3, 5), "lower": q(1, 5), "upper": q(4, 5)},
        "options": [action("keep", 2, 2, 0), action("adopt", 10, -2, 2)],
    }


def option(report, identifier):
    return next(row for row in report["options"] if row["id"] == identifier)


class ValueTests(unittest.TestCase):
    def test_expected_value_and_gain_use_fixed_cost_once(self):
        report = model.analyze(fixture())
        adopt = option(report, "adopt")
        self.assertEqual(adopt["expected_at_point"], q(16, 5))
        self.assertEqual(adopt["gain_at_point"], q(6, 5))
        self.assertEqual(adopt["expected_range"], {"minimum": q(-8, 5), "maximum": q(28, 5)})
        self.assertEqual(adopt["gain_range"], {"minimum": q(-18, 5), "maximum": q(18, 5)})
        self.assertEqual(adopt["source_ref"], "fixture/payoff/adopt")
        self.assertEqual(report["forecast_ref"], "fixture/p/1")
        self.assertEqual(report["utility_unit"], "poin-uji")

    def test_break_even_matches_exact_root_and_is_in_range(self):
        report = model.analyze(fixture())
        self.assertEqual(report["break_even"], [
            {"first": "adopt", "second": "keep", "break_even": q(1, 2), "within_range": True},
        ])
        self.assertEqual(report["optimal_at_point"], ["adopt"])
        self.assertEqual(option(report, "adopt")["relation_to_baseline"], "switches")
        self.assertEqual(report["minimum_max_regret"], ["adopt", "keep"])

    def test_tie_policy_preserves_both_ids_at_break_even(self):
        raw = fixture()
        raw["forecast"]["point"] = q(1, 2)
        self.assertEqual(model.analyze(raw)["optimal_at_point"], ["adopt", "keep"])

    def test_optimal_at_both_ends_implies_optimal_throughout(self):
        raw = fixture()
        raw["forecast"]["lower"] = q(3, 5)
        report = model.analyze(raw)
        self.assertTrue(option(report, "adopt")["optimal_throughout_interval"])
        self.assertFalse(option(report, "keep")["optimal_throughout_interval"])
        self.assertEqual(option(report, "adopt")["max_regret"], q(0))
        self.assertEqual(option(report, "adopt")["relation_to_baseline"], "dominates")
        self.assertFalse(report["break_even"][0]["within_range"])

    def test_at_boundary_equal_but_lower_everywhere_else(self):
        raw = fixture()
        raw["forecast"].update(point=q(1, 4), upper=q(1, 2))
        report = model.analyze(raw)
        self.assertEqual(option(report, "adopt")["relation_to_baseline"], "dominated")
        self.assertEqual(report["optimal_at_point"], ["keep"])

    def test_descending_utility_reverses_the_extrema(self):
        raw = fixture()
        raw["options"][1] = action("adopt", -8, 12, 2)
        adopt = option(model.analyze(raw), "adopt")
        self.assertEqual(adopt["expected_range"], {"minimum": q(-6), "maximum": q(6)})
        self.assertEqual(adopt["expected_at_point"], q(-2))

    def test_parallel_equal_options_and_outside_probability_roots(self):
        raw = fixture()
        raw["options"] += [action("same", 2, 2, 0), action("never", -10, -8, 2)]
        report = model.analyze(raw)
        self.assertEqual(option(report, "same")["relation_to_baseline"], "equal")
        self.assertEqual(option(report, "never")["relation_to_baseline"], "dominated")
        self.assertFalse(any(row["first"] == "never" or row["second"] == "never" for row in report["break_even"]))
        self.assertFalse(any(row["first"] == "keep" and row["second"] == "same" for row in report["break_even"]))

    def test_regret_considers_every_alternative_and_both_endpoints(self):
        raw = fixture()
        raw["options"].append(action("inverse", -5, 7, 0))
        report = model.analyze(raw)
        self.assertEqual(option(report, "adopt")["max_regret"], q(31, 5))
        self.assertEqual(option(report, "keep")["max_regret"], q(18, 5))
        options = [model.Action.read(row, set()) for row in raw["options"]]
        for actual in options:
            theoretical = max(max(candidate.expected(Fraction(index, 100))
                                  - actual.expected(Fraction(index, 100)) for candidate in options)
                              for index in range(20, 81))
            self.assertEqual(Fraction(**option(report, actual.name)["max_regret"]), theoretical)

    def test_singleton_range_describes_nominal_scenario(self):
        raw = fixture()
        raw["forecast"].update(lower=q(3, 5), upper=q(3, 5))
        result = model.analyze(raw)
        self.assertEqual(result["optimal_at_point"], result["minimum_max_regret"])
        self.assertEqual(option(result, "adopt")["expected_range"], {"minimum": q(16, 5), "maximum": q(16, 5)})

    def test_source_and_valid_range_are_required(self):
        for forecast in (
            {"ref": "", "point": q(1, 2), "lower": q(0), "upper": q(1)},
            {"ref": "fixture/p", "point": q(1, 2), "lower": q(2, 3), "upper": q(1)},
            {"ref": "fixture/p", "point": q(1, 2), "lower": q(0), "upper": q(4, 3)},
        ):
            with self.subTest(forecast=forecast), self.assertRaises(model.InputError):
                model.analyze({**fixture(), "forecast": forecast})

    def test_baseline_and_option_values_must_be_declared_and_unique(self):
        raw = fixture()
        for changed in (
            {**raw, "baseline": "ghost"},
            {**raw, "options": [raw["options"][0]] * 2},
            {**raw, "options": [raw["options"][0], action("bad", 0, -2, -4)]},
            {**raw, "options": [raw["options"][0], action("bad", True, 0, 0)]},
            {**raw, "utility_unit": ""},
        ):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                model.analyze(changed)

    def test_cli_reproduces_report_with_permuted_options(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "case.json"
        raw = fixture()
        reports = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            reports.append(output.getvalue())
            raw["options"].reverse()
        self.assertEqual(reports[0], reports[1])

    def test_zero_and_one_probability_agree_with_realized_payoffs(self):
        raw = fixture()
        for chance, expected in ((q(0), q(-4)), (q(1), q(8))):
            with self.subTest(chance=chance):
                raw["forecast"] = {"ref": "fixture/p", "point": chance, "lower": chance, "upper": chance}
                report = model.analyze(raw)
                self.assertEqual(option(report, "adopt")["expected_at_point"], expected)

    def test_report_verifies_break_even_with_negative_slope(self):
        raw = fixture()
        raw["options"][1] = action("adopt", -6, 7, 1)
        report = model.analyze(raw)
        self.assertEqual(report["break_even"][0]["break_even"], q(4, 13))
        self.assertEqual(report["optimal_at_point"], ["keep"])

    def test_exact_zero_slope_remains_constant_over_full_range(self):
        raw = fixture()
        raw["options"][1] = action("adopt", 10, 10, 9)
        report = model.analyze(raw)
        self.assertEqual(option(report, "adopt")["expected_range"], {"minimum": q(1), "maximum": q(1)})
        self.assertEqual(report["break_even"], [])
        self.assertEqual(report["optimal_at_point"], ["keep"])

    def test_pairwise_break_even_includes_two_nonbaseline_options(self):
        raw = fixture()
        raw["options"].append(action("third", -4, 8, 0))
        report = model.analyze(raw)
        crossing = next(row for row in report["break_even"] if (row["first"], row["second"]) == ("adopt", "third"))
        self.assertEqual(crossing["break_even"], q(1, 2))
        self.assertTrue(crossing["within_range"])
