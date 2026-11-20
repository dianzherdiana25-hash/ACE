"""Uji independensi kelompok, kontrol waktu, dan transformasi log-odds."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import brier_scorer, forecast_aggregator as aggregation
from ace_deliberation.test_brier_scorer import fixture as brier_fixture


def prediction(index, p, group, weight=1):
    return {"id": f"source{index}", "question_id": "test1", "probability": p,
            "forecast_at": "2026-11-20T00:00:00Z", "forecast_ref": f"fixture/forecast/{index}",
            "family": group, "weight": weight}


def fixture():
    return {
        "question_id": "test1", "as_of": "2026-11-20T02:00:00Z", "output_ref": "fixture/aggregate",
        "baseline": {"probability": "0.5", "source_ref": "fixture/base", "known_at": "2026-11-19T00:00:00Z"},
        "extremity": 1, "minimum_families": 2,
        "forecasts": [prediction(1, "0.9", "x", 3), prediction(2, "0.7", "x"), prediction(3, "0.5", "y")],
    }


class AggregationTests(unittest.TestCase):
    def test_weighted_inside_family_and_equal_across_families(self):
        result = aggregation.aggregate(fixture())
        self.assertEqual(result["groups"][0]["weighted_mean"], {"numerator": 17, "denominator": 20})
        self.assertEqual(result["forecast"]["probability"], "0.675")
        self.assertEqual(result["family_count"], 2)
        self.assertEqual(result["groups"][0]["inputs"][1]["source_ref"], "fixture/forecast/2")

    def test_extremizing_matches_exact_case_from_odds_four_squared(self):
        raw = {**fixture(), "extremity": 2, "forecasts": [prediction(1, "0.8", "x"), prediction(2, "0.8", "y")]}
        report = aggregation.aggregate(raw)
        self.assertEqual(report["raw_mean"], {"numerator": 4, "denominator": 5})
        self.assertEqual(report["forecast"]["probability"], "0.941176470588235294")

    def test_baseline_moves_pivot_and_preserves_neutral_forecast_at_prior(self):
        raw = fixture()
        raw["baseline"]["probability"] = "0.2"
        raw["extremity"] = 4
        raw["forecasts"] = [prediction(1, "0.2", "x"), prediction(2, "0.2", "y")]
        self.assertEqual(aggregation.aggregate(raw)["forecast"]["probability"], "0.2")
        raw["forecasts"] = [prediction(1, "0.4", "x"), prediction(2, "0.4", "y")]
        self.assertGreater(aggregation.aggregate(raw)["forecast"]["probability"], "0.4")

    def test_family_quorum_writes_no_forecast_for_same_family_duplicates(self):
        raw = fixture()
        raw["forecasts"][-1]["family"] = "x"
        result = aggregation.aggregate(raw)
        self.assertEqual(result["status"], "insufficient_families")
        self.assertIsNone(result["forecast"])
        self.assertIsNone(result["raw_mean"])

    def test_reject_forecasts_from_future_other_question_or_ref_duplication(self):
        for update in ({"forecast_at": "2026-11-20T03:00:00Z"}, {"question_id": "wrong"},
                       {"forecast_ref": "fixture/forecast/1"}, {"weight": False}):
            raw = fixture()
            raw["forecasts"][1].update(update)
            with self.subTest(update=update), self.assertRaises(aggregation.AggregateError):
                aggregation.aggregate(raw)

    def test_exact_endpoints_preserved_and_brier_accepts_output(self):
        raw = {**fixture(), "extremity": 4, "forecasts": [prediction(1, 1, "x"), prediction(2, 1, "y")]}
        report = aggregation.aggregate(raw)
        self.assertEqual(report["forecast"]["probability"], "1")
        scoring = brier_fixture()
        scoring["forecasts"][0] = report["forecast"]
        self.assertEqual(brier_scorer.score_brier(scoring)["questions"][0]["brier"],
                         {"numerator": 1, "denominator": 1})

    def test_cli_reproduces_bytes_after_input_reordering(self):
        raw = fixture()
        expected = aggregation.aggregate(raw)
        raw["forecasts"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "forecasts.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(aggregation.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_leave_family_out_preserves_quorum_gate(self):
        report = aggregation.aggregate(fixture())
        self.assertEqual(report["family_spread"], {"numerator": 7, "denominator": 20})
        self.assertEqual(report["leave_one_family_out"], [
            {"family_removed": family, "status": "insufficient_families", "probability": None, "raw_change": None}
            for family in ("x", "y")
        ])

    def test_one_family_removal_reaggregates_the_remaining_means(self):
        raw = {**fixture(), "minimum_families": 1}
        records = aggregation.aggregate(raw)["leave_one_family_out"]
        self.assertEqual(records, [
            {"family_removed": "x", "status": "aggregated", "probability": "0.5",
             "raw_change": {"numerator": -7, "denominator": 40}},
            {"family_removed": "y", "status": "aggregated", "probability": "0.85",
             "raw_change": {"numerator": 7, "denominator": 40}},
        ])

    def test_one_live_family_with_zero_remaining_families_has_no_alternate(self):
        raw = {**fixture(), "minimum_families": 1, "forecasts": [prediction(1, "0.4", "x")]}
        report = aggregation.aggregate(raw)
        self.assertEqual(report["forecast"]["probability"], "0.4")
        self.assertIsNone(report["leave_one_family_out"][0]["probability"])

    def test_lower_side_of_base_rate_is_extremized_away_from_it(self):
        raw = {**fixture(), "extremity": 2, "forecasts": [prediction(1, "0.2", "x"), prediction(2, "0.2", "y")]}
        self.assertEqual(aggregation.aggregate(raw)["forecast"]["probability"], "0.058823529411764706")

    def test_extremity_bounds_and_duplicate_output_reference_are_refused(self):
        for changes in ({"extremity": "0.9"}, {"extremity": 5}, {"output_ref": "fixture/forecast/1"}):
            with self.subTest(changes=changes), self.assertRaises(aggregation.AggregateError):
                aggregation.aggregate({**fixture(), **changes})

    def test_participation_weight_never_changes_the_groups_outside_its_own_family(self):
        raw = fixture()
        baseline = aggregation.aggregate(raw)
        raw["forecasts"][0]["weight"] = 10_000
        result = aggregation.aggregate(raw)
        self.assertEqual(result["groups"][1], baseline["groups"][1])
        self.assertEqual(result["family_count"], baseline["family_count"])

    def test_process_decimal_context_cannot_change_forecast(self):
        from decimal import ROUND_UP, localcontext

        raw = {**fixture(), "extremity": "2.3"}
        expected = aggregation.aggregate(raw)
        with localcontext() as context:
            context.prec = 1
            context.rounding = ROUND_UP
            self.assertEqual(aggregation.aggregate(raw), expected)

    def test_no_inputs_reports_empty_coverage_without_synthesizing_probability(self):
        report = aggregation.aggregate({**fixture(), "forecasts": []})
        self.assertEqual((report["family_count"], report["groups"]), (0, []))
        self.assertIsNone(report["forecast"])
