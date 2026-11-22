"""Rakit gambar reaksi dari template, aset berizin, dan caption yang muat pada raster."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         identity, integer, obj, read, schema, text)
from ._lettering import break_lines, stamp, width
from ._raster import MAX_BYTES, Raster, color, png, raster
from .image_qa import evaluate


def compose_template(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.reaction-plan.v1", ("template", "captions"))
    template = obj(plan["template"], ("id", "path", "sha256", "license_ref", "slots"))
    key = identifier(template["id"], "ID template")
    source = text(template["license_ref"], "Izin templat")
    image = raster(asset(root, template["path"], template["sha256"], MAX_BYTES))
    slots = {}
    boxes = []
    for row in entries(template["slots"], 10, 1):
        obj(row, ("id", "x", "y", "width", "height", "ink", "fill"))
        name = identifier(row["id"], "Slot caption")
        if name in slots:
            raise ContractError("Nama slot caption ganda.")
        x = integer(row["x"], "X", 0, image.width - 1)
        y = integer(row["y"], "Y", 0, image.height - 1)
        w = integer(row["width"], "Lebar", 16, image.width - x)
        h = integer(row["height"], "Tinggi", 12, image.height - y)
        if any(x < r and x + w > l and y < b and y + h > t for l, t, r, b in boxes):
            raise ContractError("Slot caption bertumpang tindih.")
        boxes.append((x, y, x + w, y + h))
        ink, fill = color(row["ink"]), color(row["fill"])
        if ink[3] != 255 or fill[3] != 255:
            raise ContractError("Slot caption perlu warna opaque.")
        slots[name] = x, y, w, h, ink[:3], fill[:3]
    captions = {}
    for row in entries(plan["captions"], 10, 1):
        obj(row, ("id", "text", "source_ref"))
        name = identifier(row["id"], "Caption")
        if name not in slots or name in captions:
            raise ContractError("Caption untuk slot tak terdaftar atau ganda.")
        captions[name] = (text(row["text"], "Caption", 120), text(row["source_ref"], "Pointer caption"))
    if slots.keys() != captions.keys():
        raise ContractError("Ada slot template belum terisi.")
    layout = []
    regions = []
    for name, (x, y, w, h, ink, fill) in slots.items():
        phrase, ref = captions[name]
        pixels = bytearray(image.pixels)
        bar = bytes(fill) * w
        for row in range(y, y + h):
            start = (row * image.width + x) * 3
            pixels[start:start + len(bar)] = bar
        image = Raster(image.width, image.height, bytes(pixels))
        for scale in range(min(6, (h - 4) // 7), 0, -1):
            try:
                lines = break_lines(phrase, (w - 4 + scale) // (6 * scale), 3)
            except ContractError:
                continue
            if (len(lines) * 9 - 2) * scale <= h - 4:
                break
        else:
            raise ContractError(f"Caption untuk {name} tidak muat.")
        baseline = y + (h - (len(lines) * 9 - 2) * scale) // 2
        for line in lines:
            image, point = stamp(image, line, x + (w - width(line, scale)) // 2, baseline, scale, ink)
            regions.append({"id": f"caption_{len(regions)}", "source_ref": ref, "ink": point,
                            "background": [x, y, 1, 1], "minimum_ratio_milli": 4500})
            baseline += 9 * scale
        layout.append({"slot": name, "source_ref": ref, "lines": lines, "scale": scale})
    result = png(image)
    digest = sha256(result).hexdigest()
    qa_plan = {"schema": "ace.media.image-qa-plan.v1", "source_ref": source, "image_sha256": digest,
               "minimum_width": image.width, "minimum_height": image.height, "max_clipped_bp": 10000,
               "min_range": 0, "min_edge_delta": 0, "require_text_regions": True, "text_regions": regions}
    qa = evaluate(result, qa_plan, identity(qa_plan))
    return result if qa["status"] == "pass" else None, {"schema": "ace.media.reaction-receipt.v1",
            "plan_sha256": expected, "template": key, "template_sha256": template["sha256"], "license_ref": source,
            "layout": layout, "status": qa["status"], "image_qa": qa}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = compose_template(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        if data is not None:
            with args.output.open("xb") as stream:
                stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(data is None)


if __name__ == "__main__":
    raise SystemExit(main())
