"""Verifier bentuk plat sintetis, hash, dan mode privasi."""
from hashlib import sha256
import unittest

from ace_perception import plate_reader as model
from ace_perception.test_document_extractor import FULL, image
from ace_perception.test_ocr_engine import font


def group(kind, minimum, maximum):
    return {"kind": kind, "min": minimum, "max": maximum}


def policy(scan, **changes):
    from ace_perception import _raster
    base = _raster.decode(scan)
    return model._canonical({"schema": "ace.perception-plate-layout.v1", "word_gap": 4, "light_ink": False,
                             "patterns": [{"id": "fixture-lpd", "source_ref": "fixture/plate-format",
                                           "groups": [group("letter", 1, 2), group("digit", 2, 4), group("letter", 1, 3)]}],
                             "zones": [{"id": "a", "pattern": "fixture-lpd", "box": [0, 0, base.width, base.height]}],
                             **changes})


class PlateTests(unittest.TestCase):
    def test_only_matching_plate_is_revealed_after_explicit_request(self):
        scan = image("HA 024 T")
        plain = model.read_plates(scan, font(FULL), policy(scan), reveal=True)
        hidden = model.read_plates(scan, font(FULL), policy(scan))
        first, second = plain["zones"][0], hidden["zones"][0]
        self.assertEqual(plain["image_sha256"], sha256(scan).hexdigest())
        self.assertEqual(first["status"], "verified_format")
        self.assertEqual(first["plate"], "HA 024 T")
        self.assertEqual(first["pattern_ref"], "fixture/plate-format")
        self.assertEqual(first["glyph_count"], 6)
        self.assertEqual(second["status"], "verified_format")
        self.assertIsNone(second["plate"])
        self.assertNotIn("HA 024 T", model._canonical(hidden).decode())

    def test_shape_rejects_letters_in_number_group_and_extra_line(self):
        for scan in (image("HA OH T"), image("H 02 T", "H 02 T")):
            with self.subTest(scan_size=len(scan)):
                result = model.read_plates(scan, font(FULL), policy(scan), reveal=True)["zones"][0]
                self.assertEqual(result["status"], "format_mismatch")
                self.assertIsNone(result["plate"])

    def test_bounded_geometry_unknown_pattern_and_wrong_reveal_type(self):
        scan = image("H 02 A")
        with self.assertRaisesRegex(ValueError, "boolean"):
            model.read_plates(scan, font(FULL), policy(scan), reveal=1)
        for zone in ({"id": "x", "pattern": "unknown", "box": [0, 0, 1, 1]},
                     {"id": "x", "pattern": "fixture-lpd", "box": [0, 0, 999, 999]}):
            with self.subTest(zone=zone), self.assertRaises(ValueError):
                model.read_plates(scan, font(FULL), policy(scan, zones=[zone]))
