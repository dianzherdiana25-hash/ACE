"""Uji fallback kelas, batas waktu, dan bukti hitungan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import reference_class as model


def record(key, outcome, a="logic", b="python", day=19):
    return {"case_id": key, "resolved_at": f"2026-11-{day:02d}T00:00:00Z", "resolution_ref": f"fixture/{key}",
            "outcome": outcome, "fields": {"topic": a, "language": b}}


def fixture():
    return {
        "target": {"question_id": "target", "forecast_at": "2026-11-20T00:00:00Z",
                   "forecast_ref": "fixture/output", "fields": {"topic": "logic", "language": "python"}},
        "dimensions": ["topic", "language"], "minimum_cases": 2, "window_days": 10,
        "prior": {"success": 1, "failure": 1, "source_ref": "fixture/prior"},
        "history": [
            record("exact", 1), record("near", 0, b="rust"), record("near2", 1, b="go"),
            record("different", 1, a="other"),
            record("old", 1, day=9), record("cutoff", 1, day=20), record("target", 1, b="rust"),
        ],
    }


def q(n, d=1):
    return {"numerator": n, "denominator": d}


class ReferenceTests(unittest.TestCase):
    def test_uses_first_sufficient_prefix_and_keeps_source_trace(self):
        result = model.forecast(fixture())
        self.assertEqual(result["selection"]["dimensions"], ["topic"])
        self.assertEqual(result["selection"]["estimate"], q(3, 5))
        self.assertEqual(result["selection"]["empirical_rate"], q(2, 3))
        self.assertEqual(result["forecast"]["probability"], "0.6")
        self.assertEqual([item["case_id"] for item in result["selection"]["records"]], ["exact", "near", "near2"])
        self.assertEqual([item["count"] for item in result["attempted_classes"]], [1, 3, 4])

    def test_target_future_and_old_history_remain_excluded_from_pooled_class(self):
        report = model.forecast({**fixture(), "minimum_cases": 4})
        self.assertEqual(report["selection"]["dimensions"], [])
        self.assertEqual(report["selection"]["count"], 4)
        self.assertEqual({item["case_id"]: item["reason"] for item in report["excluded"]}, {
            "target": "target_case", "cutoff": "not_resolved_before_cutoff", "old": "outside_window",
        })

    def test_no_sufficient_class_never_publishes_prior_as_prediction(self):
        result = model.forecast({**fixture(), "minimum_cases": 5})
        self.assertEqual(result["status"], "insufficient_cases")
        self.assertIsNone(result["forecast"])
        self.assertIsNone(result["selection"])

    def test_minimum_exact_case_ignores_all_broader_cases(self):
        selection = model.forecast({**fixture(), "minimum_cases": 1})["selection"]
        self.assertEqual(selection["dimensions"], ["topic", "language"])
        self.assertEqual(selection["estimate"], q(2, 3))
        self.assertIsNone(selection["leave_one_case_range"])

    def test_sensitivity_is_bounded_on_both_sides_only_with_sufficient_remaining_cases(self):
        selection = model.forecast(fixture())["selection"]
        self.assertEqual(selection["leave_one_case_range"], {"minimum": q(1, 2), "maximum": q(3, 4)})
        result = model.forecast({**fixture(), "minimum_cases": 3})
        self.assertIsNone(result["selection"]["leave_one_case_range"])

    def test_window_exact_boundary_is_included_when_clock_is_normalized(self):
        raw = fixture()
        raw["history"].append(record("boundary", 0, day=10))
        raw["target"]["forecast_at"] = "2026-11-20T07:00:00+07:00"
        result = model.forecast(raw)
        self.assertIn("boundary", [item["case_id"] for item in result["selection"]["records"]])
        self.assertEqual(result["cutoff"], "2026-11-20T00:00:00+00:00")

    def test_reused_case_or_ref_cannot_increase_evidence_count(self):
        raw = fixture()
        for row in (record("exact", 0), {**record("fake", 0), "resolution_ref": "fixture/exact"}):
            with self.subTest(row=row), self.assertRaises(model.InputError):
                model.forecast({**raw, "history": [*raw["history"], row]})

    def test_cli_reproduces_without_using_record_order(self):
        raw = fixture()
        expected = model.forecast(raw)
        raw["history"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "class.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)

    def test_reference_contrast_uses_disjoint_cases(self):
        report = model.forecast(fixture())
        outside = report["outside_selected_class"]
        self.assertEqual(outside["records"], [{
            "case_id": "different", "resolved_at": "2026-11-19T00:00:00+00:00",
            "resolution_ref": "fixture/different", "outcome": 1,
        }])
        self.assertEqual(outside["estimate"], q(2, 3))
        self.assertEqual(report["delta_vs_outside_class"], q(-1, 15))
        pooled = model.forecast({**fixture(), "minimum_cases": 4})
        self.assertIsNone(pooled["outside_selected_class"])
        self.assertIsNone(pooled["delta_vs_outside_class"])

    def test_axis_order_selects_different_comparable_populations(self):
        raw = fixture()
        raw["history"].append(record("near3", 0, a="other"))
        first = model.forecast(raw)
        second = model.forecast({**raw, "dimensions": ["language", "topic"]})
        self.assertEqual(first["selection"]["dimensions"], ["topic"])
        self.assertEqual(second["selection"]["dimensions"], ["language"])
        self.assertEqual(first["selection"]["estimate"], q(3, 5))
        self.assertEqual(second["selection"]["estimate"], q(3, 5))
        self.assertNotEqual(first["selection"]["records"], second["selection"]["records"])

    def test_declared_prior_changes_estimate_but_never_counts_as_observations(self):
        raw = fixture()
        raw["prior"].update(success=5, failure=3)
        report = model.forecast(raw)
        self.assertEqual(report["selection"]["estimate"], q(7, 11))
        self.assertEqual(report["selection"]["empirical_rate"], q(2, 3))
        self.assertEqual(report["prior"]["source_ref"], "fixture/prior")
        with self.assertRaises(model.InputError):
            model.forecast({**raw, "prior": {**raw["prior"], "success": True}})
        raw["history"].clear()
        self.assertIsNone(model.forecast(raw)["forecast"])

    def test_aged_and_future_cases_stay_out_of_contrast(self):
        raw = fixture()
        raw["history"] += [record("age", 0, a="other", day=3), record("now", 0, a="other", day=20)]
        report = model.forecast(raw)
        self.assertEqual(report["outside_selected_class"]["count"], 1)
        self.assertEqual(report["outside_selected_class"]["misses"], 0)

    def test_invalid_dimensions_dates_and_outcomes_fail_instead_of_dropping_rows(self):
        raw = fixture()
        for change in (
            {"dimensions": ["topic", "topic"]},
            {"window_days": 0},
            {"history": [{**record("bad", 1), "outcome": 2}]},
            {"history": [{**record("local", 1), "resolved_at": "2026-11-19T00:00:00"}]},
            {"history": [{**record("extra", 1), "fields": {"topic": "logic"}}]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                model.forecast({**raw, **change})

    def test_single_class_extremes_never_assign_impossible_probabilities(self):
        for outcome, expected in ((0, "0.2"), (1, "0.8")):
            with self.subTest(outcome=outcome):
                raw = fixture()
                raw["history"] = [record(f"case-{index}", outcome) for index in range(3)]
                report = model.forecast(raw)
                self.assertEqual(report["forecast"]["probability"], expected)
                self.assertEqual(report["selection"]["empirical_rate"], q(outcome))
                self.assertFalse(report["excluded"])

    def test_newest_resolutions_within_window_are_preserved_even_in_reversed_input(self):
        raw = fixture()
        raw["history"] += [record("half-day", 0, day=20)]
        raw["history"][-1]["resolved_at"] = "2026-11-20T00:00:00.000001Z"
        result = model.forecast(raw)
        reasons = {row["case_id"]: row["reason"] for row in result["excluded"]}
        self.assertEqual(reasons["half-day"], reasons["cutoff"])
