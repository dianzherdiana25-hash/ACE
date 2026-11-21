"""Ubah rumus cetak linear dari OCR menjadi AST yang memuat posisi.

Parser membedakan prioritas operator, pangkat asosiatif kanan, dan
persamaan tunggal. Angka desimal dipertahankan sebagai token.
Rumus parsial atau tata bahasa tak didukung tetap tampil sebagai
temuan dengan boks OCR. Kode tidak mengevaluasi rumus.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from . import _raster, _vision, ocr_engine
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token


TOKENS = re.compile(r"[0-9]{1,32}(?:\.[0-9]{1,16})?|[A-Za-z][A-Za-z0-9_]{0,31}|[()+*/^=\-−×÷]")
OPERATORS = {"+": (10, 11), "-": (10, 11), "*": (20, 21), "/": (20, 21), "^": (40, 40)}
ALIASES = {"−": "-", "×": "*", "÷": "/"}


class FormulaError(ValueError):
    def __init__(self, detail, position):
        super().__init__(detail)
        self.position = position


def _tokens(text):
    if not isinstance(text, str) or len(text) > 512:
        raise FormulaError("Rumus melampaui batas.", 0)
    rows = []
    offset = 0
    while offset < len(text):
        if text[offset].isspace():
            offset += 1
            continue
        found = TOKENS.match(text, offset)
        if found is None:
            raise FormulaError("Karakter rumus tidak didukung.", offset)
        literal = found[0]
        rows.append((ALIASES.get(literal, literal), offset, found.end()))
        offset = found.end()
    rows.append(("", len(text), len(text)))
    return rows


class Parser:
    def __init__(self, text):
        self.items = _tokens(text)
        self.offset = 0

    def current(self):
        return self.items[self.offset]

    def take(self):
        entry = self.current()
        if entry[0]:
            self.offset += 1
        return entry

    def expression(self, floor=0, depth=0):
        item, start, end = self.take()
        if depth > 40:
            raise FormulaError("Rumus bersarang terlalu dalam.", start)
        if item in ("+", "-"):
            operand = self.expression(30, depth+1)
            first = {"type": "unary", "operator": item, "argument": operand, "range": [start, operand["range"][1]]}
        elif item == "(":
            inner = self.expression(depth=depth+1)
            closer, position, finish = self.take()
            if closer != ")":
                raise FormulaError("Kurung penutup diperlukan.", position)
            first = {"type": "group", "value": inner, "range": [start, finish]}
        elif item and item[0].isalpha():
            first = {"type": "name", "literal": item, "range": [start, end]}
        elif item and item[0].isdigit():
            first = {"type": "number", "literal": item, "range": [start, end]}
        else:
            raise FormulaError("Operand diperlukan.", start)
        while self.current()[0] in OPERATORS:
            operator, _, _ = self.current()
            left, right = OPERATORS[operator]
            if left < floor:
                break
            self.take()
            second = self.expression(right, depth+1)
            first = {"type": "binary", "operator": operator, "left": first, "right": second,
                     "range": [first["range"][0], second["range"][1]]}
        return first

    def parse(self):
        left = self.expression()
        if self.current()[0] == "=":
            self.take()
            right = self.expression()
            left = {"type": "equation", "left": left, "right": right, "range": [left["range"][0], right["range"][1]]}
        found, position, _ = self.current()
        if found:
            raise FormulaError("Token tersisa setelah rumus.", position)
        return left


def parse_formula(text):
    return Parser(text).parse()


def read_formulas(image_data, font_data, layout):
    image = _raster.decode(image_data)
    font = ocr_engine.Font.decode(font_data)
    raw = _vision.spec(layout, "ace.perception-formula-layout.v1", ("zones", "word_gap", "light_ink"))
    gap = _integer(raw["word_gap"], 1, 4096, "Jarak kata")
    zones = raw["zones"]
    if type(raw["light_ink"]) is not bool or not isinstance(zones, list) or not 1 <= len(zones) <= 128:
        raise ValueError("Deklarasi zona rumus tidak sah.")
    pairs = {}
    for row in zones:
        if not isinstance(row, dict) or set(row) != {"id", "box"}:
            raise ValueError("Bentuk zona rumus tidak sah.")
        key = _token(row["id"], "ID zona rumus")
        if key in pairs:
            raise ValueError("Zona rumus ganda.")
        pairs[key] = _vision.bounded_box(row["box"], image)
    if sum((box[2]-box[0])*(box[3]-box[1]) for box in pairs.values()) > 1_000_000:
        raise ValueError("Area rumus terlalu besar.")
    rows = []
    for key, box in sorted(pairs.items()):
        evidence = ocr_engine.read_area(image, box, font_data, light_ink=raw["light_ink"], word_gap=gap)
        status = evidence["status"]
        parsed, issue = None, None
        if status == "read":
            try:
                if "\n" in evidence["text"]:
                    raise FormulaError("Rumus perlu satu baris.", evidence["text"].index("\n"))
                parsed = parse_formula(evidence["text"])
            except FormulaError as error:
                status = "unsupported_formula"
                issue = {"reason": str(error), "character_offset": error.position}
        rows.append({"id": key, "box": box, "status": status, "ast": parsed, "issue": issue, "ocr": evidence})
    return {"schema": "ace.perception-formula-ast.v1", "image_sha256": sha256(image_data).hexdigest(),
            "layout_sha256": sha256(layout).hexdigest(), "font_sha256": font.checksum, "zones": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        report = read_formulas(_raster.read(args.image), _raster.read(args.font, ocr_engine.MAX_FONT_BYTES),
                               _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(row["status"] != "read" for row in report["zones"]))


if __name__ == "__main__":
    raise SystemExit(main())
