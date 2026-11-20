"""Verifier delta berpasangan, biaya, rasio, dan sampel per kelas."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import deliberation_roi as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def obs(ref, score, ms, credits):
    return {"score": score, "elapsed_ms": ms, "credits": credits,
            "judgement_ref": f"fixture/score/{ref}", "resource_ref": f"fixture/resource/{ref}"}


def case(key, kind, first, second):
    return {"case_id": key, "class": kind, "case_ref": f"fixture/cases/{key}",
            "baseline": obs(f"{key}/single", *first) if first is not None else None,
            "deliberation": obs(f"{key}/panel", *second) if second is not None else None}


def fixture():
    return {
        "protocol_ref": "fixture/protocol", "analysis_unit": "unit-evaluasi", "minimum_pairs": 2,
        "policies": [
            {"class": "design", "ref": "fixture/policies/design", "value_per_point": 6,
             "cost_per_ms": 2, "cost_per_credit": 3},
            {"class": "repair", "ref": "fixture/policies/repair", "value_per_point": 2,
             "cost_per_ms": 1, "cost_per_credit": 1},
            {"class": "review", "ref": "fixture/policies/review", "value_per_point": 1,
             "cost_per_ms": 0, "cost_per_credit": 1},
        ],
        "cases": [
            case("alpha", "design", (70, 10, 3), (80, 15, 5)),
            case("beta", "design", (90, 16, 7), (84, 14, 6)),
            case("gamma", "design", (70, 16, 3), None),
            case("repair", "repair", (50, 10, 1), (51, 10, 1)),
        ],
    }


class RoiTests(unittest.TestCase):
    def test_paired_class_deltas_and_economic_units_agree_with_manual_total(self):
        result = model.measure(fixture())
        design = result["classes"][0]
        self.assertEqual(result["analysis_unit"], "unit-evaluasi")
        self.assertEqual(design["policy"]["ref"], "fixture/policies/design")
        self.assertEqual(design["pairs"], 2)
        self.assertEqual(design["incomplete"], 1)
        self.assertEqual(design["cases"][0]["delta"], {
            "quality_points": 10, "elapsed_ms": 5, "credits": 2, "gross_value": 60,
            "added_cost": 16, "net_value": 44,
        })
        self.assertEqual(design["totals"], {
            "quality_points": 4, "elapsed_ms": 3, "credits": 1, "gross_value": 24,
            "added_cost": 9, "net_value": 15,
        })
        self.assertEqual(design["roi"], q(5, 3))
        self.assertEqual(design["net_per_case"], q(15, 2))
        self.assertEqual(design["break_even_value_per_point"], q(9, 4))
        self.assertEqual(design["paired_net_signs"], {"positive": 1, "zero": 0, "negative": 1})

    def test_negative_case_and_missing_pair_keep_provenance(self):
        design = model.measure(fixture())["classes"][0]
        negative, missing = design["cases"][1:]
        self.assertEqual(negative["delta"]["net_value"], -29)
        self.assertEqual(negative["observations"]["deliberation"]["judgement_ref"], "fixture/score/beta/panel")
        self.assertEqual(missing["missing"], ["deliberation"])
        self.assertIsNone(missing["delta"])
        self.assertIsNone(missing["observations"]["deliberation"])
        self.assertEqual(missing["observations"]["baseline"]["resource_ref"], "fixture/resource/gamma/single")

    def test_no_pairs_and_insufficient_pairs_are_distinct(self):
        _, repair, review = model.measure(fixture())["classes"]
        self.assertEqual(repair["status"], "insufficient_pairs")
        self.assertEqual(repair["totals"]["net_value"], 2)
        self.assertIsNone(repair["net_per_case"])
        self.assertEqual(review["status"], "no_pairs")
        self.assertIsNone(review["totals"])
        self.assertEqual(review["pairs"], 0)
        self.assertEqual(review["paired_net_signs"], {"positive": 0, "zero": 0, "negative": 0})

    def test_zero_added_cost_with_improved_quality_has_no_roi_ratio(self):
        repair = model.measure({**fixture(), "minimum_pairs": 1})["classes"][1]
        self.assertEqual(repair["status"], "measured")
        self.assertIsNone(repair["roi"])
        self.assertEqual(repair["break_even_value_per_point"], q(0))
        self.assertEqual(repair["net_per_case"], q(2))

    def test_cost_savings_value_and_break_even_when_quality_drops(self):
        raw = {**fixture(), "minimum_pairs": 1, "cases": [case("only", "repair", (70, 10, 5), (69, 4, 2))]}
        repair = model.measure(raw)["classes"][1]
        self.assertEqual(repair["totals"]["added_cost"], -9)
        self.assertEqual(repair["totals"]["net_value"], 7)
        self.assertIsNone(repair["roi"])
        self.assertIsNone(repair["break_even_value_per_point"])

    def test_negative_roi_is_reported_when_quality_cannot_justify_added_cost(self):
        raw = {**fixture(), "minimum_pairs": 1, "cases": [case("one", "repair", (70, 10, 5), (70, 15, 5))]}
        repair = model.measure(raw)["classes"][1]
        self.assertEqual(repair["roi"], q(-1))
        self.assertEqual(repair["net_per_case"], q(-5))
        self.assertIsNone(repair["break_even_value_per_point"])

    def test_identical_outcomes_and_budget_use_explicit_zero(self):
        raw = {**fixture(), "minimum_pairs": 1, "cases": [case("one", "repair", (0, 0, 0), (0, 0, 0))]}
        repair = model.measure(raw)["classes"][1]
        self.assertEqual(repair["paired_net_signs"]["zero"], 1)
        self.assertEqual(repair["net_per_case"], q(0))
        self.assertEqual(repair["totals"]["quality_points"], 0)

    def test_case_with_both_arms_missing_has_two_absences_and_no_pair(self):
        raw = {**fixture(), "cases": [case("only", "repair", None, None)]}
        repair = model.measure(raw)["classes"][1]
        self.assertEqual(repair["cases"][0]["missing"], ["baseline", "deliberation"])
        self.assertEqual(repair["incomplete"], 1)
        self.assertEqual(repair["status"], "no_pairs")

    def test_unknown_class_or_duplicate_cases_not_counted(self):
        raw = fixture()
        for case_rows in ([case("only", "unknown", (0, 0, 0), None)], [raw["cases"][0]] * 2):
            with self.subTest(case_rows=case_rows), self.assertRaises(model.InputError):
                model.measure({**raw, "cases": case_rows})

    def test_score_resource_and_policy_bounds_do_not_coerce_invalid_numbers(self):
        raw = fixture()
        for update in ({"score": 101}, {"elapsed_ms": -1}, {"credits": True}):
            with self.subTest(update=update):
                raw = fixture()
                raw["cases"][0]["baseline"].update(update)
                with self.assertRaises(model.InputError):
                    model.measure(raw)
        raw = fixture()
        raw["policies"][0]["cost_per_ms"] = -2
        with self.assertRaises(model.InputError):
            model.measure(raw)

    def test_reusing_assessment_or_measurement_ref_across_arms_is_refused(self):
        raw = fixture()
        observation = raw["cases"][0]["baseline"]
        raw["cases"][0]["deliberation"]["judgement_ref"] = observation["judgement_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            model.measure(raw)

    def test_cli_output_is_identical_when_case_and_policy_inputs_are_reordered(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "roi.json"
        logs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            logs.append(output.getvalue())
            raw["cases"].reverse()
            raw["policies"].reverse()
        self.assertEqual(logs[0], logs[1])

    def test_policies_do_not_pool_unrelated_classes_even_when_names_are_similar(self):
        report = model.measure(fixture())
        self.assertEqual([row["class"] for row in report["classes"]], ["design", "repair", "review"])
        self.assertEqual(sum(row["pairs"] for row in report["classes"]), 3)
        self.assertTrue(all(case["case_id"] != "repair" for case in report["classes"][0]["cases"]))
