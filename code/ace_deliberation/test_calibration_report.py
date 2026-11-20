"""Verifier laporan pemilik, delta antarperiode dan sumber sampel."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import calibration_report as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def dataset(key, start, end, predicted, outcomes):
    return {
        "cutoff": f"2026-11-{start:02}T00:00:00Z", "as_of": f"2026-11-{end:02}T00:00:00Z",
        "history": [
            {"question_id": "h1", "resolved_at": "2026-10-30T00:00:00Z", "outcome": 1, "resolution_ref": "r/h1"},
            {"question_id": "h2", "resolved_at": "2026-10-30T00:00:00Z", "outcome": 0, "resolution_ref": "r/h2"},
        ],
        "forecasts": [
            {"question_id": f"{key}/{i}", "forecast_at": f"2026-11-{start:02}T10:00:00Z", "probability": p,
             "forecast_ref": f"p/{key}/{i}"} for i, p in enumerate(predicted)
        ],
        "resolutions": [
            {"question_id": f"{key}/{i}", "resolved_at": f"2026-11-{end:02}T00:00:00Z", "outcome": y,
             "resolution_ref": f"r/{key}/{i}"} for i, y in enumerate(outcomes)
        ],
    }


def entry(scope, key, start, end, predicted=("0.2", "0.8"), outcomes=(0, 1)):
    return {"domain": scope, "period": key, "source_ref": f"s/{scope}/{key}",
            "brier_input": dataset(key, start, end, predicted, outcomes)}


def fixture():
    return {
        "protocol_ref": "fixture/p", "bins": 2, "minimum_sample": 2,
        "periods": [entry("infra", "early", 1, 8), entry("infra", "late", 8, 16, ("0.1", "0.9")),
                    entry("riset", "latest", 8, 16, ("0.5",), (1,))],
    }


class ReportTests(unittest.TestCase):
    def test_point_metrics_and_delta_match_hand_calculation(self):
        report = model.report(fixture())
        self.assertEqual([row["domain"] for row in report["domains"]], ["infra", "riset"])
        first, last = report["domains"][0]["periods"]
        self.assertEqual(first["metrics"], {"brier": q(1, 25), "baseline_brier": q(1, 4),
                                            "improvement": q(21, 100), "ece": q(1, 5)})
        self.assertIsNone(first["change_since_previous"])
        self.assertEqual(last["change_since_previous"], {
            "since": "early", "from_source": "s/infra/early", "to_source": "s/infra/late", "status": "compared",
            "delta": {"brier": q(-3, 100), "baseline_brier": q(0), "improvement": q(3, 100), "ece": q(-1, 10)},
        })

    def test_domain_samples_never_compete_for_same_chronology(self):
        domains = model.report(fixture())["domains"]
        independent, = domains[1]["periods"]
        self.assertEqual(independent["count"], 1)
        self.assertEqual(independent["metrics"]["ece"], q(1, 2))
        self.assertIsNone(independent["change_since_previous"])
        self.assertEqual(domains[0]["periods"][1]["count"], 2)

    def test_report_carries_per_bin_sources_and_baseline_history(self):
        first = model.report(fixture())["domains"][0]["periods"][0]
        self.assertEqual(first["bins"][0]["questions"], [
            {"id": "early/0", "forecast_ref": "p/early/0", "resolution_ref": "r/early/0"},
        ])
        self.assertEqual(first["baseline_rate"], q(1, 2))
        self.assertEqual([row["resolution_ref"] for row in first["history"]], ["r/h1", "r/h2"])

    def test_delta_withheld_when_either_adjacent_period_has_too_few_cases(self):
        raw = fixture()
        raw["periods"].append(entry("infra", "last", 16, 20, ("0.75",), (1,)))
        periods = model.report(raw)["domains"][0]["periods"]
        self.assertEqual(periods[-1]["change_since_previous"]["status"], "insufficient_sample")
        self.assertIsNone(periods[-1]["change_since_previous"]["delta"])
        self.assertEqual(periods[-1]["metrics"]["brier"], q(1, 16))
        self.assertEqual(periods[1]["change_since_previous"]["status"], "compared")

    def test_duplicate_period_and_overlapping_period_are_invalid(self):
        raw = fixture()
        for extra in (entry("infra", "overlap", 7, 15), entry("infra", "late", 16, 20)):
            with self.subTest(extra=extra["period"]), self.assertRaises(model.InputError):
                model.report({**raw, "periods": [*raw["periods"], extra]})

    def test_reusing_same_question_across_periods_is_invalid_even_under_new_ref(self):
        raw = fixture()
        candidate = raw["periods"][1]["brier_input"]
        candidate["forecasts"][0]["question_id"] = "early/0"
        candidate["resolutions"][0]["question_id"] = "early/0"
        with self.assertRaisesRegex(model.InputError, "held-out"):
            model.report(raw)

    def test_aliased_held_out_reference_is_invalid_even_with_different_question(self):
        raw = fixture()
        raw["periods"][1]["brier_input"]["resolutions"][0]["resolution_ref"] = "r/early/0"
        with self.assertRaisesRegex(model.InputError, "ganda"):
            model.report(raw)

    def test_malformed_scoring_input_is_not_reported_as_perfect_calibration(self):
        raw = fixture()
        raw["periods"][0]["brier_input"]["resolutions"].pop()
        with self.assertRaises(ValueError):
            model.report(raw)

    def test_markdown_shows_counts_deltas_and_escapes_source_markup(self):
        raw = fixture()
        raw["periods"][0]["source_ref"] = "path|file [example] <b>\nnext"
        report = model.report(raw)
        markdown = model.format_markdown(report)
        self.assertIn("| early | 2 | 1/25 | 1/4 | 1/5 | — | — |", markdown)
        self.assertIn("| late | 2 | 1/100 | 1/4 | 1/10 | -3/100 | -1/10 |", markdown)
        self.assertIn("path&#124;file &#91;example&#93; &lt;b&gt; next", markdown)
        self.assertNotIn("<b>", markdown)
        self.assertIn("Protokol fixture/p.", markdown)

    def test_markdown_display_for_insufficient_and_empty_periods(self):
        raw = {**fixture(), "minimum_sample": 3}
        markdown = model.format_markdown(model.report(raw))
        self.assertIn("| Sampel kurang | Sampel kurang |", markdown)
        empty = model.report({**raw, "periods": []})
        self.assertEqual(empty["domains"], [])
        self.assertIn("Belum ada periode", model.format_markdown(empty))

    def test_cli_formats_replay_and_order_are_stable(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "report.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), model.report(raw))
        raw["periods"].reverse()
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as replay:
            self.assertEqual(model.main([str(path)]), 0)
        self.assertEqual(replay.getvalue(), output.getvalue())
        with redirect_stdout(StringIO()) as markdown:
            self.assertEqual(model.main([str(path), "--format", "markdown"]), 0)
        self.assertEqual(markdown.getvalue(), model.format_markdown(model.report(raw)))

    def test_sample_floor_and_bins_are_validated_even_without_periods(self):
        raw = {**fixture(), "periods": []}
        for change in ({"bins": 1}, {"bins": True}, {"minimum_sample": 0}, {"protocol_ref": ""}):
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.report({**raw, **change})

    def test_same_period_name_allowed_in_two_distinct_domains(self):
        raw = {**fixture(), "periods": [entry("infra", "one", 8, 15), entry("riset", "one", 8, 15)]}
        report = model.report(raw)
        self.assertEqual([domain["periods"][0]["period"] for domain in report["domains"]], ["one", "one"])

    def test_drift_keeps_baseline_shift_distinct_from_model_shift(self):
        raw = fixture()
        second = raw["periods"][1]["brier_input"]
        second["history"][1]["outcome"] = 1
        newest = model.report(raw)["domains"][0]["periods"][1]
        self.assertEqual(newest["baseline_rate"], q(1))
        self.assertEqual(newest["metrics"]["baseline_brier"], q(1, 2))
        self.assertEqual(newest["change_since_previous"]["delta"]["baseline_brier"], q(1, 4))
        self.assertEqual(newest["change_since_previous"]["delta"]["improvement"], q(7, 25))

    def test_latest_period_is_ordered_by_cutoff_not_display_label(self):
        raw = {**fixture(), "periods": [
            entry("infra", "z-earlier", 1, 7),
            entry("infra", "a-later", 8, 16),
        ]}
        early, late = model.report(raw)["domains"][0]["periods"]
        self.assertEqual(early["period"], "z-earlier")
        self.assertEqual(late["change_since_previous"]["since"], "z-earlier")
        self.assertEqual(late["change_since_previous"]["delta"]["brier"], q(0))
