"""Verifier geometri jarum dengan skala eksak, putaran dan seri."""
from hashlib import sha256
from math import cos, radians, sin
import unittest

from ace_perception import _vision, gauge_reader as model


SIZE = 111
CENTER = 55


def meter(*positions):
    board = [240]*(SIZE*SIZE)
    for position in positions:
        theta = radians(position)
        for radius in range(16, 43):
            x, y = round(CENTER+radius*cos(theta)), round(CENTER+radius*sin(theta))
            board[y*SIZE+x] = 15
    return _vision.encode(SIZE, SIZE, board)


def layout(first=30, last=150, **options):
    return model._canonical({"schema": "ace.perception-gauge-layout.v1", "center": [CENTER, CENTER],
                             "inner_radius": 16, "outer_radius": 42, "threshold": 16, "light_ink": False,
                             "scale": [{"degrees": first, "value": "-1", "ref": "fixture/zero"},
                                       {"degrees": last, "value": "2", "ref": "fixture/full"}],
                             "sweep": "clockwise", "minimum_ink_bp": 7000,
                             "minimum_margin_bp": 1000, "peak_width_degrees": 5, "unit": "kPa", **options})


class GaugeTests(unittest.TestCase):
    def test_unique_needle_and_linear_scale(self):
        picture = meter(90)
        report = model.estimate(picture, layout())
        self.assertEqual(report["image_sha256"], sha256(picture).hexdigest())
        self.assertEqual(report["needle_degrees"], 90)
        self.assertEqual(report["value"], {"numerator": 1, "denominator": 2})
        self.assertEqual(report["scale_refs"], ["fixture/zero", "fixture/full"])
        self.assertEqual(report["peak_ink_ratio"], {"numerator": 1, "denominator": 1})
        self.assertEqual(report["rays"][60], {"degrees": 90, "ink": 27, "pixels": 27})

    def test_sweep_wraps_over_zero_with_declared_orientation(self):
        source = meter(0)
        direct = model.estimate(source, layout(315, 45))
        inverse = model.estimate(source, layout(45, 315, sweep="counterclockwise"))
        self.assertEqual(direct["needle_degrees"], 0)
        self.assertEqual(inverse["value"], direct["value"])

    def test_equal_needles_without_unique_winner_and_blank_without_evidence(self):
        two = model.estimate(meter(60, 120), layout())
        self.assertEqual(two["status"], "ambiguous")
        self.assertIsNone(two["needle_degrees"])
        self.assertIsNone(two["value"])
        bare = model.estimate(meter(), layout())
        self.assertEqual(bare["status"], "insufficient_ink")
        self.assertIsNone(bare["value"])

    def test_radius_and_calibration_malformed_checks_are_strict(self):
        for args in ({"sweep": "other"}, {"outer_radius": 99}, {"peak_width_degrees": 31},
                     {"minimum_margin_bp": 0}, {"center": [1, 1]}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                model.estimate(meter(90), layout(**args))
        with self.assertRaisesRegex(ValueError, "sweep"):
            model.estimate(meter(90), layout(90, 90))
