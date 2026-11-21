"""Verifier klaim terstruktur dari raster, termasuk ketidakpastian."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import document_extractor as model
from ace_perception.test_ocr_engine import GLYPHS, canvas, font, raster


NUMBERS = {
    "0": ["11111", "10001", "10011", "10101", "11001", "10001", "11111"],
    "1": ["01100", "11100", "01100", "01100", "01100", "01100", "11111"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "10001", "01110"],
    "6": ["00111", "01000", "10000", "11110", "10001", "10001", "01110"],
    "-": ["00000", "00000", "00000", "01110", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00000", "00100"],
}
FULL = {**GLYPHS, **NUMBERS}


def field(key, prefix, kind="text", zone=None, required=True):
    return {"id": key, "prefix": prefix, "type": kind, "box": zone, "required": required}


def layout(*fields):
    return json.dumps({"schema": "ace.perception-layout.v1", "document_kind": "fixture_form", "fields": list(fields)}).encode()


def image(*lines, alphabet=FULL):
    return raster(canvas(lines, alphabet=alphabet))


def classify(result):
    return {row["id"]: row for row in result["claims"]}


class DocumentTests(unittest.TestCase):
    def test_four_typed_claims_from_same_raster_with_exact_provenance(self):
        scan = image("HA HOT", "A 24", "H -5.40", "T 2026-04-15")
        index = layout(field("subject", "HA "), field("count", "A ", "integer"),
                       field("amount", "H ", "decimal"), field("date", "T ", "iso_date"))
        templates = font(FULL)
        report = model.extract(scan, templates, index)
        claims = classify(report)
        self.assertEqual(report["status"], "extracted")
        self.assertEqual(report["ocr_status"], "read")
        self.assertEqual(report["required_open"], [])
        self.assertEqual(report["image_sha256"], sha256(scan).hexdigest())
        self.assertEqual(report["layout_sha256"], sha256(index).hexdigest())
        self.assertEqual(report["font_sha256"], sha256(templates).hexdigest())
        self.assertEqual(claims["subject"]["value"], "HOT")
        self.assertEqual(claims["count"]["value"], 24)
        self.assertEqual(claims["amount"]["value"], {"unscaled": -540, "scale": 2})
        self.assertEqual(claims["date"]["value"], "2026-04-15")
        self.assertEqual(claims["subject"]["evidence"], [{"line": 1, "box": [3, 1, 35, 8]}])
        self.assertEqual(claims["date"]["evidence"][0]["line"], 4)

    def test_duplicate_lines_even_with_equal_values_leave_claim_ambiguous(self):
        scan = image("HA HOT", "HA HOT")
        claim, = model.extract(scan, font(FULL), layout(field("subject", "HA ")))["claims"]
        self.assertEqual(claim["status"], "ambiguous")
        self.assertIsNone(claim["value"])
        self.assertEqual([row["line"] for row in claim["evidence"]], [1, 2])

    def test_zone_restricts_to_one_full_line(self):
        scan = image("HA HOT", "HA OH")
        index = layout(field("upper", "HA ", zone=[0, 0, 36, 8]),
                       field("lower", "HA ", zone=[0, 9, 36, 18]),
                       field("clipped", "HA ", zone=[4, 0, 36, 8], required=False))
        result = model.extract(scan, font(FULL), index)
        claims = classify(result)
        self.assertEqual(result["status"], "extracted")
        self.assertEqual(claims["upper"]["value"], "HOT")
        self.assertEqual(claims["lower"]["value"], "OH")
        self.assertEqual(claims["clipped"]["status"], "missing")

    def test_uncertain_prefix_or_value_never_produces_a_claim(self):
        altered = {**FULL, "V": ["10101", "11111", "01110", "11111", "11111", "11111", "11111"]}
        for text in ("HV HOT", "HA HV"):
            scan = image(text, alphabet=altered)
            result = model.extract(scan, font(FULL), layout(field("subject", "HA ")))
            with self.subTest(text=text):
                self.assertEqual(result["required_open"], ["subject"])
                self.assertEqual(result["claims"][0]["status"], "unresolved_ocr")
                self.assertIsNone(result["claims"][0]["value"])
                self.assertEqual(result["claims"][0]["evidence"][0]["line"], 1)

    def test_bad_calendar_number_and_missing_are_distinct(self):
        scan = image("T 2026-04-44", "A HOT")
        cases = layout(field("date", "T ", "iso_date"), field("amount", "A ", "integer"),
                       field("optional", "OH ", required=False))
        result = model.extract(scan, font(FULL), cases)
        self.assertEqual(result["required_open"], ["date", "amount"])
        self.assertEqual([row["status"] for row in result["claims"]], ["invalid_value", "invalid_value", "missing"])
        self.assertTrue(all(row["value"] is None for row in result["claims"]))

    def test_decimal_has_exact_scale_without_float_round_off(self):
        for source, expected in (("0.00", {"unscaled": 0, "scale": 2}),
                                 ("-15,41", {"unscaled": -1541, "scale": 2}),
                                 ("+10.400", {"unscaled": 10400, "scale": 3}),
                                 ("123.4567", {"unscaled": 1234567, "scale": 4})):
            with self.subTest(source=source):
                self.assertEqual(model._value("decimal", source), expected)
        for source in ("1e2", "1,051.48", "10.", " 1.2", ".4", "--1.1", "1.2222222"):
            with self.subTest(source=source):
                self.assertIsNone(model._value("decimal", source))

    def test_no_out_of_raster_zone_or_duplicate_id_is_accepted(self):
        scan = image("HA HOT")
        for rules in ([field("name", "HA ", zone=[0, 0, 1000, 1000])],
                      [field("name", "HA ", zone=[0, 0, True, 5])],
                      [field("name", "HA "), field("name", "A ")],
                      [field("name", "HA", required=1)], []):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                model.extract(scan, font(FULL), layout(*rules))

    def test_cli_exit_codes_and_hash_for_exact_ocr_extraction(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        scan, glyphs, spec = [root / name for name in ("scan.pgm", "font.json", "layout.json")]
        scan.write_bytes(image("HA HOT"))
        glyphs.write_bytes(font(FULL))
        args = map(str, (scan, glyphs, spec))
        command = list(args)
        for prefix, rc in (("HA ", 0), ("HOO ", 1)):
            spec.write_bytes(layout(field("required", prefix)))
            with self.subTest(prefix=prefix), redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main(command), rc)
            self.assertEqual(json.loads(out.getvalue()), model.extract(scan.read_bytes(), glyphs.read_bytes(), spec.read_bytes()))
        spec.write_bytes(b"{}")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as fail:
            model.main(command)
        self.assertEqual(fail.exception.code, 2)
