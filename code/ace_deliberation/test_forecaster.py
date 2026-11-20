"""Verifikasi odds, sensitivitas skenario, dan batas waktu informasi."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import brier_scorer, forecaster
from ace_deliberation.test_brier_scorer import fixture as scoring_fixture


def evidence(identifier, low, actual, high):
    return {"id": identifier, "lower": low, "likelihood": actual, "upper": high,
            "known_at": "2026-11-19T00:00:00Z", "source_ref": f"fixture/evidence/{identifier}",
            "family": identifier}


def fixture():
    return {
        "question_id": "test1", "question": "Apakah indikator terlampaui?",
        "forecast_at": "2026-11-20T00:00:00Z", "resolve_by": "2026-11-21T00:00:00Z",
        "resolution_rule_ref": "fixture/definition", "forecast_ref": "fixture/forecast/test1",
        "assumption_ref": "fixture/independence",
        "prior": {"probability": "0.4", "source_ref": "fixture/prior", "known_at": "2026-11-18T00:00:00Z"},
        "evidence": [evidence("b", "0.4", "0.5", "0.6"), evidence("a", 2, 3, 4)],
    }


def rational(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator}


class ForecasterTests(unittest.TestCase):
    def test_two_sources_update_odds_and_bound_scenario(self):
        raw = fixture()
        result = forecaster.make_forecast(raw)
        self.assertEqual(result["probability_exact"], rational(1, 2))
        self.assertEqual(result["forecast"]["probability"], "0.5")
        self.assertEqual(result["scenario_range"], {"lower": rational(8, 23), "upper": rational(8, 13)})
        self.assertEqual(result["evidence_trace"][0]["posterior_after"], rational(2, 3))
        self.assertEqual(result["evidence_trace"][0]["source_ref"], "fixture/evidence/a")
        raw["evidence"].reverse()
        self.assertEqual(forecaster.make_forecast(raw), result)

    def test_empty_evidence_keeps_prior_explicit(self):
        result = forecaster.make_forecast({**fixture(), "evidence": []})
        self.assertEqual(result["probability_exact"], rational(2, 5))
        self.assertEqual(result["scenario_range"]["lower"], rational(2, 5))
        self.assertEqual(result["evidence_trace"], [])

    def test_source_family_duplicate_and_lookahead_are_rejected(self):
        for change in ({"family": "a"}, {"source_ref": "fixture/prior"},
                       {"known_at": "2026-11-20T01:00:00Z"}, {"likelihood": "0.9"},
                       {"lower": "0"}, {"likelihood": 0.5}, {"id": "a"}):
            with self.subTest(change=change), self.assertRaises(forecaster.ForecastError):
                raw = fixture()
                raw["evidence"][0].update(change)
                forecaster.make_forecast(raw)

    def test_requires_preresolution_stamp_and_inner_prior(self):
        for edits in ({"resolve_by": "2026-11-20T00:00:00Z"},
                      {"prior": {**fixture()["prior"], "probability": "1"}},
                      {"prior": {**fixture()["prior"], "known_at": "2026-11-20T00:00:01Z"}}):
            with self.subTest(edits=edits), self.assertRaises(forecaster.ForecastError):
                forecaster.make_forecast({**fixture(), **edits})

    def test_rounded_fraction_uses_half_even_and_valid_decimal_profile(self):
        for value, expected in ((Fraction(2, 3), "0.666666666666666667"),
                                (Fraction(1, 2 * 10**18), "0"),
                                (Fraction(3, 2 * 10**18), "0.000000000000000002")):
            with self.subTest(value=value):
                self.assertEqual(forecaster._display(value), expected)

    def test_forecast_output_feeds_brier_without_relabeling(self):
        payload = scoring_fixture()
        payload["forecasts"][0] = forecaster.make_forecast(fixture())["forecast"]
        scored = brier_scorer.score_brier(payload)
        self.assertEqual(scored["questions"][0]["brier"], rational(1, 4))
        self.assertEqual(scored["questions"][0]["forecast_ref"], "fixture/forecast/test1")

    def test_cli_emits_same_forecast_as_python_api(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "forecast.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(forecaster.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), forecaster.make_forecast(fixture()))

    def test_leave_one_source_out_reports_largest_influence(self):
        result = forecaster.make_forecast(fixture())
        a, b = result["counterfactuals"]
        self.assertEqual((a["id"], a["posterior_without"], a["change_without"]),
                         ("a", rational(1, 4), rational(-1, 4)))
        self.assertEqual((b["id"], b["posterior_without"], b["change_without"]),
                         ("b", rational(2, 3), rational(1, 6)))
        self.assertEqual(result["largest_single_source_shift"], "a")

    def test_no_evidence_means_no_counterfactual_witness(self):
        result = forecaster.make_forecast({**fixture(), "evidence": []})
        self.assertEqual(result["counterfactuals"], [])
        self.assertIsNone(result["largest_single_source_shift"])

    def test_evidence_cannot_reuse_resolution_or_independence_reference(self):
        for ref in ("fixture/definition", "fixture/independence"):
            raw = fixture()
            raw["evidence"][0]["source_ref"] = ref
            with self.subTest(ref=ref), self.assertRaises(forecaster.ForecastError):
                forecaster.make_forecast(raw)

    def test_neutral_evidence_is_reported_without_inflating_probability(self):
        raw = {**fixture(), "evidence": [evidence("neutral", 1, 1, 1)]}
        result = forecaster.make_forecast(raw)
        self.assertEqual(result["probability_exact"], rational(2, 5))
        self.assertEqual(result["counterfactuals"][0]["change_without"], rational(0, 1))

    def test_horizon_keeps_absolute_time_and_does_not_reorder_known_events(self):
        raw = fixture()
        raw["evidence"][0]["known_at"] = "2026-11-20T07:00:00+07:00"
        result = forecaster.make_forecast(raw)
        self.assertEqual(result["evidence_trace"][1]["known_at"], "2026-11-20T00:00:00+00:00")
        self.assertEqual(result["resolve_by"], "2026-11-21T00:00:00+00:00")

    def test_nonterminating_posterior_keeps_exact_audit_field(self):
        raw = {**fixture(), "evidence": [evidence("one", 3, 3, 3)]}
        result = forecaster.make_forecast(raw)
        self.assertEqual(result["probability_exact"], rational(2, 3))
        self.assertEqual(result["forecast"]["probability"], "0.666666666666666667")
        self.assertEqual(result["scenario_range"]["upper"], rational(2, 3))
        self.assertEqual(result["scenario_range"]["lower"], rational(2, 3))

    def test_out_of_range_ratio_rejected_before_odds_mutation(self):
        raw = {**fixture(), "evidence": [evidence("huge", 1, "1000000.1", "1000000.1")]}
        with self.assertRaisesRegex(forecaster.ForecastError, "di luar batas"):
            forecaster.make_forecast(raw)
