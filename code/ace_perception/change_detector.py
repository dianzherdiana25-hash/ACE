"""Temukan perubahan raster dengan registrasi translasi yang dibatasi.

Skor registrasi memakai irisan inti yang sama untuk setiap shift.
Perpindahan hanya diterapkan jika terbaik secara unik dan lebih
baik dari nol sesuai ambang. Selisih piksel di wilayah terbanding
menghasilkan boks perubahan, sementara wilayah tepi dilaporkan.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .screen_understanding import _components


MAX_WORK = 20_000_000
MAX_ALIGNMENT = 8
MAX_REGIONS = 256


def _core_sad(a, b, width, height, margin, dx, dy):
    return sum(abs(a[y*width+x]-b[(y+dy)*width+x+dx])
               for y in range(margin, height-margin) for x in range(margin, width-margin))


def _alignment(a, b, width, height, margin, gain):
    if not margin:
        return {"shift": [0, 0], "status": "fixed", "best_shift": None, "gain_sum": None}
    area = (width-2*margin)*(height-2*margin)
    candidates = (2*margin+1)**2
    if width <= 2*margin or height <= 2*margin or area*candidates > MAX_WORK:
        raise ValueError("Biaya atau geometri registrasi melampaui batas.")
    scores = sorted((_core_sad(a, b, width, height, margin, dx, dy), dx, dy)
                    for dy in range(-margin, margin+1) for dx in range(-margin, margin+1))
    base = next(value for value, dx, dy in scores if dx == dy == 0)
    cost, dx, dy = scores[0]
    improvement = base-cost
    if scores[1][0] == cost:
        status = "ambiguous"
    elif dx == dy == 0:
        status = "already_aligned"
    elif improvement < gain*area:
        status = "below_alignment_gain"
    else:
        status = "aligned"
    return {"shift": [dx, dy] if status == "aligned" else [0, 0], "status": status,
            "best_shift": None if status == "ambiguous" else [dx, dy],
            "gain_sum": improvement, "sample_pixels": area, "base_sad": base, "best_sad": cost}


def _compare(a, b, width, height, shift, threshold):
    dx, dy = shift
    x0, x1 = max(0, -dx), min(width, width-dx)
    y0, y1 = max(0, -dy), min(height, height-dy)
    mask = bytearray((x1-x0)*(y1-y0))
    total = maximum = position = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            difference = abs(a[y*width+x]-b[(y+dy)*width+x+dx])
            maximum = max(maximum, difference)
            total += difference
            mask[position] = difference >= threshold
            position += 1
    return mask, (x0, y0, x1, y1), total, maximum


def detect(before, after, *, max_shift=0, threshold=1, minimum_region=1, minimum_alignment_gain=1):
    left, right = map(_raster.decode, (before, after))
    if (left.width, left.height) != (right.width, right.height):
        raise ValueError("Gambar perubahan perlu ukuran identik.")
    margin = _integer(max_shift, 0, MAX_ALIGNMENT, "Shift maksimum")
    cutoff = _integer(threshold, 1, 255, "Ambang perubahan")
    minimum = _integer(minimum_region, 1, _raster.MAX_PIXELS, "Piksel wilayah minimum")
    gain = _integer(minimum_alignment_gain, 1, 255, "Gain registrasi")
    width, height = left.width, left.height
    a, b = _vision.normalized(left), _vision.normalized(right)
    alignment = _alignment(a, b, width, height, margin, gain)
    mask, overlap, total, maximum = _compare(a, b, width, height, alignment["shift"], cutoff)
    x0, y0, x1, _ = overlap
    dx, dy = alignment["shift"]
    regions = []
    noise = omitted = 0
    for box, count in _components(mask, x1-x0):
        if count < minimum:
            noise += count
            continue
        if len(regions) >= MAX_REGIONS:
            omitted += 1
            continue
        lo_x, lo_y, hi_x, hi_y = box
        region = [lo_x+x0, lo_y+y0, hi_x+x0, hi_y+y0]
        regions.append({"before_box": region, "after_box": [region[0]+dx, region[1]+dy, region[2]+dx, region[3]+dy],
                        "pixels": count})
    return {"schema": "ace.perception-change.v1", "before_sha256": sha256(before).hexdigest(),
            "after_sha256": sha256(after).hexdigest(), "size": [width, height], "alignment": alignment,
            "before_overlap_box": list(overlap), "compared_pixels": len(mask), "uncompared_pixels": width*height-len(mask),
            "raw_difference_sum": total, "maximum_difference": maximum, "threshold": cutoff,
            "changed_pixels": sum(mask), "below_region_minimum_pixels": noise,
            "regions_omitted_by_cap": omitted, "regions": regions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--max-shift", type=int, default=0)
    parser.add_argument("--threshold", type=int, default=1)
    parser.add_argument("--minimum-region", type=int, default=1)
    parser.add_argument("--minimum-alignment-gain", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        result = detect(_raster.read(args.before), _raster.read(args.after), max_shift=args.max_shift,
                        threshold=args.threshold, minimum_region=args.minimum_region,
                        minimum_alignment_gain=args.minimum_alignment_gain)
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
