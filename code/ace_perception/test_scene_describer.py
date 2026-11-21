"""Verifier kotak, relasi dan penghitungan statistik dari raster."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _vision, scene_describer as model


def picture(*, reverse=False):
    width, height = 20, 16
    data = bytearray([255]*width*height)
    for x in range(6):
        data[width+x+1] = 10
        data[2*width+x+1] = 25
    for y in range(3, 10):
        data[y*width+11] = 0
    for x, y in ((1, 13), (2, 13), (1, 14), (2, 14), (16, 0)):
        data[y*width+x] = 20
    if reverse:
        data = bytearray(255-value for value in data)
    return _vision.encode(width, height, data)


class SceneTests(unittest.TestCase):
    def test_shapes_and_relative_positions_without_inferring_object_identity(self):
        data = picture()
        result = model.describe(data, threshold=30)
        self.assertEqual(result["image_sha256"], sha256(data).hexdigest())
        self.assertEqual(result["size"], [20, 16])
        self.assertEqual(result["threshold"], 30)
        self.assertEqual(result["omitted_small"], 1)
        self.assertEqual(result["omitted_limit"], 0)
        self.assertEqual(result["visible_shape_counts"], {"compact": 1, "elongated_horizontal": 1, "elongated_vertical": 1})
        first, second, third = result["regions"]
        self.assertEqual(first["box"], [1, 1, 7, 3])
        self.assertEqual(first["fill_bp"], 10000)
        self.assertEqual(first["centroid_box_ink"], {"x": [42, 12], "y": [18, 12]})
        self.assertEqual(first["intensity"], {"min": 10, "max": 25, "mean": [210, 12]})
        self.assertEqual(first["component_pixels"], 12)
        self.assertEqual(second["box"], [11, 3, 12, 10])
        self.assertEqual(third["box"], [1, 13, 3, 15])
        rels = {(row["subject"], row["relation"], row["object"]) for row in result["relations"]}
        self.assertIn(("region-1", "left_of", "region-2"), rels)
        self.assertIn(("region-1", "above", "region-2"), rels)
        self.assertIn(("region-2", "above", "region-3"), rels)

    def test_nested_object_does_not_count_as_part_of_surrounding_component(self):
        width = height = 9
        data = [255]*(width*height)
        for y in range(1, 8):
            for x in range(1, 8):
                if x in (1, 7) or y in (1, 7):
                    data[y*width+x] = 0
        data[4*width+4] = 0
        result = model.describe(_vision.encode(width, height, data), minimum_pixels=1)
        large, small = result["regions"]
        self.assertEqual(large["component_pixels"], 24)
        self.assertEqual(large["box_ink_pixels"], 25)
        self.assertEqual(large["shape_hint"], "irregular")
        self.assertEqual(small["component_pixels"], 1)
        self.assertEqual(result["relations"], [{"subject": "region-2", "relation": "inside_box", "object": "region-1"}])

    def test_keep_largest_components_independent_of_scan_position(self):
        result = model.describe(picture(), minimum_pixels=1, maximum_regions=1)
        self.assertEqual(result["omitted_small"], 0)
        self.assertEqual(result["omitted_limit"], 3)
        self.assertEqual(len(result["regions"]), 1)
        self.assertEqual(result["regions"][0]["component_pixels"], 12)

    def test_light_ink_and_otsu_share_boxes_but_report_original_intensity(self):
        original = model.describe(picture())
        inverse = model.describe(picture(reverse=True), light_ink=True)
        self.assertEqual([row["box"] for row in original["regions"]], [row["box"] for row in inverse["regions"]])
        self.assertEqual(original["relations"], inverse["relations"])
        self.assertEqual(inverse["regions"][0]["intensity"]["min"], 230)
        self.assertNotEqual(original["image_sha256"], inverse["image_sha256"])

    def test_empty_input_returns_no_claims_and_polarity_type_is_strict(self):
        blank = _vision.encode(2, 3, b"x"*6)
        result = model.describe(blank)
        self.assertIsNone(result["threshold"])
        self.assertEqual(result["regions"], [])
        self.assertEqual(result["visible_shape_counts"], {})
        for change in ({"light_ink": 1}, {"minimum_pixels": 0}, {"maximum_regions": 0}, {"threshold": -1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                model.describe(blank, **change)

    def test_partial_intersection_relation_records_overlap_area(self):
        first = {"id": "a", "box": [0, 1, 4, 5]}
        second = {"id": "b", "box": [3, 3, 8, 10]}
        self.assertEqual(model._relate(first, second), [
            {"subject": "a", "relation": "overlapping_box", "object": "b", "overlap_pixels": 2}])

    def test_feature_budget_counts_raw_box_pixels(self):
        with patch.object(model, "MAX_FEATURE_PIXELS", 1), self.assertRaisesRegex(ValueError, "pengukuran"):
            model.describe(picture())

    def test_cli_artifact_only_reads_supplied_file(self):
        path = Path(self.enterContext(TemporaryDirectory()))/"scene.pgm"
        data = picture()
        path.write_bytes(data)
        cmd = [sys.executable, "-m", "ace_perception.scene_describer", str(path), "--threshold", "30"]
        run = subprocess.run(cmd, capture_output=True, check=True)
        self.assertEqual(json.loads(run.stdout), model.describe(data, threshold=30))
        self.assertEqual(path.read_bytes(), data)
