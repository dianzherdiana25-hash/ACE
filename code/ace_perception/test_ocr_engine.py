"""Verifier OCR dua jalur atas raster cetak, kegagalan, dan provenance."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _raster, ocr_engine as model


GLYPHS = {
    "A": ["01110", "11011", "10001", "11111", "10001", "10001", "10001"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "O": ["01110", "11011", "10001", "10001", "10001", "11011", "01110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
}


def font(raw=None):
    return json.dumps({"schema": "ace.perception-font.v1", "glyphs": GLYPHS if raw is None else raw}).encode()


def raster(canvas, *, polarity=False, binary=True, levels=(0, 255)):
    width = len(canvas[0])
    low, high = levels
    values = [high if (bit == "1") == polarity else low for row in canvas for bit in row]
    if binary:
        return f"P5\n{width} {len(canvas)}\n{high}\n".encode() + bytes(values)
    return f"P2\n# synthetic print\n{width} {len(canvas)}\n{high}\n".encode() + " ".join(map(str, values)).encode()


def canvas(lines, scale=1, alphabet=None):
    glyphs = GLYPHS if alphabet is None else alphabet
    words = [line.split(" ") for line in lines]
    full = []
    for line in words:
        if full:
            full.extend([""]*2)
        for offset in range(7):
            full.append("000" + "0000".join("0".join(glyphs[label][offset] for label in word)
                                                 for word in line) + "000")
    width = max(map(len, full))
    rows = ["0"*width, *(row.ljust(width, "0") for row in full), "0"*width]
    return ["".join(bit*scale for bit in row) for row in rows for _ in range(scale)]


class OCRTests(unittest.TestCase):
    def test_two_geometric_routes_agree_on_printed_lines_and_word_spacing(self):
        image = raster(canvas(["HAT OH", "HOT"]))
        data = font()
        result = model.recognize(image, data)
        self.assertEqual(result["text"], "HAT OH\nHOT")
        self.assertEqual(result["status"], "read")
        self.assertEqual(result["glyph_count"], 8)
        self.assertEqual(result["unresolved_count"], 0)
        self.assertEqual(result["image_sha256"], sha256(image).hexdigest())
        self.assertEqual(result["font_sha256"], sha256(data).hexdigest())
        glyph = result["lines"][0]["glyphs"][0]
        self.assertEqual(glyph["box"], [3, 1, 8, 8])
        self.assertEqual((glyph["pixel_vote"]["label"], glyph["projection_vote"]["label"]), ("H", "H"))
        self.assertEqual((glyph["pixel_vote"]["distance"], glyph["projection_vote"]["distance"]), (0, 0))

    def test_integer_scale_and_light_text_are_supported_without_computing_from_names(self):
        image = raster(canvas(["HAT OH"], scale=2), polarity=True, binary=False, levels=(37, 110))
        result = model.recognize(image, font(), light_ink=True, word_gap=8)
        self.assertEqual(result["text"], "HAT OH")
        self.assertEqual(result["width"], len(canvas(["HAT OH"], scale=2)[0]))
        self.assertEqual(result["threshold"], 37)
        self.assertEqual(result["lines"][0]["glyphs"][0]["box"], [6, 2, 16, 16])

    def test_unknown_shape_is_marked_explicitly_under_exact_policy(self):
        changed = {**GLYPHS, "V": ["10101", "11111", "01110", "11111", "11111", "11111", "11111"]}
        image = raster(canvas(["HAV"], alphabet=changed))
        report = model.recognize(image, font(), limit_bp=0)
        self.assertEqual(report["text"], "HA\ufffd")
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["unresolved_count"], 1)
        self.assertIsNone(report["lines"][0]["glyphs"][-1]["pixel_vote"]["label"])

    def test_uniform_black_white_and_gray_look_empty(self):
        for shade in (0, 112, 255):
            pixels = f"P2 2 2 255 {shade} {shade} {shade} {shade}".encode()
            with self.subTest(shade=shade):
                result = model.recognize(pixels, font())
                self.assertEqual(result["status"], "empty")
                self.assertEqual(result["lines"], [])
                self.assertIsNone(result["threshold"])

    def test_strict_glyph_validation_keeps_ambiguous_shapes_out_of_font(self):
        for templates in ({"X": ["0"]}, {"AB": GLYPHS["H"]}, {"\ufffd": GLYPHS["H"]},
                          {"H": GLYPHS["H"], "X": GLYPHS["H"]}, {"H": ["10", "1"]},
                          {"H": ["1", "x"]}, {"H": GLYPHS["H"], "U": ["1"]}):
            with self.subTest(templates=templates), self.assertRaises(ValueError):
                model.Font.decode(font(templates))
        duplicate = b'{"schema":"ace.perception-font.v1","glyphs":{"I":["1"],"I":["1"]}}'
        with self.assertRaisesRegex(ValueError, "ganda"):
            model.Font.decode(duplicate)

    def test_pgms_refuse_wrong_size_bad_samples_or_extra_record(self):
        samples = [b"P2 2 1 15 10", b"P2 2 1 15 0 16", b"P2 2 1 15 0 0 1", b"P5\n2 1\n255\n\x00",
                   b"P5\n1 1\n100\n\xff", b"P5\n1 1\n255\n\xff\x00", b"P3 1 1 255 0 0 0", b"P2 2000000 9 255"]
        for source in samples:
            with self.subTest(source=source), self.assertRaises(ValueError):
                _raster.decode(source)

    def test_binary_whitespace_first_sample_is_not_trimmed(self):
        newline_as_sample = _raster.decode(b"P5\r2 1\r255\r\n#")
        real_crlf = _raster.decode(b"P5\r\n2 1\r\n255\r\n\n#")
        self.assertEqual(newline_as_sample, real_crlf)
        self.assertEqual(newline_as_sample.pixels, (10, 35))
        self.assertEqual(real_crlf.rectangle([1, 0, 2, 1]), (35,))
        with self.assertRaises(ValueError):
            real_crlf.rectangle([2, 0, 3, 1])

    def test_exact_fit_and_tied_vote_never_resolve_by_label_alone(self):
        route = model._vote([(2, "X"), (2, "Y")], 10, 9000)
        self.assertIsNone(route["label"])
        self.assertEqual(route["second_margin"], 0)
        observed = model._vote([(2, "X"), (3, "Y")], 10, 2000)
        self.assertEqual(observed["label"], "X")
        self.assertEqual(observed["second_margin"], 1)

    def test_reject_bad_caller_limits(self):
        source = raster(canvas(["A"]))
        for changes in ({"word_gap": 0}, {"word_gap": 1.5}, {"limit_bp": True},
                        {"limit_bp": 10_001}, {"light_ink": "auto"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                model.recognize(source, font(), **changes)

    def test_cli_reads_only_supplied_files_and_outputs_deterministic_json(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        image, glyphs = root / "scan.pgm", root / "font.json"
        image.write_bytes(raster(canvas(["HOT"])))
        glyphs.write_bytes(font())
        for pass_number in range(2):
            with self.subTest(pass_number=pass_number), redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(image), str(glyphs)]), 0)
            value = output.getvalue()
            expected = model.recognize(image.read_bytes(), glyphs.read_bytes())
            self.assertEqual(json.loads(value), expected)
            if pass_number:
                self.assertEqual(value, previous)
            previous = value
        self.assertEqual(sorted(p.name for p in root.iterdir()), ["font.json", "scan.pgm"])
        image.write_bytes(b"bad")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            model.main([str(image), str(glyphs)])
        self.assertEqual(error.exception.code, 2)
