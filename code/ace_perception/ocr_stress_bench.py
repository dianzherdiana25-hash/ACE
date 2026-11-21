"""Ukur retensi OCR pada gangguan raster lokal yang dapat direproduksi.

Kasus menyegel media dan gold. Setiap transformasi menghasilkan byte
baru dari seed dan kebijakan sendiri. Akurasi karakter dilaporkan
untuk semua observasi, termasuk karakter tak pasti dan bacaan kosong.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from random import Random
import sys

from . import _perception_io, _raster, _vision, ocr_engine, perception_bench
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_CASES = 64
MAX_WAVE_PIXELS = 8_000_000


def _alter(raster, mode, severity, seed, light=False):
    src = _raster.decode(raster)
    values = bytearray(_vision.normalized(src))
    if mode == "clean":
        return raster
    if mode == "contrast":
        values = bytearray(128+((value-128)*(10_000-severity))//10_000 for value in values)
    elif mode == "salt_pepper":
        rng = Random(seed)
        for position in rng.sample(range(len(values)), len(values)*severity//10_000):
            values[position] = rng.choice((0, 255))
    elif mode == "horizontal_occlusion":
        lines = src.height*severity//10_000
        start = (src.height-lines)//2
        values[start*src.width:(start+lines)*src.width] = bytes([0 if light else 255])*(lines*src.width)
    else:
        raise ValueError("Gangguan OCR tidak dikenal.")
    return _vision.encode(src.width, src.height, values)


def _rate(n, d):
    if not d:
        return None
    value = Fraction(n, d)
    return {"numerator": value.numerator, "denominator": value.denominator}


def assess(root, plan, font, expected):
    fields = ("plan_ref", "font_sha256", "seed", "cases", "variants", "light_ink", "word_gap", "limit_bp")
    raw = _vision.spec(plan, "ace.perception-ocr-stress.v1", fields)
    if _sha(raw) != _digest(expected) or sha256(font).hexdigest() != _digest(raw["font_sha256"]):
        raise ValueError("Rencana atau font stress berbeda dari anchor.")
    seed = _integer(raw["seed"], 0, (1<<63)-1, "Seed")
    gap = _integer(raw["word_gap"], 1, 4096, "Jarak kata")
    threshold = _integer(raw["limit_bp"], 0, 10000, "Batas vote")
    if type(raw["light_ink"]) is not bool or not isinstance(raw["cases"], list) or not 1 <= len(raw["cases"]) <= MAX_CASES:
        raise ValueError("Kasus stress atau polaritas tidak sah.")
    variants = raw["variants"]
    if not isinstance(variants, list) or not 1 <= len(variants) <= 12:
        raise ValueError("Jumlah varian stress di luar batas.")
    variants_index = {"clean": ("clean", 0)}
    for row in variants:
        if not isinstance(row, dict) or set(row) != {"id", "kind", "severity_bp"}:
            raise ValueError("Varian stress tidak sah.")
        key, mode = _token(row["id"], "ID varian"), _token(row["kind"], "Jenis gangguan")
        if key in variants_index or mode not in {"contrast", "salt_pepper", "horizontal_occlusion"}:
            raise ValueError("Jenis atau identitas varian tidak sah.")
        variants_index[key] = mode, _integer(row["severity_bp"], 1, 10_000, "Tingkat gangguan")

    seen = set()
    used = edit_work = 0
    results = []
    totals = {key: [0, 0] for key in variants_index}
    for row in raw["cases"]:
        if not isinstance(row, dict) or set(row) != {"id", "image_path", "bytes", "sha256", "gold", "gold_ref"}:
            raise ValueError("Bentuk kasus stress tidak sah.")
        key = _token(row["id"], "ID kasus")
        gold_ref = _token(row["gold_ref"], "Rujukan gold")
        gold = row["gold"]
        if key in seen or not isinstance(gold, str) or not 1 <= len(gold) <= 2048 or not gold.strip():
            raise ValueError("Kasus ganda atau gold stres tidak sah.")
        seen.add(key)
        size = _integer(row["bytes"], 1, _raster.MAX_BYTES, "Byte gambar")
        checksum = _digest(row["sha256"])
        data = _perception_io.read_relative(root, row["image_path"], size, checksum)
        if len(data) != size:
            raise ValueError("Jumlah byte kasus berubah.")
        image = _raster.decode(data)
        used += image.width*image.height*len(variants_index)
        if used > MAX_WAVE_PIXELS:
            raise ValueError("Budget stress raster melebihi batas.")
        scores = []
        for variant, (mode, severity) in variants_index.items():
            sub_seed = int(_sha([seed, key, variant]), 16)
            input_image = _alter(data, mode, severity, sub_seed, raw["light_ink"])
            report = ocr_engine.recognize(input_image, font, light_ink=raw["light_ink"], word_gap=gap, limit_bp=threshold)
            edit_work += (len(gold)+1)*(len(report["text"])+1)
            if edit_work > perception_bench.MAX_WORK:
                raise ValueError("Budget edit distance stress melebihi batas.")
            errors = perception_bench._align(gold, report["text"])[0]
            totals[variant][0] += errors
            totals[variant][1] += len(gold)
            scores.append({"variant": variant, "image_sha256": sha256(input_image).hexdigest(),
                           "errors": errors, "gold_characters": len(gold), "ocr_status": report["status"],
                           "unresolved_glyphs": report["unresolved_count"]})
        results.append({"id": key, "gold_ref": gold_ref, "source_sha256": checksum, "scores": scores})
    baseline = Fraction(*totals["clean"])
    summary = []
    for key, (errors, units) in totals.items():
        delta = Fraction(errors, units)-baseline
        summary.append({"variant": key, "edits": errors, "gold_chars": units, "cer": _rate(errors, units),
                        "cer_delta": _rate(delta.numerator, delta.denominator)})
    return {"schema": "ace.perception-ocr-stress-report.v1", "plan_sha256": expected,
            "plan_ref": _token(raw["plan_ref"], "Rujukan stress"), "font_sha256": raw["font_sha256"],
            "seed": seed, "summary": summary, "cases": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(args.root, _raster.read(args.plan, _vision.MAX_SPEC_BYTES),
                        _raster.read(args.font, ocr_engine.MAX_FONT_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
