"""Cari kandidat gambar nyaris sama melalui gradien dan intensitas raster.

Sampel grid memakai rata-rata area. Fingerprint membandingkan
gradien horizontal dan vertikal. Kandidat harus memenuhi batas
hamming dan selisih kecerahan. Identitas byte tetap dilaporkan
sebagai kelas terpisah dari kandidat yang hanya mirip.
"""
import argparse
from hashlib import sha256
from itertools import combinations
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer


SIZE = 9
MAX_IMAGES = 64
MAX_TOTAL_PIXELS = 8_000_000


def _low_resolution(image):
    values = _vision.normalized(image)
    result = []
    cells = SIZE
    for row in range(cells):
        start_y = row*image.height//cells
        stop_y = max(start_y+1, (row+1)*image.height//cells)
        line = []
        for column in range(cells):
            start_x = column*image.width//cells
            stop_x = max(start_x+1, (column+1)*image.width//cells)
            tiles = [values[y*image.width+x] for y in range(start_y, stop_y) for x in range(start_x, stop_x)]
            line.append(sum(tiles)//len(tiles))
        result.append(line)
    return result


def _rotate(values):
    return [list(row) for row in zip(*values[::-1], strict=True)]


def _fingerprint(rows):
    horizontal = [value < following for line in rows for value, following in zip(line, line[1:])]
    vertical = [value < below for line, next_line in zip(rows, rows[1:]) for value, below in zip(line, next_line, strict=True)]
    bits = 0
    for on in horizontal+vertical:
        bits = bits*2+on
    flat = [value for line in rows for value in line]
    return bits, flat


def _score(left, right):
    return (left[0]^right[0]).bit_count(), sum(abs(a-b) for a,b in zip(left[1], right[1], strict=True))


def compare(items, *, maximum_hamming=15, maximum_gray_mean=18, rotations=True):
    if not isinstance(items, (list, tuple)) or not 2 <= len(items) <= MAX_IMAGES:
        raise ValueError("Jumlah gambar duplikat di luar batas.")
    if type(rotations) is not bool:
        raise ValueError("Mode rotasi perlu boolean.")
    hamming = _integer(maximum_hamming, 0, 2*SIZE*(SIZE-1), "Jarak Hamming maksimum")
    gray = _integer(maximum_gray_mean, 0, 255, "Perbedaan intensitas maksimum")
    output = []
    total = 0
    for index, data in enumerate(items, 1):
        image = _raster.decode(data)
        total += image.width*image.height
        if total > MAX_TOTAL_PIXELS:
            raise ValueError("Jumlah piksel koleksi melampaui batas.")
        rows = _low_resolution(image)
        options = []
        for turn in range(4 if rotations else 1):
            options.append((turn*90, _fingerprint(rows)))
            rows = _rotate(rows)
        output.append((index, sha256(data).hexdigest(), options))
    pairs = []
    rejected = 0
    for (index, first, a), (other, second, b) in combinations(output, 2):
        scores = [(*_score(a[0][1], fingerprint), turn) for turn, fingerprint in b]
        plausible = [row for row in scores if row[0] <= hamming and row[1] <= gray*SIZE**2]
        if not plausible:
            rejected += 1
            continue
        hd, total_gray, turn = min(plausible)
        pairs.append({"left": index, "right": other, "left_sha256": first, "right_sha256": second,
                      "rotation_clockwise": turn, "hamming": hd, "gray_difference_sum": total_gray,
                      "gray_cells": SIZE**2, "status": "identical_bytes" if first == second else "near_candidate"})
    return {"schema": "ace.perception-near-duplicate-images.v1",
            "images": [{"index": index, "sha256": checksum} for index, checksum, _ in output],
            "policy": {"maximum_hamming": hamming, "maximum_gray_mean": gray, "rotations": rotations},
            "pairs": pairs, "rejected_pairs": rejected}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--maximum-hamming", type=int, default=15)
    parser.add_argument("--maximum-gray-mean", type=int, default=18)
    parser.add_argument("--fixed-orientation", action="store_true")
    args = parser.parse_args(argv)
    try:
        if len(args.images) > MAX_IMAGES:
            raise ValueError("Jumlah gambar melampaui batas.")
        result = compare([_raster.read(path) for path in args.images], maximum_hamming=args.maximum_hamming,
                         maximum_gray_mean=args.maximum_gray_mean, rotations=not args.fixed_orientation)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
