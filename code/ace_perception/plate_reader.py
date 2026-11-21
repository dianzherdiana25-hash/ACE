"""Baca boks plat yang sudah ditandai dan uji susunan karakter.

OCR dinilai terhadap pola grup huruf dan angka yang diberikan
pemanggil. Koreksi karakter ambigu tidak dilakukan. Nilai plat
disembunyikan secara default, sedangkan status, hash sumber, dan
boks tetap membantu menelaah apakah pembacaan dapat diterima.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from . import _raster, _vision, ocr_engine
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token


MAX_ZONES = 64
MAX_GRAMMARS = 12


def _patterns(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_GRAMMARS:
        raise ValueError("Daftar pola plat di luar batas.")
    patterns = {}
    for entry in rows:
        if not isinstance(entry, dict) or set(entry) != {"id", "source_ref", "groups"}:
            raise ValueError("Bentuk pola plat tidak sah.")
        key = _token(entry["id"], "ID pola plat")
        ref = _token(entry["source_ref"], "Rujukan pola plat")
        if key in patterns:
            raise ValueError("ID pola plat ganda.")
        raw = entry["groups"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 6:
            raise ValueError("Jumlah grup pola tidak sah.")
        sections = []
        for group in raw:
            if not isinstance(group, dict) or set(group) != {"kind", "min", "max"} or group["kind"] not in ("letter", "digit"):
                raise ValueError("Karakter grup plat harus huruf atau angka.")
            lo = _integer(group["min"], 1, 12, "Panjang awal grup")
            hi = _integer(group["max"], lo, 12, "Panjang akhir grup")
            base = "[A-Z]" if group["kind"] == "letter" else "[0-9]"
            sections.append(base+"{%d,%d}" % (lo, hi))
        patterns[key] = (ref, re.compile(" ".join(sections)))
    return patterns


def read_plates(data, font_data, layout, *, reveal=False):
    if type(reveal) is not bool:
        raise ValueError("Mode pengungkapan perlu boolean.")
    image = _raster.decode(data)
    font = ocr_engine.Font.decode(font_data)
    options = _vision.spec(layout, "ace.perception-plate-layout.v1", ("zones", "patterns", "word_gap", "light_ink"))
    grammars = _patterns(options["patterns"])
    gap = _integer(options["word_gap"], 1, 4096, "Celah grup plat")
    if type(options["light_ink"]) is not bool:
        raise ValueError("Polaritas perlu boolean.")
    zones = options["zones"]
    if not isinstance(zones, list) or not 1 <= len(zones) <= MAX_ZONES:
        raise ValueError("Jumlah boks plat di luar batas.")
    rows = []
    seen = set()
    total = 0
    bindings = []
    for entry in zones:
        if not isinstance(entry, dict) or set(entry) != {"id", "box", "pattern"}:
            raise ValueError("Bentuk zona plat tidak sah.")
        key = _token(entry["id"], "ID boks plat")
        mode = _token(entry["pattern"], "ID pola boks")
        if key in seen or mode not in grammars:
            raise ValueError("ID zona ganda atau pola belum didaftarkan.")
        seen.add(key)
        box = _vision.bounded_box(entry["box"], image)
        total += (box[2]-box[0])*(box[3]-box[1])
        bindings.append((key, mode, box))
    if total > 800_000:
        raise ValueError("Luas total boks plat melampaui batas.")
    for key, mode, box in sorted(bindings):
        pattern_ref, rule = grammars[mode]
        observed = ocr_engine.read_area(image, box, font_data, light_ink=options["light_ink"], word_gap=gap)
        text = observed["text"]
        normalized = text.upper() if text is not None and text.isascii() else None
        match = normalized is not None and rule.fullmatch(normalized) is not None
        status = "verified_format" if match else ("format_mismatch" if observed["status"] == "read" else observed["status"])
        rows.append({"id": key, "box": box, "pattern": mode, "pattern_ref": pattern_ref, "status": status,
                     "ocr_status": observed["status"], "glyph_count": len(observed["glyphs"]),
                     "plate": normalized if match and reveal else None})
    return {"schema": "ace.perception-plate-reads.v1", "image_sha256": sha256(data).hexdigest(),
            "font_sha256": font.checksum, "layout_sha256": sha256(layout).hexdigest(),
            "plaintext_included": reveal, "zones": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--reveal", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = read_plates(_raster.read(args.image), _raster.read(args.font, ocr_engine.MAX_FONT_BYTES),
                             _raster.read(args.layout, _vision.MAX_SPEC_BYTES), reveal=args.reveal)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(item["status"] != "verified_format" for item in report["zones"]))


if __name__ == "__main__":
    raise SystemExit(main())
