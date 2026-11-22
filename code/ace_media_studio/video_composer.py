"""Buat video pendek dari adegan tertulis dengan timeline dan frame terverifikasi."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._assets import asset
from ._audio import MAX_WAV, parse_wav
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, identity, integer, obj, read, schema, text)
from ._raster import Raster, raster
from ._video import encode_frames
from .image_generator import render


def video_size(width, height):
    integer(width, "Lebar video", 16, 960)
    integer(height, "Tinggi video", 16, 960)
    if width % 2 or height % 2:
        raise ContractError("Lebar dan tinggi video perlu genap.")
    return width, height


def _xy(raw, label):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ContractError(f"{label} perlu dua koordinat.")
    return [integer(item, label, 0, 1500) for item in raw]


def _crop(frame, width, height, x, y):
    stride = frame.width * 3
    start = y * stride + x * 3
    return Raster(width, height, b"".join(frame.pixels[start + row * stride:start + row * stride + width * 3]
                                          for row in range(height)))


def _prepared(plan, width, height):
    prepared = []
    seen = set()
    cursor = 0
    for scene in entries(plan["scenes"], 20, 1):
        obj(scene, ("id", "frames", "source_ref", "instructions", "from", "to"))
        key = identifier(scene["id"], "Adegan")
        if key in seen:
            raise ContractError("ID adegan ganda.")
        seen.add(key)
        count = integer(scene["frames"], "Frame adegan", 1, 450)
        cursor += count
        if cursor > 450 or cursor * width * height > 27_000_000:
            raise ContractError("Anggaran piksel-frame video terlampaui.")
        source = text(scene["source_ref"], "Rujukan adegan")
        image_plan = {"schema": "ace.media.image-plan.v1", "id": key, "source_ref": source,
                      "format": "png", "instructions": scene["instructions"]}
        data, report = render(image_plan, identity(image_plan))
        frame = raster(data)
        begin, end = _xy(scene["from"], "Awal kamera"), _xy(scene["to"], "Akhir kamera")
        if any(x + width > frame.width or y + height > frame.height for x, y in (begin, end)):
            raise ContractError("Kamera di luar bidang adegan.")
        prepared.append((frame, begin, end, {"id": key, "first_frame": cursor - count,
                                           "last_frame_exclusive": cursor, "source_ref": source,
                                           "scene_png_sha256": report["image_sha256"]}))
    return prepared, cursor


def _frames(prepared, width, height):
    for frame, begin, end, row in prepared:
        count = row["last_frame_exclusive"] - row["first_frame"]
        last = max(1, count - 1)
        for index in range(count):
            x, y = [(low * (last - index) + high * index) // last
                    for low, high in zip(begin, end, strict=True)]
            yield _crop(frame, width, height, x, y)


def compose(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.video-plan.v1", ("width", "height", "fps", "scenes", "soundtrack"))
    width, height = video_size(plan["width"], plan["height"])
    fps = integer(plan["fps"], "Frame rate", 2, 30)
    prepared, count = _prepared(plan, width, height)
    data = None
    if plan["soundtrack"] is not None:
        track = obj(plan["soundtrack"], ("path", "sha256"))
        data = asset(root, track["path"], track["sha256"], MAX_WAV)
        audio = parse_wav(data)
        if audio.frames * fps != count * audio.rate:
            raise ContractError("Durasi soundtrack harus sama persis dengan timeline frame.")
    with TemporaryDirectory(prefix="ace-media-frames-") as temporary:
        payload, report = encode_frames(Path(temporary), _frames(prepared, width, height), width, height, fps, data)
    return payload, {"schema": "ace.media.video-receipt.v1", "plan_sha256": expected,
                     "scene_timeline": [item[-1] for item in prepared],
                     "soundtrack_wav_sha256": sha256(data).hexdigest() if data is not None else None, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, receipt = compose(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
