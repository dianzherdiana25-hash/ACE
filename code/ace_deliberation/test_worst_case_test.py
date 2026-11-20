"""Periksa beda payoff terburuk, expected utility, dan regret."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import worst_case_test as worst


def scenario(identifier, n, d, stress=False):
    return {"id": identifier, "source_ref": f"fixture/scenario/{identifier}",
            "probability": {"numerator": n, "denominator": d}, "stress": stress}


def option(identifier, **utilities):
    return {"id": identifier, "source_ref": f"fixture/option/{identifier}",
            "payoffs": {name: {"utility": value, "source_ref": f"fixture/{identifier}/{name}"}
                        for name, value in utilities.items()}}


def fixture():
    return {"candidate": "bold", "minimum_stress_utility": -5,
            "scenarios": [scenario("normal", 3, 4), scenario("soft", 1, 4),
                          scenario("extreme", 0, 1, True), scenario("out", 0, 1)],
            "options": [option("bold", normal=20, soft=8, extreme=-20, out=-100),
                        option("safe", normal=8, soft=8, extreme=-5, out=0),
                        option("dominated", normal=2, soft=7, extreme=-6, out=999)]}


class StressTests(unittest.TestCase):
    def test_zero_probability_stress_changes_floor_with_unchanged_expectation(self):
        report = worst.stress_test(fixture())
        bold = report["options"][0]
        self.assertEqual(report["status"], "breaches_stress_floor")
        self.assertEqual(bold["expected_utility"], {"numerator": 17, "denominator": 1})
        self.assertEqual(bold["worst_utility"], -20)
        self.assertEqual(bold["worst_scenarios"][0]["payoff_ref"], "fixture/bold/extreme")
        self.assertEqual(report["excluded_zero_probability_nonstress"], ["out"])

    def test_maximin_and_regret_have_explicit_values(self):
        report = worst.stress_test(fixture())
        self.assertEqual(report["maximin_choices"], ["safe"])
        self.assertEqual(report["minimax_regret_choices"], ["safe"])
        options = {row["id"]: row for row in report["options"]}
        self.assertEqual(options["bold"]["max_regret"], 15)
        self.assertEqual(options["safe"]["max_regret"], 12)
        self.assertEqual(options["safe"]["max_regret_scenarios"][0]["scenario"], "normal")
        self.assertEqual(options["dominated"]["dominated_by"], ["safe"])

    def test_stress_floor_includes_exact_equality(self):
        raw = {**fixture(), "candidate": "safe"}
        self.assertEqual(worst.stress_test(raw)["status"], "meets_stress_floor")
        raw["minimum_stress_utility"] += 1
        self.assertEqual(worst.stress_test(raw)["status"], "breaches_stress_floor")

    def test_ties_do_not_produce_arbitrary_winner(self):
        raw = fixture()
        raw["options"].append(option("tie", normal=8, soft=8, extreme=-5, out=-1000))
        report = worst.stress_test(raw)
        self.assertEqual(report["maximin_choices"], ["safe", "tie"])
        self.assertEqual(report["minimax_regret_choices"], ["safe", "tie"])

    def test_fails_when_distribution_or_payoff_matrix_is_incomplete(self):
        raw = fixture()
        raw["scenarios"][0]["probability"]["numerator"] = 2
        with self.assertRaises(worst.StressError):
            worst.stress_test(raw)
        raw = fixture()
        del raw["options"][0]["payoffs"]["normal"]
        with self.assertRaises(worst.StressError):
            worst.stress_test(raw)

    def test_cli_keeps_candidate_status_and_order_invariant(self):
        raw = fixture()
        expected = worst.stress_test(raw)
        raw["options"].reverse()
        raw["scenarios"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "stress.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(worst.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_exhaustive_two_by_two_utility_matrix_preserves_exact_oracles(self):
        from fractions import Fraction
        from itertools import product

        scenarios = [scenario("a", 1, 4), scenario("b", 3, 4)]
        for x1, x2, y1, y2 in product((-1, 0, 1), repeat=4):
            raw = {"candidate": "x", "minimum_stress_utility": 0, "scenarios": scenarios,
                   "options": [option("x", a=x1, b=x2), option("y", a=y1, b=y2)]}
            report = worst.stress_test(raw)
            by_id = {row["id"]: row for row in report["options"]}
            expected = Fraction(x1, 4) + Fraction(3 * x2, 4)
            with self.subTest(x=(x1, x2), y=(y1, y2)):
                self.assertEqual(Fraction(**by_id["x"]["expected_utility"]), expected)
                self.assertEqual(by_id["x"]["worst_utility"], min(x1, x2))
                self.assertEqual(by_id["x"]["max_regret"], max(0, y1 - x1, y2 - x2))
                self.assertEqual(by_id["x"]["dominated_by"],
                                 ["y"] if x1 <= y1 and x2 <= y2 and (x1, x2) != (y1, y2) else [])
                self.assertEqual("x" in report["maximin_choices"], min(x1, x2) >= min(y1, y2))

    def test_positive_mass_enters_stress_analysis_even_without_manual_marker(self):
        raw = fixture()
        raw["scenarios"][0]["probability"] = {"numerator": 1, "denominator": 2}
        raw["scenarios"][3]["probability"] = {"numerator": 1, "denominator": 4}
        report = worst.stress_test(raw)
        self.assertIn("out", report["considered"])
        self.assertEqual(report["options"][0]["worst_utility"], -100)

    def test_multiple_worst_paths_preserve_all_source_refs_when_tied(self):
        raw = fixture()
        raw["options"][0]["payoffs"]["soft"]["utility"] = -20
        report = worst.stress_test(raw)
        self.assertEqual([row["scenario_ref"] for row in report["options"][0]["worst_scenarios"]],
                         ["fixture/scenario/extreme", "fixture/scenario/soft"])

    def test_boolean_utility_and_inconsistent_refs_cannot_supply_optimistic_record(self):
        for edits in ({"utility": True}, {"source_ref": "fixture/scenario/normal"}):
            raw = fixture()
            raw["options"][0]["payoffs"]["normal"].update(edits)
            with self.subTest(edits=edits), self.assertRaises(worst.StressError):
                worst.stress_test(raw)

    def test_unknown_candidate_cannot_be_converted_to_safest_choice(self):
        with self.assertRaisesRegex(worst.StressError, "Putusan"):
            worst.stress_test({**fixture(), "candidate": "unknown"})

    def test_expected_regret_witness_does_not_include_zero_mass_unmarked_path(self):
        bold = worst.stress_test(fixture())["options"][0]
        self.assertTrue(all(row["scenario"] != "out" for row in bold["max_regret_scenarios"]))
        self.assertEqual(bold["max_regret_scenarios"][0]["scenario"], "extreme")

    def test_negative_and_zero_scenarios_reject_integer_coercion_and_require_markers(self):
        raw = fixture()
        raw["scenarios"][2]["stress"] = 1
        with self.assertRaises(worst.StressError):
            worst.stress_test(raw)
        raw = fixture()
        raw["scenarios"][0]["probability"]["numerator"] = -1
        with self.assertRaises(worst.StressError):
            worst.stress_test(raw)
