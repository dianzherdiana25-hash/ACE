"""Perkecil raster sesuai anggaran tanpa crop, dengan probe OCR opsional.

Sisi terbesar dicari melalui batas piksel dan sisi yang diberikan.
Averaging area mengambil semua piksel asal. Probe OCR opsional
menahan ekspor ketika edit distance terhadap baseline fixture
melewati ambang atau baseline tidak lengkap.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision, ocr_engine, perception_bench
from .audio_pipeline import _canonical, _integer


def _size(width, height, max_edge, max_pixels):
    longest = max(width, height)
    low, high = 1, min(longest, max_edge)
    while low < high:
        chosen = (low+high+1)//2
        out_w, out_h = max(1, width*chosen//longest), max(1, height*chosen//longest)
        if out_w*out_h > max_pixels:
            high = chosen-1
        else:
            low = chosen
    return max(1, width*low//longest), max(1, height*low//longest)


def _downsample(image, width, height):
    values = _vision.normalized(image)
    if (width, height) == (image.width, image.height):
        return values
    result = bytearray()
    for y in range(height):
        top, bottom = y*image.height//height, (y+1)*image.height//height
        for x in range(width):
            left, right = x*image.width//width, (x+1)*image.width//width
            pixels = (bottom-top)*(right-left)
            total = sum(sum(values[row*image.width+left:row*image.width+right]) for row in range(top,bottom))
            result.append((total+pixels//2)//pixels)
    return bytes(result)


def resize(data, *, maximum_edge=640, maximum_pixels=320000, font=None, maximum_ocr_edits=None, light_ink=False):
    image = _raster.decode(data)
    edge = _integer(maximum_edge, 1, _raster.MAX_PIXELS, "Sisi maksimum")
    budget = _integer(maximum_pixels, 1, _raster.MAX_PIXELS, "Piksel maksimum")
    if type(light_ink) is not bool or (font is None) != (maximum_ocr_edits is None):
        raise ValueError("Probe OCR memerlukan font dan batas edit sekaligus.")
    target = _size(image.width, image.height, edge, budget)
    output = _vision.encode(*target, _downsample(image, *target))
    guard = None
    accepted = True
    if font is not None:
        limit = _integer(maximum_ocr_edits, 0, 4096, "Batas edit OCR")
        base = ocr_engine.recognize(data, font, light_ink=light_ink)
        gap = max(1, (3*target[0]+image.width//2)//image.width)
        after = ocr_engine.recognize(output, font, light_ink=light_ink, word_gap=gap)
        measured = base["status"] == "read" and after["status"] == "read"
        if measured and (len(base["text"])+1)*(len(after["text"])+1) > perception_bench.MAX_WORK:
            raise ValueError("Perbandingan OCR lean melampaui batas kerja.")
        edits = perception_bench._align(list(base["text"]), list(after["text"]))[0] if measured else None
        accepted = measured and edits <= limit
        guard = {"font_sha256": base["font_sha256"], "baseline_status": base["status"], "candidate_status": after["status"],
                 "baseline_glyphs": base["glyph_count"], "candidate_glyphs": after["glyph_count"],
                 "edits": edits, "limit": limit, "accepted": accepted}
    report = {"schema": "ace.perception-lean-raster.v1", "source_sha256": sha256(data).hexdigest(),
              "candidate_sha256": sha256(output).hexdigest(), "input_size": [image.width, image.height],
              "output_size": list(target), "output_pixels": target[0]*target[1], "maximum_pixels": budget,
              "maximum_edge": edge, "ocr_guard": guard, "status": "ready" if accepted else "held"}
    return output if accepted else None, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-edge", type=int, default=640)
    parser.add_argument("--maximum-pixels", type=int, default=320000)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--maximum-ocr-edits", type=int)
    parser.add_argument("--light-ink", action="store_true")
    args = parser.parse_args(argv)
    try:
        result, report = resize(_raster.read(args.image), maximum_edge=args.maximum_edge,
                                maximum_pixels=args.maximum_pixels, light_ink=args.light_ink,
                                font=_raster.read(args.font, ocr_engine.MAX_FONT_BYTES) if args.font else None,
                                maximum_ocr_edits=args.maximum_ocr_edits)
        if result is not None:
            with args.output.open("xb") as stream:
                stream.write(result)
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result is None)


if __name__ == "__main__":
    raise SystemExit(main())
