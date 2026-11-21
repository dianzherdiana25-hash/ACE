"""Hitung komponen objek raster dan pertahankan ketidakpastian himpitan.

Komponen di rentang luas yang diberikan dihitung sebagai kandidat
tunggal. Komponen lebih besar diberi rentang berdasarkan asumsi
luas, serta jumlah inti sesudah erosi sebagai petunjuk terpisah.
Hasil tidak mengubah petunjuk tersebut menjadi jumlah objek pasti.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision, ocr_engine
from .audio_pipeline import _canonical, _integer
from .screen_understanding import _components


MAX_PIXELS = 600_000
MAX_COMPONENTS = 512


def _labelled(mask, width):
    # Pakai ID komponen untuk memastikan kotak bersarang tidak ikut tererosi.
    seen = bytearray(len(mask))
    for origin, active in enumerate(mask):
        if not active or seen[origin]:
            continue
        seen[origin] = 1
        points = [origin]
        for point in points:
            col = point%width
            candidates = []
            if col:
                candidates.append(point-1)
            if col < width-1:
                candidates.append(point+1)
            if point >= width:
                candidates.append(point-width)
            if point+width < len(mask):
                candidates.append(point+width)
            for neighbor in candidates:
                if mask[neighbor] and not seen[neighbor]:
                    seen[neighbor] = 1
                    points.append(neighbor)
        yield points


def _core_count(points, width, bounds, limit, minimum_area):
    x0, y0, x1, y1 = bounds
    span, height = x1-x0, y1-y0
    filled = bytearray(span*height)
    for point in points:
        x, y = point%width-x0, point//width-y0
        filled[y*span+x] = 1
    for _ in range(limit):
        eroded = bytearray(len(filled))
        for y in range(1, height-1):
            base = y*span
            for x in range(1, span-1):
                p = base+x
                eroded[p] = filled[p] and filled[p-1] and filled[p+1] and filled[p-span] and filled[p+span]
        filled = eroded
    return sum(area >= minimum_area for _, area in _components(filled, span))


def count(image_data, *, box=None, threshold=None, light_ink=False, minimum_area=8,
          maximum_single_area=250, erosion_steps=1, minimum_core_area=1):
    image = _raster.decode(image_data)
    area = list(box) if isinstance(box, tuple) else box
    region = [0, 0, image.width, image.height] if area is None else _vision.bounded_box(area, image)
    x0, y0, x1, y1 = region
    width, height = x1-x0, y1-y0
    if width*height > MAX_PIXELS or type(light_ink) is not bool:
        raise ValueError("Area hitung atau polaritas tidak sah.")
    low = _integer(minimum_area, 1, MAX_PIXELS, "Luas minimum")
    high = _integer(maximum_single_area, low, MAX_PIXELS, "Luas satu objek maksimum")
    levels = _integer(erosion_steps, 0, 3, "Langkah erosi")
    core = _integer(minimum_core_area, 1, MAX_PIXELS, "Luas inti minimum")
    data = image.rectangle(region)
    cutoff = ocr_engine._otsu(data, image.maximum) if threshold is None else _integer(threshold, 0, image.maximum, "Ambang")
    mask = [] if cutoff is None else [value > cutoff if light_ink else value <= cutoff for value in data]
    groups = []
    single = noise = 0
    floor = ceiling = 0
    core_area_budget = 1_200_000
    for points in _labelled(mask, width):
        size = len(points)
        if size < low:
            noise += 1
            continue
        local_x = [point%width for point in points]
        local_y = [point//width for point in points]
        bbox = min(local_x), min(local_y), max(local_x)+1, max(local_y)+1
        x, y, r, b = bbox
        row = {"box": [x+x0, y+y0, r+x0, b+y0], "pixels": size,
               "status": "single_candidate" if size <= high else "crowded", "eroded_cores": None}
        if size <= high:
            single += 1
        else:
            span = (r-x)*(b-y)
            if span > core_area_budget:
                raise ValueError("Area inti objek melampaui batas kerja.")
            core_area_budget -= span
            lower, upper = (size+high-1)//high, size//low
            if lower > upper:
                row["area_count_range"] = None
            else:
                row["area_count_range"] = [lower, upper]
                floor += lower
                ceiling += upper
            row["eroded_cores"] = _core_count(points, width, bbox, levels, core)
        groups.append(row)
        if len(groups) > MAX_COMPONENTS:
            raise ValueError("Jumlah komponen objek melampaui batas.")
    incomplete = any(row["status"] == "crowded" and row["area_count_range"] is None for row in groups)
    return {"schema": "ace.perception-object-count.v1", "image_sha256": sha256(image_data).hexdigest(),
            "region": region, "threshold": cutoff, "single_candidates": single, "discarded_small": noise,
            "crowded_components": len(groups)-single, "area_assumption_range": None if incomplete else [single+floor, single+ceiling],
            "minimum_area": low, "maximum_single_area": high, "components": groups}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--minimum-area", type=int, default=8)
    parser.add_argument("--maximum-single-area", type=int, default=250)
    parser.add_argument("--threshold", type=int)
    parser.add_argument("--light-ink", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = count(_raster.read(args.image), minimum_area=args.minimum_area, maximum_single_area=args.maximum_single_area,
                       threshold=args.threshold, light_ink=args.light_ink)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
