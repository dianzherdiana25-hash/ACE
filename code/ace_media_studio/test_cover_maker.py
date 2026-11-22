from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .cover_maker import make_cover


def cover_plan():
    return {"schema": "ace.media.cover-plan.v1", "id": "fixture", "source_ref": "fixture:visual",
            "title": "CATATAN CAHAYA", "background": "#202038", "accent": "#3060A0",
            "foreground": "#F0E0C0", "width": 160, "height": 96, "minimum_contrast_milli": 4500}


class CoverTests(unittest.TestCase):
    def test_cover_typography_measured_from_rendered_raster(self):
        plan = cover_plan()
        data, report = make_cover(plan, identity(plan))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["image_sha256"], sha256(data).hexdigest())
        self.assertEqual(" ".join(row["line"] for row in report["layout"]), "CATATAN CAHAYA")
        image = raster(data)
        for item in report["measurements"]["text_regions"]:
            self.assertGreaterEqual(item["contrast_milli"], 4500)
            self.assertEqual(image.at(*item["ink"][:2]), (240, 224, 192))
        self.assertEqual(image.at(0, 95), (48, 96, 160))

    def test_low_contrast_and_unsupported_letters_fail_closed(self):
        plan = cover_plan()
        plan["foreground"] = "#21213A"
        _, report = make_cover(plan, identity(plan))
        self.assertEqual(report["status"], "hold")
        self.assertTrue(any(not row["pass"] for row in report["measurements"]["text_regions"]))
        plan["title"] = "♫"
        with self.assertRaisesRegex(ContractError, "ditata"):
            make_cover(plan, identity(plan))
