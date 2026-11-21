"""Verifier geometri antarmuka sintetis, label dan koordinat asli."""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import screen_understanding as model
from ace_perception.test_ocr_engine import GLYPHS, canvas, font, raster


def board(width=64, height=34):
    return [["0"]*width for _ in range(height)]


def rectangle(page, box, *, filled=False):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            if filled or x in (x0, x1-1) or y in (y0, y1-1):
                page[y][x] = "1"


def label(page, text, x0, y0, alphabet=None):
    for y, band in enumerate(canvas([text], alphabet=alphabet), y0):
        for x, value in enumerate(band, x0):
            if value == "1":
                page[y][x] = "1"


def fixture(*, light=False):
    page = board()
    rectangle(page, (2, 2, 61, 31))
    rectangle(page, (5, 7, 30, 20))
    rectangle(page, (36, 8, 56, 22))
    label(page, "HA", 7, 9)
    return raster(page, polarity=light)


class ScreenUnderstandingTests(unittest.TestCase):
    def test_container_children_and_control_label_positions(self):
        scan = fixture()
        data = font()
        report = model.inspect(scan, data)
        self.assertEqual(report["image_sha256"], sha256(scan).hexdigest())
        self.assertEqual(report["font_sha256"], sha256(data).hexdigest())
        frame, button, placeholder = report["elements"]
        self.assertEqual((frame["id"], frame["kind"], frame["parent"]), ("e1", "container", None))
        self.assertEqual(frame["label"]["status"], "contains_regions")
        self.assertEqual((button["id"], button["kind"], button["parent"]), ("e2", "labeled_control_candidate", "e1"))
        self.assertEqual(button["label"]["text"], "HA")
        self.assertEqual(button["label"]["glyphs"][0]["box"], [10, 10, 15, 17])
        self.assertEqual(button["box"], [5, 7, 30, 20])
        self.assertEqual(button["border_pixels"], 72)
        self.assertEqual(button["perimeter_pixels"], 72)
        self.assertEqual(placeholder["kind"], "frame")
        self.assertEqual(placeholder["label"]["status"], "empty")

    def test_inverting_raster_preserves_elements_when_polarity_is_declared(self):
        first = model.inspect(fixture(), font())
        reverse = model.inspect(fixture(light=True), font(), light_ink=True)
        self.assertNotEqual(first["image_sha256"], reverse["image_sha256"])
        self.assertEqual(first["elements"], reverse["elements"])

    def test_non_rectangular_and_filled_components_not_frames(self):
        page = board()
        rectangle(page, (3, 4, 20, 20), filled=True)
        for offset in range(12):
            page[8+offset][30+offset] = "1"
            page[8+offset][31+offset] = "1"
        self.assertEqual(model.inspect(raster(page), font())["elements"], [])

    def test_partial_border_accepted_only_above_threshold(self):
        page = board()
        rectangle(page, (3, 4, 20, 21))
        page[4][5] = "0"
        scan = raster(page)
        self.assertEqual(model.inspect(scan, font(), min_border_bp=10_000)["elements"], [])
        found = model.inspect(scan, font(), min_border_bp=9800)["elements"]
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["border_pixels"], found[0]["perimeter_pixels"]), (63, 64))

    def test_small_components_and_unknown_glyph_no_claimed_control_label(self):
        page = board()
        rectangle(page, (2, 4, 8, 8))
        rectangle(page, (16, 5, 40, 19))
        alphabet = {**GLYPHS, "V": ["10101", "11111", "01110", "11111", "11111", "11111", "11111"]}
        label(page, "HV", 18, 8, alphabet)
        row, = model.inspect(raster(page), font())["elements"]
        self.assertEqual(row["kind"], "frame")
        self.assertEqual(row["label"]["status"], "partial")
        self.assertIsNone(row["label"]["text"])
        self.assertEqual(row["label"]["glyphs"][1]["status"], "unresolved")

    def test_child_selects_immediate_enclosing_frame(self):
        page = board()
        for box in ((1, 1, 58, 33), (4, 4, 45, 30), (7, 7, 25, 22)):
            rectangle(page, box)
        elements = model.inspect(raster(page), font())["elements"]
        self.assertEqual([(row["id"], row["parent"]) for row in elements], [("e1", None), ("e2", "e1"), ("e3", "e2")])

    def test_uniform_image_and_invalid_geometry_inputs(self):
        self.assertEqual(model.inspect(raster(board()), font())["elements"], [])
        for changes in ({"min_border_bp": 0}, {"min_border_bp": True}, {"min_span": 2},
                        {"min_span": 1025}, {"word_gap": 0}, {"light_ink": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.inspect(fixture(), font(), **changes)

    def test_cli_stable_pixel_report_without_changing_input(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        image, glyphs = root / "screen.pgm", root / "font.json"
        image.write_bytes(fixture())
        glyphs.write_bytes(font())
        before = image.read_bytes()
        command = [str(image), str(glyphs)]
        for index in range(2):
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main(command), 0)
            actual = output.getvalue()
            self.assertEqual(json.loads(actual), model.inspect(before, glyphs.read_bytes()))
            if index:
                self.assertEqual(actual, earlier)
            earlier = actual
        self.assertEqual(image.read_bytes(), before)

    def test_four_connectivity_does_not_join_marks_across_row_edges(self):
        components = list(model._components([False, False, True, True, False, False], 3))
        self.assertEqual(components, [((2, 0, 3, 1), 1), ((0, 1, 1, 2), 1)])

    def test_content_without_a_frame_is_not_relabelled_as_a_clickable_element(self):
        page = board()
        label(page, "HOT", 5, 5)
        self.assertEqual(model.inspect(raster(page), font())["elements"], [])
