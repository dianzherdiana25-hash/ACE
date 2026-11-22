"""Buat animasi periodik tanpa frame terminal duplikat dan ukur langkah sambungan."""
import argparse
from math import cos, sin, tau
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, integer,
                         read, schema, text)
from ._raster import Raster, blank, color
from ._story_video import frame_hash, write_movie
from .video_composer import video_size


def _motion(index, count, w, h, rx, ry):
    phase = tau * (index % count) / count
    return (w // 2 + round(rx * cos(phase)), h // 2 + round(ry * sin(phase)))


def _circle(base, center, diameter, ink):
    data = bytearray(base.pixels)
    x, y = center
    radius = diameter // 2
    for row in range(y - radius, y + radius + 1):
        for col in range(x - radius, x + radius + 1):
            if (x - col)**2 + (y - row)**2 <= radius**2:
                offset = (row * base.width + col) * 3
                data[offset:offset + 3] = ink
    return Raster(base.width, base.height, bytes(data))


def make_loop(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.loop-plan.v1", ("source_ref", "width", "height", "frames", "fps",
                                           "background", "accent", "diameter", "radius_x", "radius_y"))
    source = text(plan["source_ref"], "Pointer motif")
    w, h = video_size(plan["width"], plan["height"])
    n = integer(plan["frames"], "Frame", 8, 200)
    fps = integer(plan["fps"], "FPS", 2, 30)
    diameter = integer(plan["diameter"], "Diameter", 4, min(w, h) // 2)
    rx = integer(plan["radius_x"], "Radius X", 2, w // 2 - diameter // 2 - 1)
    ry = integer(plan["radius_y"], "Radius Y", 2, h // 2 - diameter // 2 - 1)
    if n * w * h > 27_000_000:
        raise ContractError("Anggaran loop melebihi batas.")
    bg, foreground = [color(plan[key]) for key in ("background", "accent")]
    if bg[3] != 255 or foreground[3] != 255 or bg == foreground:
        raise ContractError("Palet loop harus opaque dan berbeda.")
    positions = [_motion(index, n, w, h, rx, ry) for index in range(n)]
    virtual = _motion(n, n, w, h, rx, ry)
    if positions[-1] == positions[0] or len(set(positions)) < 6:
        raise ContractError("Gerak loop tidak cukup untuk mencegah frame sambungan ganda.")
    jumps = [(a[0] - b[0])**2 + (a[1] - b[1])**2 for a, b in zip(positions, positions[1:] + [virtual], strict=True)]
    if jumps[-1] > max(jumps[:-1]):
        raise ContractError("Sambungan loop melebihi langkah gerak di bagian tengah.")
    base = blank(w, h, bg[:3])
    hashes = []

    def images():
        for center in positions:
            image = _circle(base, center, diameter, bytes(foreground[:3]))
            hashes.append(frame_hash(image))
            yield image

    output, report = write_movie(images(), w, h, fps)
    return output, {"schema": "ace.media.loop-receipt.v1", "plan_sha256": expected, "source_ref": source,
                    "centers": [list(pos) for pos in positions], "virtual_terminal": list(virtual),
                    "seam_jump_squared_px": jumps[-1], "max_internal_jump_squared_px": max(jumps[:-1]),
                    "source_frame_sha256": hashes, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = make_loop(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
