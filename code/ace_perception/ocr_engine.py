"""Baca teks cetak PGM dengan dua penilai geometri yang harus sepakat.

Font grid didaftarkan dari berkas caller dan hash semata menyatakan
byte yang dipakai. Layout stroke dipisahkan lewat proyeksi tinta.
Voting silhouette dan proyeksi/transisi mengembalikan ketidakpastian
per glyph saat jarak terlalu besar, seri, atau pilihan tak sepakat.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys

from . import _raster


MAX_GLYPHS = 1024
MAX_TEMPLATES = 128
MAX_SIDE = 24
MAX_FONT_BYTES = 250_000
MAX_COMPARISONS = 30_000_000


def _matrix(rows, size=None):
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], str):
        raise ValueError("Template perlu baris grid biner.")
    width, height = len(rows[0]), len(rows)
    if not (1 <= width <= MAX_SIDE and 1 <= height <= MAX_SIDE):
        raise ValueError("Ukuran grid font di luar batas.")
    if size is not None and (width, height) != size:
        raise ValueError("Dimensi grid template tidak sama.")
    cells = []
    for row in rows:
        if not isinstance(row, str) or len(row) != width or set(row) - {"0", "1"}:
            raise ValueError("Baris template berbeda panjang atau bukan grid biner.")
        cells.extend(int(symbol) for symbol in row)
    if not any(cells):
        raise ValueError("Glyph kosong.")
    return width, height, tuple(cells)


def _signature(width, height, mask):
    columns = [tuple(mask[x::width]) for x in range(width)]
    lines = [mask[offset:offset+width] for offset in range(0, width*height, width)]
    return tuple(value for band in lines+columns for value in
                 (sum(band), sum(first != second for first, second in zip(band, band[1:]))))


def _aspect(width, height):
    return 10_000*width//(width+height)


def _silhouette(width, height, cells):
    xy = [(index % width, index // width) for index, value in enumerate(cells) if value]
    left = min(x for x, _ in xy)
    top = min(y for _, y in xy)
    right = max(x for x, _ in xy)+1
    bottom = max(y for _, y in xy)+1
    trimmed = [cells[y*width+x] for y in range(top, bottom) for x in range(left, right)]
    crop_width, crop_height = right-left, bottom-top
    return _scale(crop_width, crop_height, trimmed, width, height), _aspect(crop_width, crop_height)


def _scale(width, height, values, target_width, target_height):
    indices = [min(width-1, (2*x+1)*width//(2*target_width)) for x in range(target_width)]
    return tuple(values[min(height-1, (2*y+1)*height//(2*target_height))*width+x]
                 for y in range(target_height) for x in indices)


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError("Kunci JSON font ganda.")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class Template:
    label: str
    mask: tuple[int, ...]
    signature: tuple[int, ...]
    aspect_bp: int


@dataclass(frozen=True, slots=True)
class Font:
    width: int
    height: int
    templates: tuple[Template, ...]
    checksum: str

    @classmethod
    def decode(cls, data):
        if not isinstance(data, bytes) or len(data) > MAX_FONT_BYTES:
            raise ValueError("Font melebihi batas byte.")
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
        if not isinstance(raw, dict) or set(raw) != {"schema", "glyphs"} or raw["schema"] != "ace.perception-font.v1":
            raise ValueError("Skema font tidak dikenal.")
        glyphs = raw["glyphs"]
        if not isinstance(glyphs, dict) or not 1 <= len(glyphs) <= MAX_TEMPLATES:
            raise ValueError("Jumlah glyph font di luar batas.")
        dimension = None
        masks = set()
        templates = []
        for key, bits in sorted(glyphs.items()):
            if len(key) != 1 or not key.isprintable() or key.isspace() or key == "\ufffd":
                raise ValueError("Label font perlu satu karakter cetak.")
            width, height, pixels = _matrix(bits, dimension)
            dimension = width, height
            normal, aspect = _silhouette(width, height, pixels)
            key_shape = (normal, aspect)
            if key_shape in masks:
                raise ValueError("Bentuk glyph ganda setelah normalisasi.")
            masks.add(key_shape)
            templates.append(Template(key, normal, _signature(width, height, normal), aspect))
        return cls(width, height, tuple(templates), sha256(data).hexdigest())


def _otsu(samples, cap):
    histogram = [0]*(cap+1)
    for value, count in Counter(samples).items():
        histogram[value] = count
    if sum(count > 0 for count in histogram) <= 1:
        return None
    total = sum(histogram)
    brightness = sum(value * weight for value, weight in enumerate(histogram))
    left = weighted = 0
    best = (0, 1)
    threshold = None
    for value, count in enumerate(histogram[:-1]):
        left += count
        weighted += value*count
        right = total-left
        if not left or not right:
            continue
        candidate = ((weighted*total - brightness*left)**2, left*right)
        if threshold is None or candidate[0]*best[1] > best[0]*candidate[1]:
            threshold, best = value, candidate
    return threshold


def _bands(sequence):
    beginning = None
    for index, filled in enumerate(sequence):
        if filled and beginning is None:
            beginning = index
        if not filled and beginning is not None:
            yield beginning, index
            beginning = None
    if beginning is not None:
        yield beginning, index+1


def _regions(mask, width, height):
    rows = (any(mask[y*width:(y+1)*width]) for y in range(height))
    consumed = 0
    for y0, y1 in _bands(rows):
        columns = (any(mask[y*width+x] for y in range(y0, y1)) for x in range(width))
        glyphs = []
        for x0, x1 in _bands(columns):
            ys = [y for y in range(y0, y1) if any(mask[y*width+x] for x in range(x0, x1))]
            glyphs.append((x0, ys[0], x1, ys[-1]+1))
            consumed += 1
            if consumed > MAX_GLYPHS:
                raise ValueError("Jumlah wilayah glyph melebihi batas.")
        yield glyphs


def _vote(scores, maximum, limit):
    ordered = sorted(scores)
    distance, preferred = ordered[0]
    gap = ordered[1][0]-distance if len(ordered) > 1 else None
    accepted = distance * 10_000 <= limit * maximum and gap != 0
    return {"label": preferred if accepted else None, "distance": distance,
            "maximum_distance": maximum, "second_margin": gap}


def _read_glyph(box, mask, image_width, font, limit):
    x0, y0, x1, y1 = box
    raw = [mask[y*image_width+x] for y in range(y0, y1) for x in range(x0, x1)]
    scaled = _scale(x1-x0, y1-y0, raw, font.width, font.height)
    signature = _signature(font.width, font.height, scaled)
    aspect = _aspect(x1-x0, y1-y0)
    pixel_cap = len(scaled)
    projection_cap = 4*len(scaled)-font.width-font.height
    distances = []
    outlines = []
    for entry in font.templates:
        aspect_error = abs(aspect-entry.aspect_bp)
        pixel_error = sum(a != b for a, b in zip(scaled, entry.mask, strict=True))
        projection_error = sum(abs(a-b) for a, b in zip(signature, entry.signature, strict=True))
        distances.append((10_000*pixel_error + pixel_cap*aspect_error, entry.label))
        outlines.append((10_000*projection_error + projection_cap*aspect_error, entry.label))
    pixels = _vote(distances, 20_000*pixel_cap, limit)
    projection = _vote(outlines, 20_000*projection_cap, limit)
    same = pixels["label"] is not None and pixels["label"] == projection["label"]
    return {"box": list(box), "character": pixels["label"] if same else "\ufffd",
            "status": "agreed" if same else "unresolved", "pixel_vote": pixels, "projection_vote": projection}


def recognize(image_data, font_data, *, light_ink=False, limit_bp=2000, word_gap=3):
    if type(light_ink) is not bool or type(limit_bp) is not int or not 0 <= limit_bp <= 10_000:
        raise ValueError("Polaritas atau batas jarak glyph tidak sah.")
    if type(word_gap) is not int or not 1 <= word_gap <= 4096:
        raise ValueError("Jeda kata harus integer dalam rentang 1–4096.")
    image = _raster.decode(image_data)
    font = Font.decode(font_data)
    threshold = _otsu(image.pixels, image.maximum)
    lines = []
    words = []
    if threshold is not None:
        mask = tuple((value > threshold) if light_ink else (value <= threshold) for value in image.pixels)
        regions = list(_regions(mask, image.width, image.height))
        cells = sum(map(len, regions))*len(font.templates)*font.width*font.height
        if cells > MAX_COMPARISONS:
            raise ValueError("Perbandingan OCR melampaui batas kerja.")
        for boxes in regions:
            current = []
            previous = None
            readings = []
            for box in boxes:
                if previous is not None and box[0]-previous >= word_gap:
                    current.append(" ")
                reading = _read_glyph(box, mask, image.width, font, limit_bp)
                current.append(reading["character"])
                readings.append(reading)
                previous = box[2]
            text = "".join(current)
            words.append(text)
            lines.append({"text": text, "glyphs": readings})
    count = sum(len(line["glyphs"]) for line in lines)
    unresolved = sum(glyph["status"] == "unresolved" for line in lines for glyph in line["glyphs"])
    return {"schema": "ace.perception-ocr.v1", "image_sha256": sha256(image_data).hexdigest(),
            "font_sha256": font.checksum, "width": image.width, "height": image.height, "threshold": threshold,
            "text": "\n".join(words), "glyph_count": count, "unresolved_count": unresolved,
            "status": "empty" if not count else "partial" if unresolved else "read", "lines": lines}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("--light-ink", action="store_true")
    parser.add_argument("--limit-bp", type=int, default=2000)
    parser.add_argument("--word-gap", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        result = recognize(_raster.read(args.image), _raster.read(args.font, MAX_FONT_BYTES),
                           light_ink=args.light_ink, limit_bp=args.limit_bp, word_gap=args.word_gap)
        sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "read")


if __name__ == "__main__":
    raise SystemExit(main())
