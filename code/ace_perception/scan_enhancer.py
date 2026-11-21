"""Perbaiki pindaian lokal dengan kontras dan binarisasi berbasis wilayah.

Catatan menyimpan percentile sebelum perbaikan, jumlah speckle yang
dihapus, dan jumlah piksel hasil. Kontras yang tidak cukup menahan
binarisasi. Setiap perubahan dapat diputar ulang dari raster dan
parameter tanpa mengambil data dari layanan.
"""
import argparse
from array import array
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer


MAX_SCAN_PIXELS = 1_200_000


def _cutoffs(values, trim):
    histogram = Counter(values)
    n = len(values)
    start = (n-1)*trim//10_000
    stop = n-1-start
    running = 0
    low = high = None
    for key, amount in sorted(histogram.items()):
        running += amount
        if running > start and low is None:
            low = key
        if running > stop:
            high = key
            break
    return low, high


def _despeckle(values, width, height, deviation):
    updated = bytearray(values)
    count = 0
    if deviation == 0:
        return updated, count
    for y in range(1, height-1):
        for x in range(1, width-1):
            index = y*width+x
            old = values[index]
            adjacent = [values[(y+i)*width+x+j] for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j]
            if sum(abs(item-old) < deviation for item in adjacent) >= 2:
                continue
            ordered = sorted(adjacent)
            mid = (ordered[3]+ordered[4])//2
            if abs(old-mid) >= deviation and ordered[-1]-ordered[0] <= deviation:
                updated[index] = mid
                count += 1
    return updated, count


def _integral(values, width, height):
    stride = width+1
    summary = array("I", [0])*(stride*(height+1))
    for y in range(height):
        row_total = 0
        for x in range(width):
            row_total += values[y*width+x]
            summary[(y+1)*stride+x+1] = summary[y*stride+x+1]+row_total
    return summary, stride


def _threshold(values, width, height, radius, offset, light):
    integral, stride = _integral(values, width, height)
    result = bytearray(len(values))
    ink = 0
    for y in range(height):
        top, bottom = max(0, y-radius), min(height, y+radius+1)
        for x in range(width):
            left, right = max(0, x-radius), min(width, x+radius+1)
            area = (right-left)*(bottom-top)
            surrounding = (integral[bottom*stride+right]-integral[top*stride+right]
                           -integral[bottom*stride+left]+integral[top*stride+left])
            pixel = values[y*width+x]
            contrast = pixel*area-surrounding if light else surrounding-pixel*area
            selected = contrast >= offset*area
            result[y*width+x] = 0 if selected else 255
            ink += int(selected)
    return result, ink


def enhance(image_data, *, trim_bp=50, noise_delta=0, radius=8, offset=12, light_ink=False, binary=True):
    img = _raster.decode(image_data)
    if img.width*img.height > MAX_SCAN_PIXELS:
        raise ValueError("Pindaian terlalu besar untuk filter lokal.")
    trim = _integer(trim_bp, 0, 2000, "Trim intensitas")
    deviation = _integer(noise_delta, 0, 255, "Simpangan speckle")
    window = _integer(radius, 1, 128, "Radius lingkungan")
    difference = _integer(offset, 1, 255, "Kontras lingkungan")
    if type(light_ink) is not bool or type(binary) is not bool:
        raise ValueError("Polaritas dan mode biner perlu boolean.")
    normal = _vision.normalized(img)
    cleaned, count = _despeckle(normal, img.width, img.height, deviation)
    low, high = _cutoffs(cleaned, trim)
    changed = high > low
    if changed:
        stretch = bytes(max(0, min(255, (item-low)*255//(high-low))) for item in cleaned)
    else:
        stretch = cleaned
    ink = None
    if binary and changed:
        pixels, ink = _threshold(stretch, img.width, img.height, window, difference, light_ink)
    else:
        pixels = stretch
    payload = _vision.encode(img.width, img.height, pixels)
    report = {"schema": "ace.perception-scan-enhancement.v1", "source_sha256": sha256(image_data).hexdigest(),
              "output_sha256": sha256(payload).hexdigest(), "size": [img.width, img.height],
              "status": "processed" if changed else "flat_percentiles", "removed_speckles": count,
              "cutoffs_8bit": [low, high], "ink_pixels": ink, "binary_applied": bool(binary and changed),
              "policy": {"trim_bp": trim, "noise_delta": deviation, "radius": window, "offset": difference,
                         "light_ink": light_ink, "binary": binary}}
    return payload, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trim-bp", type=int, default=50)
    parser.add_argument("--noise-delta", type=int, default=0)
    parser.add_argument("--radius", type=int, default=8)
    parser.add_argument("--offset", type=int, default=12)
    parser.add_argument("--light-ink", action="store_true")
    parser.add_argument("--grayscale-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload, report = enhance(_raster.read(args.image), trim_bp=args.trim_bp, noise_delta=args.noise_delta,
                                  radius=args.radius, offset=args.offset, light_ink=args.light_ink,
                                  binary=not args.grayscale_only)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
