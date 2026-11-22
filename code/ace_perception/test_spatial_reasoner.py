"""Verifier relasi boks, kalibrasi dan jarak rasional."""
from hashlib import sha256
import unittest

from ace_perception import _vision, spatial_reasoner as model


IMAGE = _vision.encode(12, 12, [240]*144)


def fields(**changes):
    boxes = [("a", [0, 0, 2, 2]), ("b", [5, 6, 7, 8]), ("touch", [2, 1, 4, 3]), ("overlap", [1, 1, 4, 4])]
    data = {"schema": "ace.perception-spatial-layout.v1", "image_sha256": sha256(IMAGE).hexdigest(),
            "objects": [{"id": key, "box": box, "ref": f"fixture/{key}"} for key, box in boxes],
            "queries": [["a", "b"], ["a", "touch"], ["a", "overlap"]],
            "scale": {"points": [[0, 0], [3, 4]], "length": "10", "unit": "cm", "ref": "fixture/ruler"}}
    return model._canonical({**data, **changes})


def q(n, d=1):
    return {"numerator": n, "denominator": d}


class SpatialTests(unittest.TestCase):
    def test_squared_distance_and_iou_keep_exact_arithmetic(self):
        output = model.reason(IMAGE, fields())
        first, touch, overlap = output["relations"]
        self.assertEqual(first["horizontal"], "left_of")
        self.assertEqual(first["vertical"], "above")
        self.assertEqual(first["edge_pixel_distance_squared"], q(25))
        self.assertEqual(first["edge_unit_distance_squared"], q(100))
        self.assertEqual(first["center_unit_distance_squared"], q(244))
        self.assertEqual(first["a_ref"], "fixture/a")
        self.assertEqual(touch["box_interaction"], "touches")
        self.assertEqual(touch["intersection_pixels"], 0)
        self.assertEqual(overlap["box_interaction"], "overlaps")
        self.assertEqual(overlap["iou"], q(1, 12))
        self.assertEqual(overlap["center_delta_x"], q(-3, 2))

    def test_calibrated_dimensions_and_input_anchor_required(self):
        report = model.reason(IMAGE, fields(scale=None))
        self.assertIsNone(report["calibration"])
        self.assertIsNone(report["relations"][0]["edge_unit_distance_squared"])
        for opts in ({"image_sha256": "0"*64}, {"queries": [["a", "a"]]}, {"queries": [["a", "bad"]]}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                model.reason(IMAGE, fields(**opts))
