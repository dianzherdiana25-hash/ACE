"""Uji jendela triwulan, pasangan Brier, dan riwayat terlarang."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import forecast_quarterly_audit as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def forecast(key, value, when="2026-10-03T00:00:00Z"):
    return {"question_id": key, "probability": value, "forecast_at": when, "forecast_ref": f"p/{key}"}


def resolved(key, outcome, when="2026-10-07T00:00:00Z"):
    return {"question_id": key, "outcome": outcome, "resolved_at": when, "resolution_ref": f"r/{key}"}


def fixture():
    return {"year": 2026, "quarter": 4, "audit_as_of": "2026-12-20T00:00:00Z", "protocol_ref": "fixture/audit",
            "forecasts": [
                forecast("win", "0.8"), forecast("lose", "0.2"), forecast("pending", "0.7"),
                forecast("late", "0.9"), forecast("future", "0.1", "2026-12-31T00:00:00Z"),
                forecast("prev", "0.1", "2026-09-30T23:59:59Z"),
                forecast("next", "0.1", "2027-01-01T00:00:00Z"),
            ],
            "resolutions": [resolved("win", 1), resolved("lose", 0),
                            resolved("late", 1, "2026-10-03T00:00:00Z"),
                            resolved("pending", 0, "2026-12-21T00:00:00Z")],
            "baseline": [resolved("prior-yes", 1, "2026-09-02T00:00:00Z"),
                         resolved("prior-no", 0, "2026-09-02T00:00:00Z"),
                         resolved("other", 1, "2026-10-01T00:00:00Z"),
                         resolved("pending", 0, "2026-09-02T00:00:00Z") | {"resolution_ref": "r/prior-reuse"}]}


def indexed(report):
    return {row["question_id"]: row for row in report["cohort"]}


class AuditTests(unittest.TestCase):
    def test_matched_scores_and_baseline_match_hand_calculation(self):
        result = model.audit(fixture())
        self.assertEqual(result["period"], "2026-Q4")
        self.assertEqual(result["scores"], {"brier": q(1, 25), "baseline_brier": q(1, 4), "improvement": q(21, 100)})
        self.assertEqual(result["baseline"]["rate"], q(1, 2))
        self.assertEqual(result["counts"], {"scored": 2, "pending": 1, "late_forecast": 1, "unissued_at_audit": 1})
        for key in ("win", "lose"):
            row = indexed(result)[key]
            self.assertEqual(row["forecast_ref"], f"p/{key}")
            self.assertEqual(row["resolution_ref"], f"r/{key}")
            self.assertEqual(row["brier"], q(1, 25))
            self.assertEqual(row["baseline_brier"], q(1, 4))

    def test_interval_is_utc_half_open_even_with_offsets(self):
        raw = fixture()
        raw["forecasts"] += [forecast("first", "0.5", "2026-10-01T07:00:00+07:00"),
                             forecast("previous", "0.5", "2026-10-01T06:59:59+07:00")]
        result = model.audit(raw)
        self.assertEqual(result["start"], "2026-10-01T00:00:00+00:00")
        self.assertEqual(result["end_exclusive"], "2027-01-01T00:00:00+00:00")
        self.assertEqual(result["outside_cohort"], ["next", "prev", "previous"])
        self.assertEqual(indexed(result)["first"]["status"], "pending")

    def test_historical_baseline_excludes_cohort_and_boundary(self):
        result = model.audit(fixture())
        self.assertEqual(result["baseline"]["excluded"], [
            {"question_id": "other", "resolution_ref": "r/other", "reason": "not_before_quarter"},
            {"question_id": "pending", "resolution_ref": "r/prior-reuse", "reason": "cohort_question"},
        ])
        self.assertEqual([x["outcome"] for x in result["baseline"]["training"]], [0, 1])

    def test_future_resolutions_are_revealed_only_after_their_timestamp(self):
        raw = fixture()
        before = indexed(model.audit(raw))["pending"]
        self.assertEqual(before["status"], "pending")
        self.assertNotIn("outcome", before)
        self.assertNotIn("resolution_ref", before)
        raw["audit_as_of"] = "2026-12-21T00:00:00Z"
        after = indexed(model.audit(raw))["pending"]
        self.assertEqual(after["status"], "scored")
        self.assertEqual(after["brier"], q(49, 100))
        self.assertEqual(after["resolution_ref"], "r/pending")

    def test_missing_baseline_keeps_model_score_and_absence(self):
        result = model.audit({**fixture(), "baseline": []})
        self.assertEqual(result["scores"], {"brier": q(1, 25), "baseline_brier": None, "improvement": None})
        self.assertIsNone(result["baseline"]["rate"])
        self.assertIsNone(indexed(result)["win"]["baseline_brier"])

    def test_no_paired_outcomes_means_no_score_even_if_baseline_exists(self):
        result = model.audit({**fixture(), "resolutions": []})
        self.assertEqual(result["counts"]["pending"], 4)
        self.assertEqual(result["scores"], dict.fromkeys(("brier", "baseline_brier", "improvement")))
        self.assertEqual(result["baseline"]["rate"], q(1, 2))

    def test_issuance_gate_keeps_future_forecasts_out_of_score(self):
        raw = fixture()
        raw["resolutions"].append(resolved("future", 1, "2026-12-08T00:00:00Z"))
        result = model.audit(raw)
        self.assertEqual(indexed(result)["future"]["status"], "unissued_at_audit")
        self.assertEqual(result["counts"]["scored"], 2)
        raw["audit_as_of"] = "2027-01-01T00:00:00Z"
        result = model.audit(raw)
        self.assertTrue(result["closed_period"])
        self.assertEqual(indexed(result)["future"]["status"], "late_forecast")
        self.assertEqual(indexed(result)["future"]["resolution_ref"], "r/future")

    def test_duplicate_version_and_conflicting_resolution_are_refused(self):
        raw = fixture()
        resolution = raw["resolutions"][0]
        duplicates = (
            {"forecasts": [*raw["forecasts"], {**raw["forecasts"][0], "forecast_ref": "p/duplicate"}]},
            {"resolutions": [*raw["resolutions"], resolution]},
            {"baseline": [{**resolution, "outcome": 0}]},
            {"baseline": [{**resolution, "resolution_ref": "p/win"}]},
        )
        for changed in duplicates:
            with self.subTest(changed=changed.keys()), self.assertRaises(model.InputError):
                model.audit({**raw, **changed})

    def test_exact_same_baseline_record_can_be_shared_if_outside_cohort(self):
        raw = fixture()
        raw["resolutions"].append(raw["baseline"][0].copy())
        self.assertEqual(model.audit(raw)["baseline"]["rate"], q(1, 2))

    def test_bad_quarter_year_and_as_of_fail_with_no_table(self):
        raw = fixture()
        for changed in ({"quarter": 0}, {"quarter": True}, {"quarter": 5}, {"year": 9999},
                        {"audit_as_of": "2026-09-30T00:00:00Z"}, {"audit_as_of": "2026-12-20T00:00:00"}):
            with self.subTest(changed=changed), self.assertRaises(model.InputError):
                model.audit({**raw, **changed})

    def test_cli_order_is_stable_after_permuting_inputs(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "quarter.json"
        output = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as stream:
                self.assertEqual(model.main([str(path)]), 0)
            output.append(stream.getvalue())
            for field in ("baseline", "resolutions", "forecasts"):
                raw[field].reverse()
        self.assertEqual(output[0], output[1])

    def test_overconfident_misses_can_benchmark_worse_than_base_rate(self):
        raw = fixture()
        raw["forecasts"][0]["probability"] = "0.1"
        raw["forecasts"][1]["probability"] = "0.9"
        self.assertEqual(model.audit(raw)["scores"], {
            "brier": q(81, 100), "baseline_brier": q(1, 4), "improvement": q(-14, 25),
        })

    def test_q1_and_q3_end_dates_do_not_round_months_into_cohort(self):
        for quarter, start, end in ((1, "01", "04"), (2, "04", "07"), (3, "07", "10")):
            with self.subTest(quarter=quarter):
                raw = {**fixture(), "quarter": quarter,
                       "forecasts": [forecast("inside", "0.1", f"2026-{start}-01T00:00:00Z"),
                                     forecast("outside", "0.1", f"2026-{end}-01T00:00:00Z")]}
                result = model.audit(raw)
                self.assertEqual(result["outside_cohort"], ["outside"])
                self.assertEqual(indexed(result)["inside"]["status"], "pending")

    def test_base_rate_zero_is_data_distinct_from_empty_history(self):
        raw = fixture()
        raw["baseline"] = [raw["baseline"][1]]
        report = model.audit(raw)
        self.assertEqual(report["baseline"]["rate"], q(0))
        self.assertEqual(indexed(report)["win"]["baseline_brier"], q(1))
        self.assertEqual(indexed(report)["lose"]["baseline_brier"], q(0))
        self.assertEqual(report["scores"]["baseline_brier"], q(1, 2))

    def test_second_ref_cannot_hide_contradictory_baseline_for_same_question(self):
        raw = fixture()
        raw["resolutions"].append({**raw["baseline"][0], "resolution_ref": "r/alternate", "outcome": 0})
        with self.assertRaisesRegex(model.InputError, "bertentangan"):
            model.audit(raw)

    def test_empty_cohort_remains_valid_and_keeps_historical_provenance(self):
        raw = fixture()
        result = model.audit({**raw, "forecasts": [], "baseline": raw["baseline"][:-1]})
        self.assertEqual(result["cohort"], [])
        self.assertEqual(sum(result["counts"].values()), 0)
        self.assertEqual(result["baseline"]["training"][0]["resolution_ref"], "r/prior-no")
        self.assertIsNone(result["scores"]["improvement"])
