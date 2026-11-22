"""Render sampul orisinal dengan judul yang diperiksa ulang dari piksel."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, identifier,
                         identity, integer, read, schema, text)
from ._lettering import break_lines, stamp, width
from ._raster import color, png, raster
from .image_generator import render
from .image_qa import evaluate


def make_cover(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.cover-plan.v1", ("id", "source_ref", "title", "background",
                                             "accent", "foreground", "width", "height", "minimum_contrast_milli"))
    design = identifier(plan["id"], "Desain")
    source = text(plan["source_ref"], "Pointer arahan")
    title = text(plan["title"], "Judul", 85)
    bg, accent, fg = (color(plan[key]) for key in ("background", "accent", "foreground"))
    if any(value[-1] != 255 for value in (bg, accent, fg)):
        raise ContractError("Warna perlu opaque untuk QA kontras.")
    width_px = integer(plan["width"], "Lebar", 80, 1000)
    height = integer(plan["height"], "Tinggi", 56, 1000)
    limit = integer(plan["minimum_contrast_milli"], "Rasio minimum", 3000, 21000)
    margin = max(5, width_px // 12)
    scale = max(1, min(width_px // 58, height // 34))
    for size in range(scale, 0, -1):
        usable = max(1, (width_px - 2 * margin + size) // (6 * size))
        try:
            lines = break_lines(title, usable, 3)
        except ContractError:
            continue
        if (len(lines) * 9 - 2) * size <= height - 2 * margin:
            scale = size
            break
    else:
        raise ContractError("Judul tidak dapat ditata tanpa pemotongan.")
    hex_bg = "#{:02x}{:02x}{:02x}".format(*bg[:3])
    hex_accent = "#{:02x}{:02x}{:02x}".format(*accent[:3])
    outline = {"schema": "ace.media.image-plan.v1", "id": design, "source_ref": source, "format": "png",
               "instructions": f"CANVAS {width_px} {height} {hex_bg}\n"
                               f"RECT 0 {height - margin} {width_px} {margin} {hex_accent}"}
    raw, _ = render(outline, identity(outline))
    image = raster(raw)
    y = max(2, (height - margin - (9 * len(lines) - 2) * scale) // 2)
    regions = []
    layout = []
    for index, row in enumerate(lines):
        start = (width_px - width(row, scale)) // 2
        image, foreground = stamp(image, row, start, y, scale, fg[:3])
        layout.append({"line": row, "x": start, "y": y, "scale": scale})
        regions.append({"id": f"title_{index}", "ink": foreground, "background": [1, 1, 2, 2],
                        "minimum_ratio_milli": limit, "source_ref": source})
        y += 9 * scale
    data = png(image)
    digest = sha256(data).hexdigest()
    qa_plan = {"schema": "ace.media.image-qa-plan.v1", "source_ref": source, "image_sha256": digest,
               "minimum_width": width_px, "minimum_height": height, "max_clipped_bp": 10000,
               "min_range": 0, "min_edge_delta": 0, "require_text_regions": True, "text_regions": regions}
    report = evaluate(data, qa_plan, identity(qa_plan))
    return data, {"schema": "ace.media.cover-receipt.v1", "id": design, "plan_sha256": expected,
                  "title": title, "layout": layout, "image_sha256": digest,
                  "measurements": report, "status": report["status"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        image, report = make_cover(decode(read(args.plan)), args.expect_sha256)
        if report["status"] == "pass":
            with args.output.open("xb") as stream:
                stream.write(image)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
