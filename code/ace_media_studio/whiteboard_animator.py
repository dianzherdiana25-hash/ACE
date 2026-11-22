"""Perlihatkan urutan stroke papan tulis dengan waktu per jejak dan piksel aktual."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)
from ._raster import Raster, blank, color
from ._story_video import frame_hash, write_movie
from .video_composer import video_size


def _points(raw, w, h):
    for value in entries(raw, 70, 2):
        if not isinstance(value, list) or len(value) != 2:
            raise ContractError("Titik stroke perlu pasangan integer.")
        yield (integer(value[0], "X", 0, w - 1), integer(value[1], "Y", 0, h - 1))


def _line_grid(vertices):
    sampled = [vertices[0]]
    for (x, y), (end_x, end_y) in zip(vertices, vertices[1:]):
        length = max(abs(x - end_x), abs(y - end_y))
        for pos in range(1, length + 1):
            sampled.append(((x * (length - pos) + end_x * pos) // length,
                            (y * (length - pos) + end_y * pos) // length))
        if len(sampled) > 12_000:
            raise ContractError("Panjang raster stroke melebihi batas.")
    return sampled


def _draw(pixels, coordinates, thickness, rgb, w, h):
    for x, y in coordinates:
        for row in range(max(0, y - thickness), min(h, y + thickness + 1)):
            for col in range(max(0, x - thickness), min(w, x + thickness + 1)):
                if (row - y)**2 + (col - x)**2 <= thickness**2:
                    offset = (row * w + col) * 3
                    pixels[offset:offset + 3] = rgb


def animate_board(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.whiteboard-plan.v1", ("source_ref", "width", "height", "fps", "strokes"))
    source = text(plan["source_ref"], "Pointer sketsa")
    w, h = video_size(plan["width"], plan["height"])
    fps = integer(plan["fps"], "FPS", 2, 24)
    stage = []
    seen = set()
    cursor = 0
    for row in entries(plan["strokes"], 32, 1):
        obj(row, ("id", "color", "radius", "points", "frames"))
        name = identifier(row["id"], "Stroke")
        if name in seen:
            raise ContractError("ID stroke ganda.")
        seen.add(name)
        rgba = color(row["color"])
        if rgba[3] != 255:
            raise ContractError("Tinta stroke perlu opaque.")
        coords = _line_grid(list(_points(row["points"], w, h)))
        count = integer(row["frames"], "Durasi stroke", 1, 90)
        report = {"id": name, "first_frame": cursor, "end_frame_exclusive": cursor + count, "ink_points": len(coords)}
        cursor += count
        if cursor > 450 or cursor * w * h > 27_000_000:
            raise ContractError("Papan tulis melampaui anggaran.")
        stage.append((coords, integer(row["radius"], "Radius pena", 1, 8), bytes(rgba[:3]), report))
    hashes = []
    white = blank(w, h, (245, 244, 233))

    def frames():
        pixels = bytearray(white.pixels)
        for coords, radius, rgb, report in stage:
            count = report["end_frame_exclusive"] - report["first_frame"]
            rendered = 0
            for index in range(1, count + 1):
                target = (len(coords) * index + count - 1) // count
                _draw(pixels, coords[rendered:target], radius, rgb, w, h)
                rendered = target
                frame = Raster(w, h, bytes(pixels))
                hashes.append(frame_hash(frame))
                yield frame

    output, report = write_movie(frames(), w, h, fps)
    return output, {"schema": "ace.media.whiteboard-receipt.v1", "plan_sha256": expected, "source_ref": source,
                    "strokes": [row for _, _, _, row in stage], "source_frame_sha256": hashes, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = animate_board(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
