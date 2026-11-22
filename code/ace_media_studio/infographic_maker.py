"""Tampilkan perbandingan dari CSV dengan skala bar nol dan pointer pada data sumber."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, digest,
                         integer, read, schema, text)
from ._lettering import break_lines, stamp, width
from ._raster import Raster, blank, color, png


def _rect(image, coords, ink):
    x, y, w, h = coords
    if not (0 <= x <= x + w <= image.width and 0 <= y <= y + h <= image.height):
        raise ContractError("Kotak grafis di luar kanvas.")
    pixels = bytearray(image.pixels)
    bar = bytes(ink) * w
    for row in range(y, y + h):
        offset = (image.width * row + x) * 3
        pixels[offset:offset + len(bar)] = bar
    return Raster(image.width, image.height, bytes(pixels))


def _read_csv(raw):
    try:
        reader = csv.reader(StringIO(raw.decode("utf-8")), strict=True)
        if next(reader, None) != ["label", "value", "source_ref"]:
            raise ContractError("CSV perlu kolom label,value,source_ref.")
        seen = set()
        data = []
        for position, row in enumerate(reader, 2):
            if len(row) != 3 or position > 17:
                raise ContractError("CSV perlu 1–16 baris dalam schema sumber.")
            label = text(row[0], "Label", 20).upper()
            value = Decimal(row[1])
            if not value.is_finite() or value < 0 or value > 10**9 or not -4 <= value.as_tuple().exponent <= 9:
                raise ContractError("Nilai grafik perlu desimal nonnegatif sampai empat digit pecahan.")
            if label in seen:
                raise ContractError("Label grafik duplikat.")
            seen.add(label)
            data.append((label, value, text(row[2], "Pointer nilai"), position))
        return data
    except (InvalidOperation, csv.Error) as error:
        raise ContractError("CSV angka tidak valid.") from error


def make_infographic(raw, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.infographic-plan.v1", ("csv_sha256", "title", "unit", "width", "descending"))
    anchor = digest(plan["csv_sha256"])
    if sha256(raw).hexdigest() != anchor:
        raise ContractError("CSV berbeda dari anchor.")
    width_px = integer(plan["width"], "Lebar", 320, 800)
    title = break_lines(text(plan["title"], "Judul", 80), (width_px - 16) // 12, 2)
    unit = break_lines(text(plan["unit"], "Satuan", 40), 20, 1)[0]
    if type(plan["descending"]) is not bool:
        raise ContractError("Arah urut perlu boolean.")
    data = _read_csv(raw)
    if not data:
        raise ContractError("CSV tidak berisi angka.")
    if plan["descending"]:
        data.sort(key=lambda row: (-row[1], row[0]))
    maximum = max(row[1] for row in data)
    dark, pale, blue = map(lambda value: color(value)[:3], ("#1C2C3A", "#F0F4F6", "#2D719B"))
    label_width = max(width(break_lines(row[0], 20, 1)[0], 1) for row in data)
    bar_start = label_width + 28
    bar_length = width_px - bar_start - 120
    image = blank(width_px, 45 + 17 * len(data) + 18 * len(title), pale)
    y = 7
    for phrase in title:
        image, _ = stamp(image, phrase, 8, y, 2, dark)
        y += 18
    image, _ = stamp(image, unit, 8, y + 1, 1, dark)
    y += 18
    image = _rect(image, (bar_start - 2, y - 3, 1, 17 * len(data)), dark)
    values = []
    for label, value, pointer, position in data:
        size = int(value * bar_length / maximum) if maximum else 0
        notation = format(value, "f")
        image = _rect(image, (bar_start, y, size, 9), blue)
        image, _ = stamp(image, break_lines(label, 20, 1)[0], 8, y + 1, 1, dark)
        image, _ = stamp(image, notation, width_px - 8 - width(notation, 1), y + 1, 1, dark)
        values.append({"label": label, "value": notation, "source_ref": pointer, "csv_line": position,
                       "bar_pixels": size, "rect": [bar_start, y, size, 9]})
        y += 17
    result = png(image)
    return result, {"schema": "ace.media.infographic-receipt.v1", "plan_sha256": expected, "csv_sha256": anchor,
                    "png_sha256": sha256(result).hexdigest(), "scaling": {"minimum": "0", "maximum": format(maximum, "f"),
                     "length_px": bar_length, "unit": unit}, "bars": values}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, receipt = make_infographic(read(args.csv), decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
