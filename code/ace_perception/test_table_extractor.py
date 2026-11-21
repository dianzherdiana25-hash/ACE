"""Verifier grid raster, sel kosong, dan penahanan kolom bergeser."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import table_extractor as model
from ace_perception.test_ocr_engine import GLYPHS, font, raster
from ace_perception.test_screen_understanding import board, label


XS = (2, 27, 52)
YS = (2, 15, 28)
BOX = [2, 2, 53, 29]


def grid(*, vertical=True, horizontal=True, thickness=1):
    page = board(56, 34)
    x_bands = XS if vertical else (XS[0], XS[-1])
    y_bands = YS if horizontal else (YS[0], YS[-1])
    for top in y_bands:
        for y in range(top, top+thickness):
            for x in range(2, 52+thickness):
                page[y][x] = "1"
    for left in x_bands:
        for x in range(left, left+thickness):
            for y in range(2, 28+thickness):
                page[y][x] = "1"
    return page


def sample(*, polarity=False, unknown=False, vertical=True):
    page = grid(vertical=vertical)
    label(page, "HA", 5, 4)
    label(page, "T", 30, 4)
    alphabet = {**GLYPHS, "V": ["10101", "11111", "01110", "11111", "11111", "11111", "11111"]}
    label(page, "HV" if unknown else "OH", 5, 17, alphabet)
    return raster(page, polarity=polarity)


def layout(**changed):
    fields = {"schema": "ace.perception-table-layout.v1", "box": BOX, "expected_rows": 2,
              "expected_columns": 2, "light_ink": False, "separator_bp": 10_000, "word_gap": 4}
    return model._canonical({**fields, **changed})


class TableTests(unittest.TestCase):
    def test_each_cell_read_with_original_coordinates_and_empty_kept(self):
        image, templates, spec = sample(), font(), layout()
        product = model.extract(image, templates, spec)
        self.assertEqual(product["status"], "extracted")
        self.assertEqual(product["image_sha256"], sha256(image).hexdigest())
        self.assertEqual(product["font_sha256"], sha256(templates).hexdigest())
        self.assertEqual(product["layout_sha256"], sha256(spec).hexdigest())
        self.assertEqual((product["rows"], product["columns"]), (2, 2))
        self.assertEqual(product["horizontal_rulings"], [[2, 3], [15, 16], [28, 29]])
        self.assertEqual(product["vertical_rulings"], [[2, 3], [27, 28], [52, 53]])
        self.assertEqual([row["text"] for row in product["cells"]], ["HA", "T", "OH", None])
        self.assertEqual([(row["row"], row["column"]) for row in product["cells"]],
                         [(1, 1), (1, 2), (2, 1), (2, 2)])
        self.assertEqual(product["cells"][0]["box"], [3, 3, 27, 15])
        self.assertEqual(product["cells"][0]["glyphs"][0]["box"], [8, 5, 13, 12])
        self.assertEqual(product["cells"][-1]["status"], "empty")

    def test_filled_with_unresolved_chars_is_different_from_empty_cell(self):
        report = model.extract(sample(unknown=True), font(), layout())
        self.assertEqual(report["status"], "text_partial")
        self.assertEqual(report["reasons"], [])
        self.assertEqual(report["cells"][2]["status"], "partial")
        self.assertEqual(report["cells"][2]["glyphs"][1]["status"], "unresolved")
        self.assertEqual(report["cells"][3]["status"], "empty")
        self.assertIsNone(report["cells"][2]["text"])

    def test_missing_internal_rule_blocks_before_reading_merged_column(self):
        report = model.extract(sample(vertical=False), font(), layout())
        self.assertEqual(report["columns"], 1)
        self.assertEqual(report["status"], "grid_incomplete")
        self.assertEqual(report["reasons"], ["column_count_mismatch"])
        self.assertEqual(report["cells"], [])

    def test_missing_joint_differs_from_density_and_expected_partitions(self):
        page = grid()
        page[15][27] = "0"
        product = model.extract(raster(page), font(), layout(separator_bp=9000))
        self.assertEqual((product["rows"], product["columns"]), (2, 2))
        self.assertEqual(product["missing_joints"], 1)
        self.assertEqual(product["status"], "grid_incomplete")
        self.assertEqual(product["reasons"], ["unjoined_rulings"])
        self.assertEqual(product["cells"], [])

    def test_thick_lines_are_one_ruling_and_can_be_read_without_expected_counts(self):
        image = raster(grid(thickness=2))
        result = model.extract(image, font(), layout(box=[2, 2, 54, 30], expected_columns=None, expected_rows=None))
        self.assertEqual(result["horizontal_rulings"], [[2, 4], [15, 17], [28, 30]])
        self.assertEqual(result["vertical_rulings"], [[2, 4], [27, 29], [52, 54]])
        self.assertEqual((result["rows"], result["columns"]), (2, 2))
        self.assertEqual(result["status"], "extracted")
        self.assertTrue(all(row["status"] == "empty" for row in result["cells"]))

    def test_polarity_inverse_has_equal_grid_and_text(self):
        light = model.extract(sample(polarity=True), font(), layout(light_ink=True))
        dark = model.extract(sample(), font(), layout())
        self.assertNotEqual(light["image_sha256"], dark["image_sha256"])
        self.assertNotEqual(light["layout_sha256"], dark["layout_sha256"])
        self.assertEqual(light["cells"], dark["cells"])

    def test_uniform_pixels_remain_missing_rulings_even_with_null_shape(self):
        report = model.extract(raster(board(56, 34)), font(), layout(expected_rows=None, expected_columns=None))
        self.assertEqual(report["reasons"], ["missing_rulings"])
        self.assertEqual(report["status"], "grid_incomplete")
        self.assertEqual(report["horizontal_rulings"], [])
        self.assertIsNone(report["threshold"])
        self.assertEqual(report["cells"], [])

    def test_outer_crop_region_and_expected_dimensions_are_strict(self):
        image = sample()
        for changes in ({"box": [2, 2, 57, 34]}, {"box": None}, {"expected_rows": False},
                        {"expected_columns": 0}, {"separator_bp": 5999}, {"word_gap": False}, {"light_ink": 1},
                        {"schema": "wrong"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.extract(image, font(), layout(**changes))

    def test_rules_outside_declared_table_do_not_create_new_cells(self):
        page = grid()
        for x in range(len(page[0])):
            page[31][x] = "1"
        report = model.extract(raster(page), font(), layout())
        self.assertEqual(report["horizontal_rulings"], [[2, 3], [15, 16], [28, 29]])
        self.assertEqual(len(report["cells"]), 4)

    def test_cli_exit_codes_and_canonical_contents(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        image, types, spec = root/"table.pgm", root/"font.json", root/"layout.json"
        types.write_bytes(font())
        spec.write_bytes(layout())
        command = [sys.executable, "-m", "ace_perception.table_extractor", *map(str, (image, types, spec))]
        for source, expected in ((sample(), 0), (sample(unknown=True), 1), (sample(vertical=False), 1)):
            with self.subTest(expected=expected):
                image.write_bytes(source)
                run = subprocess.run(command, capture_output=True)
                self.assertEqual(run.returncode, expected)
                self.assertEqual(json.loads(run.stdout), model.extract(source, types.read_bytes(), spec.read_bytes()))
                self.assertEqual(image.read_bytes(), source)
        spec.write_bytes(b"{}")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_row_count_cannot_change_without_holding_cell_positions(self):
        report = model.extract(raster(grid(horizontal=False)), font(), layout())
        self.assertEqual(report["rows"], 1)
        self.assertEqual(report["columns"], 2)
        self.assertEqual(report["reasons"], ["row_count_mismatch"])
        self.assertEqual(report["cells"], [])

    def test_grid_budget_checks_before_ocr_for_large_contracts(self):
        from unittest.mock import patch

        image = sample()
        with patch.object(model, "MAX_CELLS", 3), self.assertRaisesRegex(ValueError, "Grid"):
            model.extract(image, font(), layout())
        with patch.object(model, "MAX_TABLE_PIXELS", 20), self.assertRaisesRegex(ValueError, "Plot"):
            model.extract(image, font(), layout())

    def test_wrong_polarity_does_not_return_table_from_known_rule_fixture(self):
        report = model.extract(sample(), font(), layout(light_ink=True))
        self.assertEqual(report["status"], "grid_incomplete")
        self.assertIn("missing_rulings", report["reasons"])
        self.assertEqual(report["cells"], [])

    def test_same_pixels_with_reencoded_layout_keep_results_and_separate_anchor(self):
        original = layout()
        rewritten = json.dumps(json.loads(original), indent=2).encode()
        data = sample()
        first, second = (model.extract(data, font(), spec) for spec in (original, rewritten))
        self.assertNotEqual(first["layout_sha256"], second["layout_sha256"])
        self.assertEqual(first["image_sha256"], second["image_sha256"])
        self.assertEqual(first["cells"], second["cells"])
        self.assertEqual(first["vertical_rulings"], second["vertical_rulings"])
