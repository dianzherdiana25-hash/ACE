"""Rakit pindaian berurutan dengan provenance halaman dan sambungan.

Mode overlap menilai pita konten dari dua input yang bersebelahan.
Irisan rata, ambiguitas, dan mismatch ditahan. Mode gap meletakkan
halaman berurutan tanpa klaim registrasi. Keluaran membawa boks
sumber, hasil uji sambungan, dan hash raster gabungan.
"""
import argparse
from array import array
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer


MAX_PAGES = 16
MAX_WORK = 5_000_000
MAX_INPUT_PIXELS = 8_000_000
MAX_AUTO_OVERLAP = 64


def _line(values, width, height, direction, index):
    if direction == "vertical":
        return values[index*width:(index+1)*width]
    return values[index:width*height:width]


def _candidate(before, after, overlap, direction):
    w0, h0, a = before
    w1, h1, b = after
    length = h0 if direction == "vertical" else w0
    cross = w0 if direction == "vertical" else h0
    difference = 0
    left_low = right_low = 255
    left_high = right_high = 0
    for index in range(overlap):
        edge_a = _line(a, w0, h0, direction, length-overlap+index)
        edge_b = _line(b, w1, h1, direction, index)
        difference += sum(abs(left-right) for left, right in zip(edge_a, edge_b, strict=True))
        left_low, right_low = min(left_low, min(edge_a)), min(right_low, min(edge_b))
        left_high, right_high = max(left_high, max(edge_a)), max(right_high, max(edge_b))
    return difference, overlap*cross, min(left_high-left_low, right_high-right_low)


def _seam(before, after, direction, low, high, max_error, min_range, auto):
    considered = []
    ranking = []
    for overlap in range(low, high+1):
        total, count, contrast = _candidate(before, after, overlap, direction)
        considered.append({"overlap": overlap, "difference_sum": total, "samples": count, "range": contrast})
        if contrast >= min_range:
            ranking.append((Fraction(total, count), overlap))
    ranking.sort()
    if not ranking:
        status, chosen = "insufficient_texture", None
    elif ranking[0][0] > max_error:
        status, chosen = "mismatch", None
    elif auto and len(ranking) > 1 and ranking[0][0] == ranking[1][0]:
        status, chosen = "ambiguous", None
    else:
        status, chosen = "verified", ranking[0][1]
    return {"status": status, "overlap": chosen, "candidates": considered}


def _rasterize(pages, placements, width, height, direction):
    total = array("I", [0])*(width*height)
    count = bytearray(width*height)
    for (source_width, source_height, values), position in zip(pages, placements, strict=True):
        x0, y0 = (0, position) if direction == "vertical" else (position, 0)
        for y in range(source_height):
            for x in range(source_width):
                index = (y+y0)*width+x+x0
                total[index] += values[y*source_width+x]
                count[index] += 1
    merged = bytes((value+occurrences//2)//occurrences if occurrences else 255
                   for value, occurrences in zip(total, count, strict=True))
    return _vision.encode(width, height, merged)


def stitch(images, *, direction="vertical", gap=0, overlap_px=None, auto_overlap=None,
           maximum_mean_difference=8, minimum_range=8):
    if not isinstance(images, (list, tuple)) or not 2 <= len(images) <= MAX_PAGES:
        raise ValueError("Perlu sedikitnya dua halaman dalam batas.")
    if direction not in ("horizontal", "vertical"):
        raise ValueError("Arah perlu horizontal atau vertical.")
    space = _integer(gap, 0, 1024, "Jeda")
    maximum_error = _integer(maximum_mean_difference, 0, 255, "Selisih maksimum")
    texture = _integer(minimum_range, 1, 255, "Rentang overlap")
    if (overlap_px is not None and auto_overlap is not None) or (space and (overlap_px is not None or auto_overlap is not None)):
        raise ValueError("Pilih satu mode sambungan.")
    if any(not isinstance(image, bytes) for image in images) or sum(map(len, images)) > _raster.MAX_BYTES*2:
        raise ValueError("Ukuran seluruh berkas halaman melampaui batas.")
    pages = []
    area = 0
    for image in images:
        decoded = _raster.decode(image)
        area += decoded.width*decoded.height
        if area > MAX_INPUT_PIXELS:
            raise ValueError("Jumlah piksel masukan halaman melampaui batas.")
        pages.append((decoded.width, decoded.height, _vision.normalized(decoded)))
    advance_axis = 1 if direction == "vertical" else 0
    length = [page[advance_axis] for page in pages]
    cross = [page[1-advance_axis] for page in pages]
    seams = []
    if overlap_px is not None or auto_overlap is not None:
        if len(set(cross)) != 1:
            raise ValueError("Overlap memerlukan dimensi silang yang sama.")
        limit = min(length)-1
        if auto_overlap is not None:
            if not isinstance(auto_overlap, (list, tuple)) or len(auto_overlap) != 2:
                raise ValueError("Rentang auto overlap perlu dua batas.")
            low = _integer(auto_overlap[0], 1, min(limit, MAX_AUTO_OVERLAP), "Overlap awal")
            high = _integer(auto_overlap[1], low, min(limit, MAX_AUTO_OVERLAP), "Overlap akhir")
        else:
            low = high = _integer(overlap_px, 1, limit, "Overlap")
        if sum(range(low, high+1))*cross[0]*(len(pages)-1) > MAX_WORK:
            raise ValueError("Pencarian overlap melampaui batas.")
        seams = [_seam(a, b, direction, low, high, maximum_error, texture, auto_overlap is not None)
                 for a, b in zip(pages, pages[1:])]
    else:
        seams = [{"status": "gap", "overlap": 0, "candidates": []} for _ in pages[1:]]
    report = {"schema": "ace.perception-page-stitch.v1", "direction": direction, "gap": space, "seams": seams,
              "source_sha256": [sha256(image).hexdigest() for image in images], "placements": [],
              "output_sha256": None, "size": None, "status": "held"}
    if any(seam["overlap"] is None for seam in seams):
        return None, report
    offsets = [0]
    for previous, seam in zip(length, seams):
        offsets.append(offsets[-1]+previous+space-seam["overlap"])
    advance = offsets[-1]+length[-1]
    width, height = (max(cross), advance) if direction == "vertical" else (advance, max(cross))
    if width*height > _raster.MAX_PIXELS:
        raise ValueError("Raster hasil melampaui batas.")
    payload = _rasterize(pages, offsets, width, height, direction)
    locations = []
    for page, ((w, h, _), start, checksum) in enumerate(zip(pages, offsets, report["source_sha256"], strict=True), 1):
        x, y = (0, start) if direction == "vertical" else (start, 0)
        locations.append({"page": page, "sha256": checksum, "box": [x, y, x+w, y+h]})
    report.update(output_sha256=sha256(payload).hexdigest(), size=[width, height], placements=locations, status="stitched")
    return payload, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--direction", choices=("vertical", "horizontal"), default="vertical")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--gap", type=int, default=0)
    modes.add_argument("--overlap-px", type=int)
    modes.add_argument("--auto-overlap", nargs=2, type=int)
    parser.add_argument("--maximum-mean-difference", type=int, default=8)
    parser.add_argument("--minimum-range", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        if len(args.images) > MAX_PAGES:
            raise ValueError("Terlalu banyak berkas halaman.")
        payload, report = stitch([_raster.read(path) for path in args.images], direction=args.direction,
                                 gap=args.gap, overlap_px=args.overlap_px, auto_overlap=args.auto_overlap,
                                 maximum_mean_difference=args.maximum_mean_difference, minimum_range=args.minimum_range)
        if payload is not None:
            with args.output.open("xb") as stream:
                stream.write(payload)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(payload is None)


if __name__ == "__main__":
    raise SystemExit(main())
