"""Verifier diagram batang raster, kalibrasi eksak dan bukti yang ambigu."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import diagram_reader as model
from ace_perception.test_ocr_engine import raster
from ace_perception.test_screen_understanding import board, rectangle


def layout():
    return {"schema": "ace.perception-bar-layout.v1", "plot": [2, 2, 50, 27], "baseline_y": 17,
            "ticks": [{"y": 5, "value": "12", "ref": "fixture/tick/top"}, {"y": 25, "value": "-8", "ref": "fixture/tick/bottom"}],
            "categories": [{"id": name, "x_start": start, "x_stop": stop} for name, start, stop in
                           [("a", 4, 15), ("b", 15, 26), ("c", 27, 39)]],
            "minimum_fill_bp": 9300, "minimum_width": 2, "light_ink": False, "unit": "samples"}


def bytes_layout(raw=None):
    return json.dumps(layout() if raw is None else raw).encode()


def figure(*boxes, polarity=False):
    page = board(55, 33)
    for box in boxes:
        rectangle(page, box, filled=True)
    return raster(page, polarity=polarity)


BARS = [(6, 9, 10, 17), (17, 17, 21, 20), (30, 12, 36, 17)]


class DiagramTests(unittest.TestCase):
    def test_positive_negative_and_category_order_from_pixel_values(self):
        image = figure(*BARS)
        spec = bytes_layout()
        report = model.read_chart(image, spec)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["image_sha256"], sha256(image).hexdigest())
        self.assertEqual(report["layout_sha256"], sha256(spec).hexdigest())
        self.assertEqual(report["unit"], "samples")
        self.assertEqual(report["calibration_refs"], [{"y": 5, "ref": "fixture/tick/top"}, {"y": 25, "ref": "fixture/tick/bottom"}])
        self.assertEqual([row["category"] for row in report["rows"]], ["a", "b", "c"])
        for row, value, box in zip(report["rows"], [8, -3, 5], BARS, strict=True):
            self.assertEqual(row["value"], {"numerator": value, "denominator": 1})
            self.assertEqual(row["evidence"][0]["box"], list(box))
        self.assertEqual(report["rows"][0]["evidence"][0]["filled_pixels"], 32)
        self.assertEqual(report["rows"][1]["measured_y"], 20)

    def test_exact_rational_measurement_with_fractional_axis(self):
        spec = layout()
        spec["ticks"][0]["value"], spec["ticks"][1]["value"] = "0.4", "-0.26666667"
        with self.assertRaisesRegex(ValueError, "titik nol"):
            model.read_chart(figure(*BARS), bytes_layout(spec))
        spec["ticks"] = [{"y": 5, "value": "0.3", "ref": "fixture/top"}, {"y": 25, "value": "-0.2", "ref": "fixture/bottom"}]
        report = model.read_chart(figure(*BARS), bytes_layout(spec))
        self.assertEqual(report["rows"][0]["value"], {"numerator": 1, "denominator": 5})
        self.assertEqual(report["rows"][1]["value"], {"numerator": -3, "denominator": 40})

    def test_unattached_outside_scope_missing_and_duplicate_are_distinct(self):
        scan = figure((6, 3, 10, 17), (17, 11, 21, 16))
        report = model.read_chart(scan, bytes_layout())
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual([row["status"] for row in report["rows"]], ["outside_calibration", "unattached_bar", "missing"])
        self.assertTrue(all(row["value"] is None for row in report["rows"]))
        ambiguous = model.read_chart(figure(*BARS, (12, 11, 14, 17)), bytes_layout())
        self.assertEqual(ambiguous["rows"][0]["status"], "ambiguous")
        self.assertEqual(len(ambiguous["rows"][0]["evidence"]), 2)

    def test_unassigned_bar_cannot_be_nearest_category(self):
        scan = figure(*BARS, (24, 11, 28, 17), (0, 1, 2, 20))
        report = model.read_chart(scan, bytes_layout())
        self.assertEqual(report["unassigned_bars"], [{"box": [24, 11, 28, 17], "filled_pixels": 24}])
        self.assertEqual(report["status"], "incomplete")

    def test_light_ink_case_and_images_with_no_visible_data(self):
        spec = layout()
        spec["light_ink"] = True
        light = model.read_chart(figure(*BARS, polarity=True), bytes_layout(spec))
        dark = model.read_chart(figure(*BARS), bytes_layout())
        self.assertEqual(light["rows"], dark["rows"])
        no_bars = model.read_chart(figure(), bytes_layout())
        self.assertIsNone(no_bars["threshold"])
        self.assertTrue(all(row["status"] == "missing" for row in no_bars["rows"]))

    def test_refuses_overlap_reused_ticks_bad_bounds_and_shape(self):
        for mutate in (
            lambda raw: raw["categories"][1].update(x_start=14),
            lambda raw: raw["categories"][1].update(id="a"),
            lambda raw: raw["ticks"][1].update(y=5),
            lambda raw: raw["ticks"][1].update(ref="fixture/tick/top"),
            lambda raw: raw.update(baseline_y=True),
            lambda raw: raw.update(plot=[2, 2, 56, 34]),
            lambda raw: raw.update(minimum_fill_bp=10_001),
        ):
            spec = layout()
            mutate(spec)
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                model.read_chart(figure(*BARS), bytes_layout(spec))

    def test_cli_distinguishes_complete_partial_and_invalid_input(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        image, spec = root/"plot.pgm", root/"layout.json"
        spec.write_bytes(bytes_layout())
        for bars, code in ((BARS, 0), (BARS[:-1], 1)):
            image.write_bytes(figure(*bars))
            data = image.read_bytes()
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(image), str(spec)]), code)
            self.assertEqual(json.loads(output.getvalue()), model.read_chart(data, spec.read_bytes()))
            self.assertEqual(image.read_bytes(), data)
        spec.write_bytes(b"{}")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            model.main([str(image), str(spec)])
        self.assertEqual(error.exception.code, 2)

    def test_row_order_is_spatial_even_when_layout_supplies_unsorted_categories(self):
        before = model.read_chart(figure(*BARS), bytes_layout())
        config = layout()
        config["categories"].reverse()
        config["ticks"].reverse()
        after = model.read_chart(figure(*BARS), bytes_layout(config))
        self.assertNotEqual(after["layout_sha256"], before["layout_sha256"])
        self.assertEqual(after["rows"], before["rows"])
        self.assertEqual(after["calibration_refs"], before["calibration_refs"])

    def test_bar_crossing_baseline_is_never_assumed_stacked_or_signed(self):
        image = figure((6, 9, 10, 21), *BARS[1:])
        choice = model.read_chart(image, bytes_layout())["rows"][0]
        self.assertEqual(choice["status"], "unattached_bar")
        self.assertIsNone(choice["measured_y"])
        self.assertEqual(choice["evidence"][0]["box"], [6, 9, 10, 21])
