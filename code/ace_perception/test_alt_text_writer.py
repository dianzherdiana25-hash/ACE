"""Verifier alt text berbatas dari geometri raster yang sama."""
import unittest

from ace_perception import _vision, alt_text_writer as model, scene_describer
from ace_perception.test_scene_describer import picture


class AltTests(unittest.TestCase):
    def test_text_describes_known_regions_and_preserves_scene_hash(self):
        data = picture()
        report = model.write(data, maximum_chars=200, maximum_regions=3, threshold=30)
        scene = scene_describer.describe(data, threshold=30, maximum_regions=3)
        self.assertEqual(report["scene_sha256"], model._sha(scene))
        self.assertIn("wilayah mendatar gelap di kiri atas", report["alt_text"])
        self.assertIn("wilayah tegak gelap di tengah", report["alt_text"])
        self.assertEqual(report["regions"][0]["box"], [1, 1, 7, 3])
        self.assertEqual(report["characters"], len(report["alt_text"]))
        self.assertEqual(report["regions_not_in_text"], 0)

    def test_limit_and_empty_are_visible_without_false_claim(self):
        report = model.write(picture(), maximum_chars=32, maximum_regions=1)
        self.assertLessEqual(report["characters"], 32)
        self.assertEqual(report["regions_not_in_text"], 3)
        blank = _vision.encode(2, 2, bytes([30]*4))
        empty = model.write(blank)
        self.assertEqual(empty["regions"], [])
        self.assertIn("Tidak ada wilayah terdeteksi", empty["alt_text"])
