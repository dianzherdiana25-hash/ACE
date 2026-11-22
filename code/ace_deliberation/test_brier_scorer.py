"""Periksa skor dengan pecahan hitungan tangan dan kontrol kebocoran waktu."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import brier_scorer as brier


def outcome(identifier, result, when):
    return {"question_id": identifier, "outcome": result, "resolved_at": when,
            "resolution_ref": f"fixture/resolution/{identifier}"}


def forecast(identifier, prediction):
    return {"question_id": identifier, "probability": prediction,
            "forecast_at": "2026-11-20T00:00:00Z", "forecast_ref": f"fixture/forecast/{identifier}"}


def fixture():
    return {"cutoff": "2026-11-20T07:00:00+07:00", "as_of": "2026-11-22T00:00:00Z",
            "history": [outcome("h1", 0, "2026-11-19T00:00:00Z"),
                        outcome("h2", 1, "2026-11-19T00:00:00Z")],
            "forecasts": [forecast("test1", "0.2"), forecast("test2", "0.8")],
            "resolutions": [outcome("test1", 0, "2026-11-21T00:00:00Z"),
                            outcome("test2", 1, "2026-11-21T00:00:00Z")]}


class BrierTests(unittest.TestCase):
    def test_exact_brier_mean_and_positive_improvement(self):
        raw = fixture()
        result = brier.score_brier(raw)
        self.assertEqual(result["baseline_rate"], {"numerator": 1, "denominator": 2})
        self.assertEqual(result["brier"], {"numerator": 1, "denominator": 25})
        self.assertEqual(result["baseline_brier"], {"numerator": 1, "denominator": 4})
        self.assertEqual(result["improvement"], {"numerator": 21, "denominator": 100})
        self.assertEqual(result["brier_skill"], {"numerator": 21, "denominator": 25})
        self.assertEqual(result["verdict"], "better")
        self.assertEqual(result["question_count"], 2)
        raw["forecasts"].reverse()
        raw["resolutions"].reverse()
        self.assertEqual(result, brier.score_brier(raw))

    def test_worse_and_tie_are_reported_without_rounding(self):
        raw = fixture()
        raw["forecasts"] = [forecast("test1", 1), forecast("test2", 0)]
        self.assertEqual(brier.score_brier(raw)["verdict"], "worse")
        raw["forecasts"] = [forecast("test1", "0.5"), forecast("test2", "0.500000000000000000")]
        result = brier.score_brier(raw)
        self.assertEqual(result["verdict"], "tie")
        self.assertEqual(result["improvement"], {"numerator": 0, "denominator": 1})

    def test_zero_error_baseline_has_no_skill_ratio(self):
        raw = fixture()
        raw["history"][1]["outcome"] = 0
        raw["resolutions"][1]["outcome"] = 0
        raw["forecasts"] = [forecast("test1", 0), forecast("test2", "0")]
        result = brier.score_brier(raw)
        self.assertEqual(result["verdict"], "tie")
        self.assertIsNone(result["brier_skill"])

    def test_rejects_future_history_resolved_predictions_and_partial_set(self):
        raw = fixture()
        cases = [
            {"history": [outcome("h3", 1, "2026-11-20T00:00:00Z")]},
            {"history": [outcome("test1", 1, "2026-11-19T00:00:00Z")]},
            {"forecasts": [{**raw["forecasts"][0], "forecast_at": raw["resolutions"][0]["resolved_at"]},
                           raw["forecasts"][1]]},
            {"resolutions": raw["resolutions"][:1]},
            {"as_of": "2026-11-21T00:00:00"},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(brier.ScoringError):
                brier.score_brier({**raw, **changes})

    def test_rejects_non_binary_outcome_floating_input_and_duplicate_forecast(self):
        for key, changes in (("forecasts", {"probability": 0.5}),
                             ("forecasts", {"probability": "1.001"}),
                             ("forecasts", {"question_id": "test2"}),
                             ("resolutions", {"outcome": True})):
            with self.subTest(changes=changes), self.assertRaises(brier.ScoringError):
                raw = deepcopy(fixture())
                raw[key][0].update(changes)
                brier.score_brier(raw)

    def test_cli_retains_question_provenance(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "forecast.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(brier.main([str(path)]), 0)
        question = json.loads(output.getvalue())["questions"][0]
        self.assertEqual(question["forecast_ref"], "fixture/forecast/test1")
        self.assertEqual(question["resolution_ref"], "fixture/resolution/test1")

    def test_resolution_reuse_between_history_and_holdout_is_rejected(self):
        raw = fixture()
        raw["resolutions"][0]["resolution_ref"] = raw["history"][0]["resolution_ref"]
        with self.assertRaisesRegex(brier.ScoringError, "sudah dipakai"):
            brier.score_brier(raw)

    def test_equal_instants_with_different_zones_do_not_pass_temporal_ordering(self):
        raw = fixture()
        raw["forecasts"][0]["forecast_at"] = "2026-11-20T19:00:00-05:00"
        with self.assertRaisesRegex(brier.ScoringError, "sebelum resolusi"):
            brier.score_brier(raw)
