"""Verifier label fisik, bentuk nilai, dan checkbox yang meragukan."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import form_reader as model
from ace_perception.test_document_extractor import FULL
from ace_perception.test_ocr_engine import font, raster
from ace_perception.test_screen_understanding import board, label, rectangle


CHECK = (26, 29, 36, 39)


def field(key, expected, top, kind="text", required=True):
    value = list(CHECK) if kind == "checkbox" else [25, top, 50, top+11]
    return {"id": key, "expected_label": expected, "label_box": [2, top, 23, top+11],
            "value_box": value, "type": kind, "required": required}


def spec(fields=None, **changed):
    if fields is None:
        fields = [field("tag", "ha", 3), field("number", "H", 15, "digits"), field("flag", "T", 27, "checkbox")]
    return model._canonical({"schema": "ace.perception-form-layout.v1", "form_ref": "fixture/form",
                             "light_ink": False, "word_gap": 4, "border_bp": 10000, "unchecked_max_bp": 0,
                             "checked_min_bp": 1500, "fields": fields, **changed})


def fixture(*, mark=14, outline=True, number="024", polarity=False, tag="HA"):
    out = board(56, 43)
    label(out, tag, 3, 5)
    label(out, "HOT", 25, 5)
    label(out, "H", 3, 17)
    label(out, number, 25, 17, FULL)
    label(out, "T", 3, 29)
    if outline:
        rectangle(out, CHECK)
    for index in range(mark):
        out[CHECK[1]+1+index//8][CHECK[0]+1+index%8] = "1"
    return raster(out, polarity=polarity)


class FormTests(unittest.TestCase):
    def test_independently_read_labels_text_digits_and_checkbox(self):
        image, data, layout = fixture(), font(FULL), spec()
        result = model.extract(image, data, layout)
        self.assertEqual(result["status"], "extracted")
        self.assertEqual(result["form_ref"], "fixture/form")
        self.assertEqual(result["image_sha256"], sha256(image).hexdigest())
        self.assertEqual(result["font_sha256"], sha256(data).hexdigest())
        self.assertEqual(result["layout_sha256"], sha256(layout).hexdigest())
        self.assertEqual(result["required_open"], [])
        one, two, three = result["fields"]
        self.assertEqual([row["value"] for row in result["fields"]], ["HOT", "024", True])
        self.assertEqual(one["label"]["text"], "HA")
        self.assertEqual(one["label"]["glyphs"][0]["box"], [6, 6, 11, 13])
        self.assertEqual(two["value_evidence"]["box"], [25, 15, 50, 26])
        self.assertEqual(three["value_evidence"]["marked_pixels"], 14)
        self.assertEqual(three["value_evidence"]["border_pixels"], 36)

    def test_false_requires_an_outline_missing_checkbox_never_false(self):
        for outlined, expected in ((True, False), (False, None)):
            scan = fixture(mark=0, outline=outlined)
            result = model.extract(scan, font(FULL), spec())
            flag = result["fields"][-1]
            with self.subTest(outlined=outlined):
                self.assertEqual(flag["value"], expected)
                self.assertEqual(flag["value_evidence"]["status"], "read" if outlined else "missing_outline")
                self.assertEqual(result["required_open"], [] if outlined else ["flag"])

    def test_weak_mark_and_wrong_label_do_not_emit_value(self):
        result = model.extract(fixture(mark=2, tag="OH"), font(FULL), spec())
        self.assertEqual(result["required_open"], ["tag", "flag"])
        first, _, last = result["fields"]
        self.assertEqual(first["label"]["status"], "label_mismatch")
        self.assertEqual(first["value_evidence"]["text"], "HOT")
        self.assertIsNone(first["value"])
        self.assertEqual(last["value_evidence"]["status"], "ambiguous_mark")
        self.assertIsNone(last["value"])

    def test_optional_field_validation_and_leading_zero_kept(self):
        scan = fixture(number="OH", mark=0)
        fields = [field("number", "H", 15, "digits", required=False)]
        report = model.extract(scan, font(FULL), spec(fields))
        self.assertEqual(report["status"], "extracted")
        item, = report["fields"]
        self.assertEqual(item["status"], "unresolved")
        self.assertIsNone(item["value"])
        self.assertEqual(item["value_evidence"]["status"], "invalid_digits")

    def test_polarity_inversion_preserves_form_values(self):
        dark = model.extract(fixture(), font(FULL), spec())
        light = model.extract(fixture(polarity=True), font(FULL), spec(light_ink=True))
        self.assertEqual(dark["fields"], light["fields"])
        self.assertNotEqual(dark["image_sha256"], light["image_sha256"])

    def test_intersecting_regions_rejected_within_or_between_fields(self):
        raw = [field("first", "HA", 3), field("second", "H", 15)]
        raw[1]["label_box"] = [22, 8, 30, 18]
        with self.assertRaisesRegex(ValueError, "beririsan"):
            model.extract(fixture(), font(FULL), spec(raw))
        item = field("single", "H", 15)
        item["value_box"] = item["label_box"]
        with self.assertRaisesRegex(ValueError, "beririsan"):
            model.extract(fixture(), font(FULL), spec([item]))

    def test_bad_config_or_outside_coordinates_fail_before_pairs(self):
        for changes in ({"checked_min_bp": 0}, {"unchecked_max_bp": True}, {"light_ink": 1},
                        {"border_bp": 10001}, {"word_gap": 0}, {"schema": "wrong"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.extract(fixture(), font(FULL), spec(**changes))
        row = field("outside", "HA", 3)
        row["label_box"] = [2, 3, 999, 14]
        with self.assertRaisesRegex(ValueError, "di luar raster"):
            model.extract(fixture(), font(FULL), spec([row]))

    def test_all_inputs_cli_exit_when_required_box_is_missing(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        scan, glyphs, layout = root/"f.pgm", root/"glyphs.json", root/"form.json"
        glyphs.write_bytes(font(FULL))
        layout.write_bytes(spec())
        command = [sys.executable, "-m", "ace_perception.form_reader", *map(str, (scan, glyphs, layout))]
        for payload, code in ((fixture(), 0), (fixture(mark=0, outline=False), 1)):
            scan.write_bytes(payload)
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, code)
            self.assertEqual(json.loads(result.stdout), model.extract(payload, glyphs.read_bytes(), layout.read_bytes()))
            self.assertEqual(scan.read_bytes(), payload)

    def test_box_mark_at_exact_boundary_is_selected(self):
        report = model.extract(fixture(mark=16), font(FULL), spec(checked_min_bp=2500))
        self.assertIs(report["fields"][-1]["value"], True)
        report = model.extract(fixture(mark=15), font(FULL), spec(checked_min_bp=2500))
        self.assertEqual(report["fields"][-1]["value_evidence"]["status"], "ambiguous_mark")
        self.assertIsNone(report["fields"][-1]["value"])

    def test_blank_form_cannot_get_value_from_expected_label_alone(self):
        empty = raster(board(56, 43))
        result = model.extract(empty, font(FULL), spec())
        self.assertEqual(result["required_open"], ["tag", "number", "flag"])
        self.assertTrue(all(item["value"] is None for item in result["fields"]))
        self.assertEqual([item["label"]["status"] for item in result["fields"]], ["empty"]*3)
        self.assertEqual(result["fields"][-1]["value_evidence"]["status"], "missing_outline")

    def test_checkbox_geometry_requires_nonempty_interior(self):
        item = field("flag", "T", 27, "checkbox")
        item["value_box"] = [26, 29, 28, 31]
        with self.assertRaisesRegex(ValueError, "interior"):
            model.extract(fixture(), font(FULL), spec([item]))
