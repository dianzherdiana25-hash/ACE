"""Verifier digitasi garis, pecahan eksak, dan kolom tanpa keputusan."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _vision, chart_digitizer as model


def tick(pixel, value, ref):
    return {"pixel": pixel, "value": value, "ref": ref}


def layout_obj():
    return {"schema": "ace.perception-line-chart.v1", "plot": [1, 1, 7, 8],
            "x_axis": [tick(1, "0", "fixture/x0"), tick(6, "2.5", "fixture/x1")],
            "y_axis": [tick(2, "10", "fixture/y0"), tick(6, "0", "fixture/y1")], "stride_px": 1,
            "series": [{"id": "z", "gray_min": 100, "gray_max": 102, "max_stroke_px": 1},
                       {"id": "a", "gray_min": 10, "gray_max": 20, "max_stroke_px": 2}]}


def plot(points=None):
    data = bytearray([255]*90)
    if points is None:
        points = [(1, 2, 10), (1, 3, 15), (2, 4, 10), (2, 6, 10), (3, 5, 20), (4, 4, 10),
                  (4, 5, 10), (4, 6, 10), (6, 7, 10), (1, 6, 100), (3, 2, 102), (6, 4, 101)]
    for x, y, value in points:
        data[y*10+x] = value
    return _vision.encode(10, 9, data)


def read(raw=None, picture=None):
    return model.digitize(plot() if picture is None else picture, model._canonical(layout_obj() if raw is None else raw))


def q(n, d=1):
    return {"numerator": n, "denominator": d}


class ChartDigitizerTests(unittest.TestCase):
    def test_uses_actual_column_and_half_pixel_midpoint_from_two_gray_bands(self):
        payload = plot()
        layout = model._canonical(layout_obj())
        report = model.digitize(payload, layout)
        self.assertEqual(report["image_sha256"], sha256(payload).hexdigest())
        self.assertEqual(report["layout_sha256"], sha256(layout).hexdigest())
        self.assertEqual(report["calibration"]["y"][0], {"pixel": 2, "value": q(10), "ref": "fixture/y0"})
        first, second = report["series"]
        self.assertEqual((first["id"], second["id"]), ("a", "z"))
        self.assertEqual(first["read"], 2)
        self.assertEqual(second["read"], 3)
        initial = first["samples"][0]
        self.assertEqual(initial, {"x_pixel": 1, "x": q(0), "y": q(35, 4),
                                   "status": "read", "stroke_y_intervals": [[2, 4]]})
        self.assertEqual(first["samples"][2]["x"], q(1))
        self.assertEqual(first["samples"][2]["y"], q(5, 2))
        self.assertEqual(second["samples"][0]["y"], q(0))
        self.assertEqual(second["samples"][-1]["y"], q(5))

    def test_different_failure_statuses_keep_evidence_and_never_invent_values(self):
        first = read()["series"][0]["samples"]
        self.assertEqual([row["status"] for row in first], ["read", "multiple_traces", "read",
                         "too_thick", "missing", "outside_calibration"])
        self.assertEqual(first[1]["stroke_y_intervals"], [[4, 5], [6, 7]])
        self.assertEqual(first[3]["stroke_y_intervals"], [[4, 7]])
        self.assertEqual(first[4]["stroke_y_intervals"], [])
        for row in (first[1], *first[3:]):
            self.assertIsNone(row["y"])

    def test_missing_x_calibration_does_not_interpolate_outside_two_ticks(self):
        layout = layout_obj()
        layout["x_axis"] = [tick(3, "0", "fixture/x0"), tick(6, "2.5", "fixture/x1")]
        first = read(layout)["series"][0]["samples"][0]
        self.assertEqual(first["x_pixel"], 1)
        self.assertIsNone(first["x"])
        self.assertIsNone(first["y"])
        self.assertEqual(first["status"], "outside_calibration")

    def test_stride_and_reordering_calibration_keep_series_evidence(self):
        layout = layout_obj()
        original = read(layout)
        layout["stride_px"] = 2
        layout["series"].reverse()
        layout["x_axis"].reverse()
        stride = read(layout)
        self.assertEqual(stride["calibration"], original["calibration"])
        for new, old in zip(stride["series"], original["series"], strict=True):
            self.assertEqual(new["samples"], old["samples"][::2])
        self.assertEqual(stride["stride_px"], 2)

    def test_gray_bands_must_not_overlap_and_sources_cannot_repeat(self):
        layout = layout_obj()
        layout["series"][0]["gray_min"] = 20
        with self.assertRaisesRegex(ValueError, "beririsan"):
            read(layout)
        layout = layout_obj()
        layout["y_axis"][1]["ref"] = "fixture/x0"
        with self.assertRaisesRegex(ValueError, "dipakai ulang"):
            read(layout)

    def test_rejects_log_numbers_nan_duplicate_ticks_and_outside_plot(self):
        for changes in ({"value": "1e4"}, {"value": "NaN"}, {"pixel": True}, {"pixel": 5_000}, {"pixel": 6}):
            layout = layout_obj()
            layout["x_axis"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                read(layout)

    def test_work_bounds_checked_before_pixel_processing(self):
        with patch.object(model, "MAX_PLOT_PIXELS", 1), self.assertRaisesRegex(ValueError, "Plot"):
            read()
        with patch.object(model, "MAX_SAMPLES", 2), self.assertRaisesRegex(ValueError, "Pencuplikan"):
            read()

    def test_cli_keeps_inputs_and_exit_status_reports_series_without_reads(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        picture, layout = root/"chart.pgm", root/"layout.json"
        spec = model._canonical(layout_obj())
        layout.write_bytes(spec)
        cmd = [sys.executable, "-m", "ace_perception.chart_digitizer", str(picture), str(layout)]
        for payload, status in ((plot(), 0), (plot([]), 1)):
            picture.write_bytes(payload)
            run = subprocess.run(cmd, capture_output=True)
            self.assertEqual(run.returncode, status)
            self.assertEqual(json.loads(run.stdout), model.digitize(payload, spec))
            self.assertEqual(picture.read_bytes(), payload)
        layout.write_text("{}")
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
