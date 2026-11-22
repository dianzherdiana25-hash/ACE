"""Ambil still dari timeline dan rakit poster dengan judul pada pita tersendiri."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._clip_edit import open_clip
from ._contracts import ContractError, canonical, checked, decode, integer, read, schema, text
from ._lettering import break_lines, stamp, width
from ._raster import Raster, blank, png
from ._story_video import frame_hash
from .aspect_adapter import _center, _crop
from .media_compressor import scale_frame
from .preview_renderer import _place


def poster(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.still-poster.v1", ("source", "frame", "width", "height", "focus_x_bp",
                                              "focus_y_bp", "title", "source_ref"))
    source = text(plan["source_ref"], "Pointer pilihan adegan")
    frames, fps, _ = open_clip(root, plan["source"])
    index = integer(plan["frame"], "Posisi still", 0, len(frames) - 1)
    w = integer(plan["width"], "Lebar poster", 96, 800)
    h = integer(plan["height"], "Tinggi poster", 80, 800)
    scene = frames[index]
    title = break_lines(text(plan["title"], "Judul", 60), (w - 10) // 12, 2)
    footer = len(title) * 17 + 12
    height = h - footer
    if w * scene.height <= height * scene.width:
        width_src, height_src = max(1, scene.height * w // height), scene.height
    else:
        width_src, height_src = scene.width, max(1, scene.width * height // w)
    x = _center(scene.width, width_src, integer(plan["focus_x_bp"], "Fokus X", 0, 10000))
    y = _center(scene.height, height_src, integer(plan["focus_y_bp"], "Fokus Y", 0, 10000))
    crop = scale_frame(_crop(scene, (x, y, width_src, height_src)), w, height)
    slate = blank(w, h, (20, 28, 42))
    grid = bytearray(slate.pixels)
    _place(grid, w, crop, 0, 0)
    image = Raster(w, h, bytes(grid))
    for line, label in enumerate(title):
        image, _ = stamp(image, label, (w - width(label, 2)) // 2, height + 5 + line * 17, 2, (240, 231, 200))
    payload = png(image)
    return payload, {"schema": "ace.media.poster-receipt.v1", "plan_sha256": expected, "source_ref": source,
                     "video_sha256": plan["source"]["sha256"], "selected_frame_sha256": frame_hash(scene),
                     "source_frame": index, "timestamp_ms": index * 1000 // fps, "source_crop": [x, y, width_src, height_src],
                     "title_lines": title, "poster_sha256": sha256(payload).hexdigest(), "dimensions": [w, h]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = poster(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
