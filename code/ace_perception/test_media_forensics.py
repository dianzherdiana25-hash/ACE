"""Verifier petunjuk numerik raster dan perbandingan rujukan tertambat."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _vision, media_forensics as model


def pgm(rows):
    return _vision.encode(len(rows[0]), len(rows), [value for row in rows for value in row])


class MediaForensicsTests(unittest.TestCase):
    def test_periodic_seams_and_repeated_tiles_are_observations_only(self):
        image = pgm([[50, 50, 150, 150, 50, 50, 150, 150],
                     [80, 80, 185, 185, 80, 80, 185, 185]]*2)
        report = model.inspect(image, block=2)
        self.assertEqual(report["provenance"], "unknown")
        self.assertEqual(report["quantization_levels_8bit"], 4)
        self.assertEqual(report["findings"], [{"kind": "grid_seam", "axis": "x"}, {"kind": "repeated_textured_tiles"}])
        x, y = report["seams"]
        self.assertEqual(x["boundary_minus_other_mean"], {"numerator": 205, "denominator": 2})
        self.assertFalse(y["flagged"])
        self.assertEqual(report["repetition"]["textured_tiles"], 8)
        self.assertEqual(report["repetition"]["repeat_groups"], 2)
        self.assertEqual(report["repetition"]["repeated_beyond_first"], 6)
        self.assertEqual(len(report["repetition"]["examples"][0]["boxes"]), 3)

    def test_flat_tiles_are_excluded_and_tiny_axis_marked_unmeasured(self):
        image = pgm([[255, 255], [255, 255]])
        response = model.inspect(image, block=4)
        self.assertEqual(response["findings"], [])
        self.assertEqual(response["saturated_pixels"], 4)
        self.assertEqual(response["repetition"]["textured_tiles"], 0)
        self.assertTrue(all(item["boundary_minus_other_mean"] is None for item in response["seams"]))

    def test_anchored_reference_proves_only_exact_pixel_differences(self):
        before = pgm([[10, 50], [80, 100]])
        after = pgm([[10, 70], [80, 0]])
        key = sha256(before).hexdigest()
        result = model.inspect(after, reference=before, reference_sha256=key)
        self.assertEqual(result["reference_comparison"], {
            "sha256": key, "changed_pixels": 2, "mean_absolute_difference": {"numerator": 30, "denominator": 1}})
        self.assertEqual(result["provenance"], "unknown")
        with self.assertRaisesRegex(ValueError, "berbeda"):
            model.inspect(after, reference=before, reference_sha256="0"*64)
        with self.assertRaisesRegex(ValueError, "perlu"):
            model.inspect(after, reference_sha256=key)
        with self.assertRaisesRegex(ValueError, "berukuran"):
            model.inspect(pgm([[10]]), reference=before, reference_sha256=key)

    def test_cli_does_not_modify_evidence_and_report_is_canonical(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        image = folder/"source.pgm"
        payload = pgm([[0, 20, 120], [40, 50, 255]])
        image.write_bytes(payload)
        args = [sys.executable, "-m", "ace_perception.media_forensics", str(image), "--block", "2"]
        run = subprocess.run(args, capture_output=True, check=True)
        self.assertEqual(json.loads(run.stdout), model.inspect(payload, block=2))
        self.assertEqual(image.read_bytes(), payload)
