"""Verifier ukuran bounded, rata-rata area, dan gate OCR lean."""
import unittest

from ace_perception import _raster, _vision, lean_perception as model
from ace_perception.test_ocr_engine import canvas, font, raster


class LeanTests(unittest.TestCase):
    def test_exact_average_covers_every_source_pixel_with_even_budget(self):
        src = _vision.encode(4, 4, [0, 4, 10, 14, 8, 12, 18, 22, 30, 34, 40, 44, 38, 42, 48, 52])
        payload, report = model.resize(src, maximum_pixels=4)
        self.assertEqual(report["output_size"], [2, 2])
        self.assertEqual(_raster.decode(payload).pixels, (6, 16, 36, 46))
        self.assertEqual(model._size(100, 40, 40, 50), (12, 4))
        self.assertEqual(model._size(1, 10000, 100, 1), (1, 1))

    def test_retention_guard_accepts_identity_and_refuses_overreduction(self):
        src = raster(canvas(["HAT"]))
        output, good = model.resize(src, font=font(), maximum_ocr_edits=0)
        self.assertIsNotNone(output)
        self.assertEqual(good["ocr_guard"]["edits"], 0)
        held, response = model.resize(src, maximum_pixels=1, font=font(), maximum_ocr_edits=0)
        self.assertIsNone(held)
        self.assertEqual(response["status"], "held")
        self.assertIsNone(response["ocr_guard"]["edits"])
        with self.assertRaisesRegex(ValueError, "sekaligus"):
            model.resize(src, maximum_ocr_edits=0)
