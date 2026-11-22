"""Uji bin tepi, perhitungan kalibrasi persis, dan artefak SVG."""
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.etree import ElementTree

from ace_deliberation import calibration_analyzer as analyzer
from ace_deliberation.test_brier_scorer import fixture, forecast, outcome


def fraction(payload):
    return Fraction(payload["numerator"], payload["denominator"])


class CalibrationTests(unittest.TestCase):
    def test_reliability_and_resolution_decompose_grouped_brier(self):
        report = analyzer.analyze(fixture(), bins=2)
        self.assertEqual([row["count"] for row in report["bins"]], [1, 1])
        self.assertEqual(fraction(report["ece"]), Fraction(1, 5))
        self.assertEqual(fraction(report["reliability"]), Fraction(1, 25))
        self.assertEqual(fraction(report["resolution"]), Fraction(1, 4))
        self.assertEqual(fraction(report["uncertainty"]), Fraction(1, 4))
        self.assertEqual(fraction(report["grouped_brier"]), Fraction(1, 25))
        self.assertEqual(report["individual_brier"], report["grouped_brier"])
        self.assertEqual(report["bins"][0]["questions"], [{
            "id": "test1", "forecast_ref": "fixture/forecast/test1", "resolution_ref": "fixture/resolution/test1",
        }])

    def test_within_bin_individual_brier_can_differ_from_grouped_brier(self):
        raw = fixture()
        raw["forecasts"][0]["probability"] = "0.6"
        result = analyzer.analyze(raw, bins=2)
        self.assertEqual(fraction(result["ece"]), Fraction(1, 5))
        self.assertEqual(fraction(result["individual_brier"]), Fraction(1, 5))
        self.assertEqual(fraction(result["grouped_brier"]), Fraction(29, 100))
        identity = (fraction(result["reliability"]) - fraction(result["resolution"])
                    + fraction(result["uncertainty"]))
        self.assertEqual(identity, fraction(result["grouped_brier"]))

    def test_upper_endpoint_belongs_to_last_bin_and_empty_bins_are_omitted_in_svg(self):
        raw = fixture()
        raw["forecasts"] = [forecast("test1", 0), forecast("test2", 1)]
        result = analyzer.analyze(raw, bins=4)
        self.assertEqual([row["count"] for row in result["bins"]], [1, 0, 0, 1])
        self.assertEqual([row["include_high"] for row in result["bins"]], [False, False, False, True])
        for row in result["bins"][1:3]:
            self.assertIsNone(row["observed_rate"])
            self.assertIsNone(row["mean_prediction"])
            self.assertIsNone(row["confidence_95"])
        svg = ElementTree.fromstring(analyzer.render_svg(result))
        circles = svg.findall("{*}circle")
        self.assertEqual([(item.get("cx"), item.get("cy")) for item in circles],
                         [("92.00", "476.00"), ("532.00", "36.00")])

    def test_probability_exactly_on_interior_boundary_uses_higher_bin(self):
        raw = fixture()
        raw["forecasts"][0]["probability"] = "0.5"
        report = analyzer.analyze(raw, bins=4)
        self.assertEqual([row["count"] for row in report["bins"]], [0, 0, 1, 1])
        self.assertEqual(report["bins"][2]["confidence_95"][0], 0)
        self.assertLess(report["bins"][2]["confidence_95"][1], 1)

    def test_input_order_and_cli_output_are_stable(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "sample.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(analyzer.main([str(path), "--format", "svg"]), 0)
        raw["forecasts"].reverse()
        raw["resolutions"].reverse()
        self.assertEqual(output.getvalue(), analyzer.render_svg(analyzer.analyze(raw)))

    def test_invalid_bins_and_leaked_outcomes_fail_closed(self):
        for bins in (True, -1, 1, 101):
            with self.subTest(bins=bins), self.assertRaises(ValueError):
                analyzer.analyze(fixture(), bins=bins)
        raw = fixture()
        raw["resolutions"].append(outcome("post-hoc", 1, "2026-11-21T00:00:00Z"))
        with self.assertRaisesRegex(ValueError, "held-out"):
            analyzer.analyze(raw)

    def test_signed_gap_keeps_opposite_biases_from_canceling(self):
        result = analyzer.analyze(fixture(), bins=2)
        lower, upper = result["bins"]
        self.assertEqual(fraction(lower["signed_gap"]), Fraction(1, 5))
        self.assertEqual(fraction(upper["signed_gap"]), Fraction(-1, 5))
        for key in ("overprediction_ece", "underprediction_ece"):
            self.assertEqual(fraction(result[key]), Fraction(1, 10))
        self.assertEqual(fraction(result["ece"]),
                         sum(fraction(row["ece_contribution"]) for row in result["bins"]))

    def test_weights_ece_by_bin_population_not_equal_bin_average(self):
        raw = fixture()
        raw["forecasts"].append(forecast("test3", "0.2"))
        raw["resolutions"].append(outcome("test3", 1, "2026-11-21T00:00:00Z"))
        result = analyzer.analyze(raw, bins=2)
        self.assertEqual([row["count"] for row in result["bins"]], [2, 1])
        self.assertEqual(fraction(result["ece"]), Fraction(4, 15))
        self.assertEqual(fraction(result["bins"][0]["ece_contribution"]), Fraction(1, 5))

    def test_empty_bins_carry_no_signed_gap_or_numeric_weight(self):
        report = analyzer.analyze(fixture(), bins=10)
        outside = [row for row in report["bins"] if not row["count"]]
        self.assertEqual(len(outside), 8)
        self.assertTrue(all(row["signed_gap"] is None and row["ece_contribution"] is None for row in outside))

    def test_first_and_last_confidence_ranges_stay_in_probability_scale(self):
        raw = fixture()
        raw["forecasts"] = [forecast("test1", 0), forecast("test2", 1)]
        first, last = analyzer.analyze(raw, bins=2)["bins"]
        self.assertEqual(first["confidence_95"][0], 0)
        self.assertEqual(last["confidence_95"][1], 1)
        self.assertGreater(last["confidence_95"][0], 0)
        self.assertLess(first["confidence_95"][1], 1)

    def test_cli_json_agrees_with_analysis(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "sample.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(analyzer.main([str(path), "--bins", "3"]), 0)
        self.assertEqual(json.loads(output.getvalue()), analyzer.analyze(fixture(), bins=3))

    def test_exact_alignment_gives_zero_error_when_probabilities_match_outcomes(self):
        raw = fixture()
        raw["forecasts"] = [forecast("test1", 0), forecast("test2", 1)]
        report = analyzer.analyze(raw)
        self.assertEqual(fraction(report["ece"]), 0)
