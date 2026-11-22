"""Verifier kesamaan bentuk dengan kandidat kosong/ambigu."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _vision, stamp_reader as model


def mark(pattern):
    size = len(pattern)
    return _vision.encode(size+2, size+2, [255]*(size+2)+[
        pixel for line in pattern for pixel in ([255]+[0 if v=="1" else 255 for v in line]+[255])]+[255]*(size+2))


MATCH = mark(["11111","10001","10101","10001","11111"])
OTHER = mark(["00100","00100","11111","00100","00100"])


class StampTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))

    def template(self, key, data):
        path = f"{key}.pgm"
        (self.root/path).write_bytes(data)
        return {"id": key, "path": path, "sha256": sha256(data).hexdigest(), "bytes": len(data),
                "source_ref": f"fixture/{key}", "light_ink": False}

    def scan(self, target, templates):
        return model.read_stamp(target, self.root, model._canonical({
            "schema": "ace.perception-stamp-layout.v1", "box": [0,0,7,7],
            "expected_image_sha256": sha256(target).hexdigest(), "minimum_iou_bp": 9000,
            "minimum_margin_bp": 1000, "jitter": 1, "light_ink": False, "templates": templates}))

    def test_exact_stamp_compares_shapes_and_records_reference(self):
        report = self.scan(MATCH, [self.template("first",MATCH), self.template("different",OTHER)])
        self.assertEqual(report["status"], "shape_match")
        self.assertEqual(report["pattern_id"], "first")
        self.assertEqual(report["candidates"][0]["iou"], {"numerator": 1, "denominator": 1})
        self.assertEqual(report["candidates"][0]["source_ref"], "fixture/first")

    def test_equal_patterns_never_resolve_and_missing_shapes_are_empty(self):
        templates = [self.template("one",MATCH), self.template("two",MATCH)]
        self.assertEqual(self.scan(MATCH,templates)["status"], "ambiguous")
        self.assertEqual(self.scan(_vision.encode(7,7,[255]*49), templates)["status"], "empty")
