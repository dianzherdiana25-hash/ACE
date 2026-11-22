"""Verifier replay jendela krisis dan baseline berembargo."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import crisis_backtest as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def at(day):
    return f"2026-11-{day:02d}T00:00:00Z"


def window(key, start, stop):
    return {"id": key, "source_ref": f"fixture/{key}", "start": at(start), "end_exclusive": at(stop)}


def f(key, value, day):
    return {"question_id": key, "forecast_ref": f"p/{key}", "forecast_at": at(day), "probability": value}


def r(key, value, day):
    return {"question_id": key, "resolution_ref": f"r/{key}", "resolved_at": at(day), "outcome": value}


def fixture():
    return {
        "protocol_ref": "fixture/protocol", "as_of": at(28), "embargo_days": 2, "minimum_training": 1,
        "windows": [window("early", 10, 15), window("late", 20, 25)],
        "training": [r("prior-no", 0, 7), r("boundary-yes", 1, 8), r("recent-yes", 1, 17),
                     r("future-no", 0, 29)],
        "forecasts": [f("a", "0.5", 10), f("b", "0.8", 20), f("outside", "0.4", 15),
                      f("pending", "0.5", 12), f("late-forecast", "0.8", 21)],
        "resolutions": [r("a", 1, 11), r("b", 1, 22), r("late-forecast", 1, 21), r("pending", 0, 29)],
    }


class BacktestTests(unittest.TestCase):
    def test_rolling_baseline_uses_embargo_boundary_exclusively(self):
        result = model.replay(fixture())
        early, late = result["windows"]
        self.assertEqual(early["baseline_rate"], q(0))
        self.assertEqual(early["training_before"], "2026-11-08T00:00:00+00:00")
        self.assertEqual([row["question_id"] for row in early["training"]], ["prior-no"])
        self.assertEqual(late["baseline_rate"], q(2, 3))
        self.assertEqual([row["resolution_ref"] for row in late["training"]],
                         ["r/boundary-yes", "r/prior-no", "r/recent-yes"])
        self.assertEqual((early["improvement"], late["improvement"]), (q(3, 4), q(16, 225)))
        self.assertEqual(result["pooled"], {
            "paired_cases": 2, "brier": q(29, 200), "baseline_brier": q(5, 9), "improvement": q(739, 1800),
        })

    def test_pool_scores_cases_instead_of_equally_weighting_windows(self):
        raw = fixture()
        raw["forecasts"].append(f("extra", "0.9", 11))
        raw["resolutions"].append(r("extra", 0, 12))
        result = model.replay(raw)
        self.assertEqual(result["pooled"]["paired_cases"], 3)
        self.assertEqual(result["pooled"]["brier"], q(11, 30))
        self.assertEqual(result["pooled"]["baseline_brier"], q(10, 27))

    def test_excluded_cases_keep_timing_and_references(self):
        result = model.replay(fixture())
        self.assertEqual(result["outside_windows"], ["outside"])
        early, late = result["windows"]
        pending = early["records"][1]
        self.assertEqual(pending["status"], "unresolved_at_audit")
        self.assertEqual(pending["forecast_ref"], "p/pending")
        self.assertNotIn("resolution_ref", pending)
        self.assertEqual(late["records"][1]["status"], "late_forecast")
        self.assertEqual(late["records"][1]["resolution_ref"], "r/late-forecast")

    def test_unissued_case_never_enters_coverage_or_loss(self):
        raw = {**fixture(), "as_of": at(19)}
        result = model.replay(raw)
        self.assertEqual([item["status"] for item in result["windows"][1]["records"]],
                         ["unissued_at_audit", "unissued_at_audit"])
        self.assertEqual(result["pooled"]["paired_cases"], 1)
        self.assertEqual(result["pooled"]["improvement"], q(3, 4))

    def test_baseline_shortfall_withholds_comparison_but_preserves_observation(self):
        result = model.replay({**fixture(), "minimum_training": 2})
        early, late = result["windows"]
        early_first = early["records"][0]
        self.assertEqual(early_first["status"], "baseline_unavailable")
        self.assertEqual(early_first["resolution_ref"], "r/a")
        self.assertEqual(early_first["brier"], q(1, 4))
        self.assertIsNone(early["brier"])
        self.assertEqual(late["paired_cases"], 1)

    def test_training_questions_cannot_enter_either_held_out_list(self):
        raw = fixture()
        overlapping_training = [r("a", 1, 2), r("unforecast", 1, 2)]
        overlapping_training[0]["resolution_ref"] = "r/training-copy"
        with self.assertRaisesRegex(model.InputError, "tumpang"):
            model.replay({**raw, "training": overlapping_training})
        raw["resolutions"].append(r("unforecast", 1, 22))
        raw["resolutions"][-1]["resolution_ref"] = "r/new"
        with self.assertRaisesRegex(model.InputError, "tumpang"):
            model.replay({**raw, "training": overlapping_training[1:]})

    def test_touching_windows_accept_boundary_only_once(self):
        raw = fixture()
        raw["windows"][0]["end_exclusive"] = at(20)
        first, second = model.replay(raw)["windows"]
        self.assertNotIn("b", [case["question_id"] for case in first["records"]])
        self.assertIn("b", [case["question_id"] for case in second["records"]])
        raw["windows"][0]["end_exclusive"] = at(21)
        with self.assertRaisesRegex(model.InputError, "tumpang"):
            model.replay(raw)

    def test_bad_window_metadata_fails_closed(self):
        raw = fixture()
        for change in ({"windows": []}, {"windows": [window("bad", 10, 10)]},
                       {"windows": [window("same", 10, 15), window("same", 20, 25)]},
                       {"embargo_days": -1}, {"minimum_training": False}, {"as_of": "2026-11-20"}):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.replay({**raw, **change})

    def test_exactly_zero_measured_improvement_is_reported(self):
        raw = {**fixture(), "training": [r("no", 0, 3)], "forecasts": [f("a", "0", 10)]}
        self.assertEqual(model.replay(raw)["pooled"]["improvement"], q(0))

    def test_no_overlapping_forecasts_at_all_has_valid_empty_output(self):
        raw = fixture()
        raw["forecasts"] = [f("only-outside", "0", 1)]
        result = model.replay(raw)
        self.assertTrue(all(not row["records"] for row in result["windows"]))
        self.assertEqual(result["pooled"], {"paired_cases": 0, "brier": None,
                                           "baseline_brier": None, "improvement": None})

    def test_cli_bytes_are_stable_for_permuted_datasets(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "backtest.json"
        logs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            logs.append(output.getvalue())
            for key in ("windows", "training", "forecasts", "resolutions"):
                raw[key].reverse()
        self.assertEqual(logs[0], logs[1])

    def test_embargo_zero_keeps_resolution_at_start_outside_baseline(self):
        raw = fixture()
        raw["training"] += [r("on-start", 0, 10)]
        result = model.replay({**raw, "embargo_days": 0})
        self.assertEqual(result["windows"][0]["baseline_rate"], q(1, 2))
        self.assertNotIn("on-start", [row["question_id"] for row in result["windows"][0]["training"]])
        self.assertIn("on-start", [row["question_id"] for row in result["windows"][1]["training"]])

    def test_bad_early_date_does_not_wrap_embargo_into_future(self):
        raw = fixture()
        raw["windows"] = [{"id": "old", "start": "0001-01-01T00:00:00Z",
                          "end_exclusive": "0001-01-10T00:00:00Z", "source_ref": "fixture/old"}]
        with self.assertRaisesRegex(model.InputError, "rentang tanggal"):
            model.replay(raw)

    def test_before_first_window_cannot_expose_future_training_rows(self):
        raw = {**fixture(), "as_of": at(6)}
        report = model.replay(raw)
        self.assertTrue(all(not window["training"] for window in report["windows"]))
        self.assertTrue(all(window["training_before"] == "2026-11-06T00:00:00+00:00"
                            for window in report["windows"]))
        self.assertEqual(report["pooled"]["paired_cases"], 0)
