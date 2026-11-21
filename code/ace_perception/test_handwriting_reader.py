"""Verifier variasi glyph, pemisahan penulis, dan jarak tulisan tangan."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import handwriting_reader as model
from ace_perception.test_ocr_engine import GLYPHS, raster
from ace_perception.test_screen_understanding import board


ALT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "H": ["10001", "10001", "11111", "10001", "10001", "10001", "10001"],
}
RANGES = [("first", [2, 2, 13, 13]), ("second", [17, 2, 27, 13]), ("empty", [31, 2, 41, 13])]


def write_glyph(page, x, y, bits):
    for offset, row in enumerate(bits):
        for column, item in enumerate(row):
            if item == "1":
                page[y+offset][x+column] = "1"


def templates():
    return [{"character": char, "writer_code": writer, "receipt_ref": f"fixture/example/{char}/{writer}", "grid": glyphs[char]}
            for writer, glyphs in (("code-1", GLYPHS), ("code-2", ALT), ("excluded", GLYPHS)) for char in ("A", "H")]


def encode(records):
    return model._canonical({"schema": "ace.handwriting-examples.v1", "examples": records})


def layout(example_bytes, **changes):
    raw = {"schema": "ace.handwriting-cells.v1", "template_sha256": sha256(example_bytes).hexdigest(), "light_ink": False,
           "minimum_writers": 2, "distance_bp": 1800, "margin_bp": 200, "exclude_writer_code": "excluded",
           "cells": [{"id": key, "box": box[:]} for key, box in RANGES]}
    return model._canonical({**raw, **changes})


def fixture(*, light=False):
    page = board(43, 15)
    write_glyph(page, 4, 4, ALT["A"])
    write_glyph(page, 19, 4, GLYPHS["H"])
    return raster(page, polarity=light)


class HandwritingTests(unittest.TestCase):
    def test_shape_variations_resolve_from_two_distinct_writer_codes(self):
        image, data = fixture(), encode(templates())
        spec = layout(data)
        result = model.read_cells(image, data, spec)
        self.assertEqual(result["text"], "AH\ufffd")
        self.assertEqual(result["image_sha256"], sha256(image).hexdigest())
        self.assertEqual(result["layout_sha256"], sha256(spec).hexdigest())
        first, second, empty = result["cells"]
        self.assertEqual((first["id"], first["box"], first["status"]), ("first", RANGES[0][1], "read"))
        self.assertEqual({row["writer_code"] for row in first["candidates"][0]["evidence"]}, {"code-1", "code-2"})
        self.assertEqual(first["candidates"][0]["evidence"][0]["receipt_ref"], "fixture/example/A/code-2")
        self.assertEqual(second["candidates"][0]["label"], "H")
        self.assertEqual(empty["status"], "empty")
        self.assertEqual(empty["candidates"], [])

    def test_repeated_examples_from_same_writer_do_not_satisfy_minimum(self):
        source = [row for row in templates() if row["writer_code"] == "code-1"]
        source += [{**row, "receipt_ref": row["receipt_ref"] + "/copy"} for row in source]
        data = encode(source)
        result = model.read_cells(fixture(), data, layout(data))
        self.assertEqual(result["text"], "\ufffd\ufffd\ufffd")
        self.assertEqual(result["cells"][0]["status"], "no_writer_support")

    def test_margin_ties_and_distance_are_different_abstentions(self):
        records = templates()
        for row in records:
            row["grid"] = ALT["A"]
        data = encode(records)
        result = model.read_cells(fixture(), data, layout(data, distance_bp=10_000))
        self.assertEqual(result["cells"][0]["status"], "ambiguous")
        self.assertIsNone(result["cells"][0]["character"])
        self.assertEqual([row["distance_bp"] for row in result["cells"][0]["candidates"]], [0, 0])
        result = model.read_cells(fixture(), data, layout(data, distance_bp=0))
        self.assertEqual(result["cells"][1]["status"], "too_far")

    def test_polarity_inverse_preserves_readings(self):
        data = encode(templates())
        dark = model.read_cells(fixture(), data, layout(data))
        light = model.read_cells(fixture(light=True), data, layout(data, light_ink=True))
        self.assertEqual(light["cells"], dark["cells"])
        self.assertNotEqual(light["image_sha256"], dark["image_sha256"])

    def test_anchor_and_bad_coordinates_fail_before_assigning_letters(self):
        original = encode(templates())
        with self.assertRaisesRegex(ValueError, "hash roster"):
            model.read_cells(fixture(), original+b" ", layout(original))
        for changes in ({"cells": [{"id": "outside", "box": [0, 0, 45, 12]}]}, {"margin_bp": True},
                        {"minimum_writers": 0}, {"light_ink": 1}, {"cells": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.read_cells(fixture(), original, layout(original, **changes))

    def test_banded_warp_prefers_near_profiles_and_is_symmetric(self):
        centered = [0, 0, 0, 4, 8, 12, 8, 4, 0, 0, 0, 0]
        shifted = [0, 0, 4, 8, 12, 8, 4, 0, 0, 0, 0, 0]
        self.assertEqual(model._warp(centered, centered), 0)
        self.assertEqual(model._warp(centered, shifted), model._warp(shifted, centered))
        self.assertLess(model._warp(centered, shifted), model._warp(centered, [12]*12))

    def test_cli_preserves_existing_scan_and_provenance(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        source, samples, spec = root/"scan.pgm", root/"examples.json", root/"boxes.json"
        source.write_bytes(fixture())
        data = encode(templates())
        samples.write_bytes(data)
        spec.write_bytes(layout(data))
        command = [sys.executable, "-m", "ace_perception.handwriting_reader", *map(str, (source, samples, spec))]
        process = subprocess.run(command, capture_output=True)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(json.loads(process.stdout), model.read_cells(fixture(), data, spec.read_bytes()))
        self.assertEqual(source.read_bytes(), fixture())
