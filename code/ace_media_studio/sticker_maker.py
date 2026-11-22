"""Buat stiker RGBA asli dengan alpha dari siluet dan label pose yang unik."""
import argparse
from hashlib import sha256
from pathlib import Path
from struct import pack
import sys
from zlib import compress

from ._contracts import ContractError, canonical, checked, decode, entries, identity, integer, read, schema
from ._raster import PNG, _chunk, color, raster
from .character_keeper import portrait


def _transparency(image, bg, edge):
    rows = []
    opaque = 0
    border = 0
    pixels = [tuple(image.pixels[index:index + 3]) != bg for index in range(0, len(image.pixels), 3)]
    for y in range(image.height):
        line = bytearray(b"\0")
        for x in range(image.width):
            offset = y * image.width + x
            if pixels[offset]:
                line.extend((*image.at(x, y), 255))
                opaque += 1
            elif edge and any(pixels[dy * image.width + dx] for dx, dy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                              if 0 <= dx < image.width and 0 <= dy < image.height):
                line.extend((255, 255, 255, 255))
                border += 1
            else:
                line.extend((0, 0, 0, 0))
        rows.append(bytes(line))
    header = pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)
    data = PNG + _chunk(b"IHDR", header) + _chunk(b"IDAT", compress(b"".join(rows), 6)) + _chunk(b"IEND", b"")
    return data, {"opaque_character_pixels": opaque, "border_pixels": border,
                  "transparent_pixels": image.width * image.height - opaque - border}


def make_stickers(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.sticker-plan.v1", ("character", "poses", "border"))
    border = integer(plan["border"], "Outline stiker", 0, 1)
    poses = entries(plan["poses"], 4, 1)
    if len(poses) != len(set(poses)):
        raise ContractError("Pose stiker ganda.")
    images = {}
    records = []
    character = plan["character"]
    for pose in poses:
        result, receipt = portrait(character, identity(character), pose)
        background = color(character["palette"]["background"])[:3]
        raw, measured = _transparency(raster(result), background, border)
        if not measured["transparent_pixels"] or not measured["opaque_character_pixels"]:
            raise ContractError("Stiker perlu area transparan dan siluet.")
        images[f"{pose}.png"] = raw
        records.append({"pose": pose, "sticker_sha256": sha256(raw).hexdigest(),
                        "source_portrait_sha256": receipt["image_sha256"], **measured})
    return images, {"schema": "ace.media.sticker-receipt.v1", "plan_sha256": expected,
                    "format": "png_rgba", "bible_sha256": identity(character), "stickers": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        results, report = make_stickers(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for name, raw in results.items():
            (args.output / name).write_bytes(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
