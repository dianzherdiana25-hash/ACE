"""Buat keluaran berbeda rasio dengan crop fokus yang terukur."""
import argparse
from pathlib import Path
import sys

from ._audio import wav
from ._clip_edit import open_clip
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema)
from ._raster import Raster
from ._story_video import write_movie
from .media_compressor import scale_frame
from .video_composer import video_size


def _crop(frame, shape):
    x, y, width, height = shape
    pixels = b"".join(frame.pixels[(row * frame.width + x) * 3:(row * frame.width + x + width) * 3]
                      for row in range(y, y + height))
    return Raster(width, height, pixels)


def _center(size, span, focus):
    return max(0, min(size - span, (size * focus // 10000) - span // 2))


def adapt_aspect(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.aspect-plan.v1", ("source", "outputs"))
    frames, fps, audio = open_clip(root, plan["source"])
    w, h = frames[0].width, frames[0].height
    outputs = {}
    measurements = []
    for row in entries(plan["outputs"], 5, 1):
        obj(row, ("id", "width", "height", "focus_x_bp", "focus_y_bp"))
        key = identifier(row["id"], "Versi rasio")
        if key in outputs:
            raise ContractError("ID rasio duplikat.")
        target_w, target_h = video_size(row["width"], row["height"])
        x = integer(row["focus_x_bp"], "Fokus X", 0, 10000)
        y = integer(row["focus_y_bp"], "Fokus Y", 0, 10000)
        if target_w * h <= target_h * w:
            width, height = max(1, target_w * h // target_h), h
        else:
            width, height = w, max(1, target_h * w // target_w)
        if target_w * target_h * len(frames) > 27_000_000:
            raise ContractError("Anggaran piksel frame keluaran terlampaui.")
        shape = (_center(w, width, x), _center(h, height, y), width, height)
        selected = (scale_frame(_crop(frame, shape), target_w, target_h) for frame in frames)
        output, info = write_movie(selected, target_w, target_h, fps, wav(audio) if audio else None)
        outputs[key] = output
        measurements.append({"id": key, "source_crop": list(shape), "focus_bp": [x, y], **info})
    return outputs, {"schema": "ace.media.aspect-receipt.v1", "plan_sha256": expected,
                     "source_sha256": plan["source"]["sha256"], "outputs": measurements}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, receipt = adapt_aspect(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        args.output.mkdir()
        for name, data in files.items():
            (args.output / f"{name}.mp4").write_bytes(data)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
