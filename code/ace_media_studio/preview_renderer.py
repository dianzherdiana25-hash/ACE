"""Buat contact sheet preview hemat dari gambar atau frame terpilih MP4, tanpa mengubah aset."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._contracts import (ContractError, canonical, checked, decode, digest, integer,
                         read, schema, text)
from ._lettering import stamp
from ._raster import MAX_BYTES, Raster, blank, png, raster
from ._video import MAX_MOVIE, load_movie
from .media_compressor import scale_frame


def _place(grid, grid_width, image, x, y):
    stride = image.width * 3
    for row in range(image.height):
        left = ((y + row) * grid_width + x) * 3
        grid[left:left + stride] = image.pixels[row * stride:(row + 1) * stride]


def preview(data, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.preview-plan.v1", ("source_ref", "source_sha256", "media_type", "samples",
                                               "columns", "tile_width", "tile_height"))
    source = text(plan["source_ref"], "Pointer media")
    anchor = digest(plan["source_sha256"])
    if sha256(data).hexdigest() != anchor:
        raise ContractError("Media sumber tidak sesuai anchor.")
    limit = integer(plan["samples"], "Frame diambil", 1, 16)
    if plan["media_type"] == "image":
        frames = [raster(data)]
        fps = None
    elif plan["media_type"] == "video":
        if len(data) > MAX_MOVIE:
            raise ContractError("MP4 melampaui anggaran byte.")
        with TemporaryDirectory(prefix="ace-media-preview-") as temporary:
            frames, fps, _ = load_movie(Path(temporary), data)
    else:
        raise ContractError("Jenis preview harus image atau video.")
    count = min(limit, len(frames))
    indices = [(len(frames) - 1) * index // (count - 1) for index in range(count)] if count > 1 else [0]
    cols = min(integer(plan["columns"], "Kolom contact sheet", 1, 4), count)
    rows = (count + cols - 1) // cols
    width = integer(plan["tile_width"], "Lebar tile", 36, 200)
    height = integer(plan["tile_height"], "Tinggi tile", 30, 150)
    gap = 5
    grid_width = cols * (width + gap) + gap
    grid_height = rows * (height + 16 + gap) + 22
    slate = blank(grid_width, grid_height, (24, 28, 38))
    grid = bytearray(slate.pixels)
    windows = []
    for position, index in enumerate(indices):
        frame = frames[index]
        if width * frame.height <= height * frame.width:
            w, h = width, max(1, frame.height * width // frame.width)
        else:
            w, h = max(1, frame.width * height // frame.height), height
        thumb = scale_frame(frame, w, h)
        left = gap + position % cols * (width + gap)
        top = 20 + position // cols * (height + 16 + gap)
        x = left + (width - w) // 2
        y = top + (height - h) // 2
        _place(grid, grid_width, thumb, x, y)
        windows.append({"frame": index, "source_frame_sha256": frame.receipt()["rgb_sha256"],
                        "timestamp_ms": 1000 * index // fps if fps else None,
                        "tile": [x, y, w, h], "label": [left, top + height + 2]})
    sheet, _ = stamp(Raster(grid_width, grid_height, bytes(grid)), "PREVIEW", gap, 5, 1, (250, 220, 80))
    for item in windows:
        sheet, _ = stamp(sheet, f"F{item['frame']:03}", *item["label"], 1, (224, 226, 232))
    output = png(sheet)
    return output, {"schema": "ace.media.preview-receipt.v1", "plan_sha256": expected,
                    "source_sha256": anchor, "source_ref": source, "decoded_frames": len(frames),
                    "preview_png_sha256": sha256(output).hexdigest(), "tiles": windows,
                    "output_dimensions": [grid_width, grid_height]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        plan = decode(read(args.plan))
        cap = MAX_MOVIE if plan.get("media_type") == "video" else MAX_BYTES
        data, report = preview(read(args.input, cap), plan, args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
