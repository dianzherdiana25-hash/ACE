"""Verifier skor dua vote dan pemetaan boks sampai piksel tepi."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _raster, ocr_confidence_map as model
from ace_perception.test_ocr_engine import GLYPHS, canvas, font, raster


class ConfidenceMapTests(unittest.TestCase):
    def test_exact_glyph_contributes_its_area_across_multiple_tiles(self):
        source = raster(canvas(["HA"]))
        report = model.map_confidence(source, font(), tile_px=4, limit_bp=0)
        self.assertEqual(report["image_sha256"], sha256(source).hexdigest())
        self.assertEqual(report["metric"], "ocr_geometric_proximity")
        self.assertEqual(report["ocr_status"], "read")
        self.assertEqual(sum(row["scored_box_pixels"] for row in report["tiles"]), 70)
        self.assertEqual(sum(row["unresolved_box_pixels"] for row in report["tiles"]), 0)
        first = report["tiles"][0]
        self.assertEqual(first["box"], [0, 0, 4, 4])
        self.assertEqual(first["scored_box_pixels"], 3)
        self.assertEqual(first["mean_geometry_score_bp"], 10000)
        self.assertTrue(any(row["status"] == "empty" for row in report["tiles"]))

    def test_unknown_glyph_area_has_no_score_and_preview_distinguishes_empty(self):
        glyphs = {**GLYPHS, "V": ["10101", "11111", "01110", "11111", "11111", "11111", "11111"]}
        report = model.map_confidence(raster(canvas(["HV"], alphabet=glyphs)), font(), tile_px=4, limit_bp=0)
        unknown = report["glyphs"][1]
        self.assertIsNone(unknown["geometry_score_bp"])
        self.assertGreater(unknown["nearest_distance_bp"], 0)
        self.assertEqual(sum(row["unresolved_box_pixels"] for row in report["tiles"]), 35)
        artifact = _raster.decode(model.render_tile_raster(report))
        for tile, gray in zip(report["tiles"], artifact.pixels, strict=True):
            if tile["status"] in {"unresolved", "empty"}:
                self.assertEqual(gray, 0 if tile["status"] == "unresolved" else 255)

    def test_direct_vote_proxy_uses_worst_distance_and_separate_margin(self):
        raw = {"box": [0, 0, 4, 2], "status": "agreed",
               "pixel_vote": {"distance": 1, "maximum_distance": 5, "second_margin": 2},
               "projection_vote": {"distance": 1, "maximum_distance": 10, "second_margin": 1}}
        result = model._estimate(raw)
        self.assertEqual(result["geometry_score_bp"], 8000)
        self.assertEqual(result["minimum_alternative_margin_bp"], 1000)
        _, _, tiles = model._tile_map([result], 4, 2, 4, 8001)
        self.assertEqual(tiles[0]["status"], "low_geometry_score")
        self.assertEqual(tiles[0]["weak_box_pixels"], 8)
        self.assertEqual(tiles[0]["mean_geometry_score_bp"], 8000)

    def test_one_template_means_no_margin_and_bounds_checked(self):
        one = font({"A": GLYPHS["A"]})
        source = raster(canvas(["A"]))
        result = model.map_confidence(source, one)
        self.assertIsNone(result["glyphs"][0]["minimum_alternative_margin_bp"])
        with patch.object(model, "MAX_TILES", 1), self.assertRaisesRegex(ValueError, "tile"):
            model.map_confidence(source, one, tile_px=1)

    def test_preview_hash_and_readonly_source(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        scan, samples, preview = [folder/item for item in ("scan.pgm", "font.json", "preview.pgm")]
        data = raster(canvas(["HA"]))
        scan.write_bytes(data)
        samples.write_bytes(font())
        args = [sys.executable, "-m", "ace_perception.ocr_confidence_map", str(scan), str(samples),
                "--preview", str(preview), "--tile-px", "4"]
        result = subprocess.run(args, capture_output=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report["preview_sha256"], sha256(preview.read_bytes()).hexdigest())
        self.assertEqual(preview.read_bytes(), model.render_tile_raster(report))
        self.assertEqual(scan.read_bytes(), data)
