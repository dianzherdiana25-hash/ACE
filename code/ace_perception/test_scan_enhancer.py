"""Verifier kontras eksak, ambang lokal, dan perlindungan pindaian sumber."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ace_perception import _raster, _vision, scan_enhancer as model


def scan(width, height, values, maximum=255):
    return _vision.encode(width, height, values, maximum)


class EnhancementTests(unittest.TestCase):
    def test_grayscale_stretch_does_not_introduce_new_geometry(self):
        src = scan(3, 2, [32, 64, 96, 128, 160, 192])
        artifact, report = model.enhance(src, trim_bp=0, binary=False)
        self.assertEqual(_raster.decode(artifact).pixels, (0, 51, 102, 153, 204, 255))
        self.assertEqual(report["cutoffs_8bit"], [32, 192])
        self.assertEqual(report["size"], [3, 2])
        self.assertEqual(report["source_sha256"], sha256(src).hexdigest())
        self.assertEqual(report["output_sha256"], sha256(artifact).hexdigest())
        self.assertIsNone(report["ink_pixels"])
        self.assertFalse(report["binary_applied"])

    def test_flat_preserves_normalized_level_and_does_not_classify_all_as_ink(self):
        input_data = scan(2, 2, [40]*4, maximum=100)
        artifact, report = model.enhance(input_data)
        self.assertEqual(_raster.decode(artifact).pixels, (102,)*4)
        self.assertEqual(report["status"], "flat_percentiles")
        self.assertFalse(report["binary_applied"])
        self.assertIsNone(report["ink_pixels"])

    def test_trim_ignores_isolated_intensity_extremes(self):
        input_data = scan(10, 2, [0]+[10]*9+[20]*9+[255])
        artifact, report = model.enhance(input_data, trim_bp=1000, binary=False)
        self.assertEqual(report["cutoffs_8bit"], [10, 20])
        self.assertEqual(_raster.decode(artifact).pixels, (0,)*10+(255,)*10)

    def test_despeckle_removes_impulse_but_keeps_connected_thin_line(self):
        values = [200]*81
        for y in range(2, 6):
            values[y*9+2] = 60
        values[5*9+6] = 0
        cleaned, count = model._despeckle(values, 9, 9, 70)
        self.assertEqual(count, 1)
        self.assertEqual(cleaned[5*9+6], 200)
        self.assertEqual([cleaned[y*9+2] for y in range(2, 6)], [60]*4)
        self.assertEqual(values[5*9+6], 0)

    def test_adaptive_threshold_sees_left_and_right_strokes_under_gradient(self):
        w, h = 12, 8
        before = [100+8*x for _ in range(h) for x in range(w)]
        for y in range(2, 6):
            for x in (3, 8):
                before[y*w+x] -= 42
        source = scan(w, h, before)
        artifact, result = model.enhance(source, trim_bp=0, radius=1, offset=35)
        self.assertEqual(result["ink_pixels"], 8)
        pixels = _raster.decode(artifact).pixels
        self.assertEqual({(x, y) for y in range(h) for x in range(w) if not pixels[y*w+x]},
                         {(x, y) for x in (3, 8) for y in range(2, 6)})
        white = scan(w, h, [255-v for v in before])
        output, inverse = model.enhance(white, trim_bp=0, radius=1, offset=35, light_ink=True)
        self.assertEqual(artifact, output)
        self.assertNotEqual(inverse["source_sha256"], result["source_sha256"])

    def test_rejects_invalid_settings_and_work_is_bounded(self):
        data = scan(2, 2, [0, 0, 0, 255])
        for options in ({"noise_delta": 256}, {"radius": 0}, {"offset": True},
                        {"trim_bp": 2001}, {"light_ink": 1}, {"binary": None}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                model.enhance(data, **options)
        with patch.object(model, "MAX_SCAN_PIXELS", 3), self.assertRaisesRegex(ValueError, "terlalu besar"):
            model.enhance(data)

    def test_cli_produces_new_raster_and_rejects_overwrite(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        pic, out = folder/"before.pgm", folder/"after.pgm"
        data = scan(3, 2, [10, 20, 30, 40, 50, 60])
        pic.write_bytes(data)
        call = [sys.executable, "-m", "ace_perception.scan_enhancer", str(pic),
                "--output", str(out), "--grayscale-only"]
        process = subprocess.run(call, check=True, capture_output=True)
        artifact, expected = model.enhance(data, binary=False)
        self.assertEqual(out.read_bytes(), artifact)
        self.assertEqual(json.loads(process.stdout), expected)
        self.assertEqual(subprocess.run(call, capture_output=True).returncode, 2)
        self.assertEqual(pic.read_bytes(), data)
