"""Verifier area, erosi dan cakupan objek raster sintetis."""
import unittest

from ace_perception import _vision, object_counter as model


def pixels():
    w, h = 24, 13
    values = bytearray([255]*w*h)
    for x0, y0, x1, y1 in ((1, 1, 6, 6), (8, 1, 13, 6), (6, 3, 8, 4), (17, 8, 20, 11), (0, 12, 1, 13)):
        for y in range(y0, y1):
            for x in range(x0, x1):
                values[y*w+x] = 10
    return _vision.encode(w, h, values)


class CountTests(unittest.TestCase):
    def test_bridged_blobs_produce_two_eroded_cores_without_exact_claim(self):
        report = model.count(pixels(), minimum_area=8, maximum_single_area=30)
        self.assertEqual(report["single_candidates"], 1)
        self.assertEqual(report["crowded_components"], 1)
        self.assertEqual(report["discarded_small"], 1)
        self.assertEqual(report["area_assumption_range"], [3, 7])
        first = report["components"][0]
        self.assertEqual(first["pixels"], 52)
        self.assertEqual(first["box"], [1, 1, 13, 6])
        self.assertEqual(first["eroded_cores"], 2)
        self.assertEqual(first["area_count_range"], [2, 6])

    def test_crop_and_impossible_area_assumption_remain_visible(self):
        crop = model.count(pixels(), box=(16, 7, 23, 13), minimum_area=3, maximum_single_area=10)
        self.assertEqual(crop["components"][0]["box"], [17, 8, 20, 11])
        impossible = model.count(pixels(), minimum_area=29, maximum_single_area=30)
        self.assertIsNone(impossible["area_assumption_range"])
        self.assertIsNone(impossible["components"][0]["area_count_range"])

    def test_empty_and_bad_bounds(self):
        blank = _vision.encode(3, 3, [20]*9)
        self.assertEqual(model.count(blank)["area_assumption_range"], [0, 0])
        for changes in ({"box": [0, 0, 100, 100]}, {"maximum_single_area": 2},
                        {"erosion_steps": 4}, {"light_ink": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.count(blank, **changes)
