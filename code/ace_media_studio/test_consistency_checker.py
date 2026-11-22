from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from ._raster import Raster, blank, png
from .consistency_checker import compare


class ConsistencyTests(unittest.TestCase):
    def test_same_palette_does_not_hide_displaced_landmark(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = blank(20, 20, (25, 39, 120))
            pixels = bytearray(first.pixels)
            foreground = bytes((226, 180, 65))
            index = (10 * 20 + 10) * 3
            pixels[index:index + 3] = foreground
            reference = png(Raster(20, 20, bytes(pixels)))
            pixels[index:index + 3] = first.pixels[index:index + 3]
            pixels[-3:] = foreground
            changed = png(Raster(20, 20, bytes(pixels)))
            files = []
            for name, content in (("reference", reference), ("moved", changed)):
                (root / f"{name}.png").write_bytes(content)
                files.append({"path": f"{name}.png", "sha256": sha256(content).hexdigest()})
            plan = {"schema": "ace.media.consistency-plan.v1", "reference": files[0],
                    "variants": [files[0] | {"id": "intact"}, files[1] | {"id": "shift"}],
                    "palette_min_bp": 10000, "landmark_min_bp": 10000,
                    "landmarks": [{"id": "mark", "x_bp": 5500, "y_bp": 5500, "tolerance": 8}]}
            report = compare(plan, identity(plan), root)
            self.assertFalse(report["pass"])
            self.assertTrue(report["variants"][0]["pass"])
            self.assertEqual(report["variants"][1]["palette_overlap_bp"], 10000)
            self.assertEqual(report["variants"][1]["landmark_match_bp"], 0)
            self.assertFalse(report["variants"][1]["landmarks"][0]["pass"])
