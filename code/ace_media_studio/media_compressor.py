"""Kompresi MP4 lokal dengan target ukuran, dimensi, dan gerbang mutu hasil decode."""
import argparse
from hashlib import sha256
from math import log10
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._audio import wav
from ._contracts import (ContractError, canonical, checked, decode, digest, integer,
                         read, schema, text)
from ._raster import Raster
from ._video import MAX_MOVIE, encode_frames, load_movie


def scale_frame(image, width, height):
    """Downsample RGB nearest at pixel centers for an exact reference."""
    stride = image.width * 3
    x_coordinates = [((2 * x + 1) * image.width // (2 * width)) * 3 for x in range(width)]
    pixels = bytearray()
    for y in range(height):
        row = ((2 * y + 1) * image.height // (2 * height)) * stride
        for x in x_coordinates:
            pixels.extend(image.pixels[row + x:row + x + 3])
    return Raster(width, height, bytes(pixels))


def measure(reference, decoded):
    if len(reference) != len(decoded) or not reference:
        raise ContractError("Urutan hasil encode berbeda dari referensi.")
    span = len(reference) - 1
    indices = sorted({index * span // 7 for index in range(8)})
    measured = []
    for index in indices:
        original, result = reference[index], decoded[index]
        if (original.width, original.height) != (result.width, result.height):
            raise ContractError("Dimensi hasil encode berbeda dari referensi.")
        squared_error = sum((left - right) ** 2 for left, right in zip(original.pixels, result.pixels, strict=True))
        psnr = round(10_000 * log10(255**2 * len(original.pixels) / squared_error)) if squared_error else None
        measured.append({"frame": index, "squared_error": squared_error, "psnr_millidb": psnr})
    return measured


def compress_movie(data, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.compress-plan.v1", ("profile", "source_ref", "video_sha256", "max_width",
                                                "max_height", "max_bytes", "crf", "minimum_psnr_millidb"))
    anchor = digest(plan["video_sha256"])
    source = text(plan["source_ref"], "Pointer video")
    profile = text(plan["profile"], "Nama profil", 80)
    if sha256(data).hexdigest() != anchor:
        raise ContractError("Hash video sumber berbeda.")
    cap_width = integer(plan["max_width"], "Lebar maksimum", 16, 960)
    cap_height = integer(plan["max_height"], "Tinggi maksimum", 16, 960)
    max_bytes = integer(plan["max_bytes"], "Anggaran byte", 256, MAX_MOVIE)
    crf = integer(plan["crf"], "CRF", 10, 40)
    min_psnr = integer(plan["minimum_psnr_millidb"], "PSNR minimum", 0, 60_000)
    with TemporaryDirectory(prefix="ace-media-compress-source-") as temporary:
        frames, fps, audio = load_movie(Path(temporary), data)
    first = frames[0]
    w, h = first.width, first.height
    if cap_width * h <= cap_height * w:
        target_w = min(w, cap_width)
        target_h = h * target_w // w
    else:
        target_h = min(h, cap_height)
        target_w = w * target_h // h
    width, height = target_w & ~1, target_h & ~1
    if width < 16 or height < 16:
        raise ContractError("Rasio aspek akan menghasilkan dimensi di bawah 16 piksel.")
    reference = [scale_frame(frame, width, height) for frame in frames]
    with TemporaryDirectory(prefix="ace-media-compress-output-") as temporary:
        root = Path(temporary)
        payload, result = encode_frames(root, reference, width, height, fps, wav(audio) if audio else None, crf)
        decoded, measured_fps, _ = load_movie(root, payload)
    if measured_fps != fps:
        raise ContractError("Frame rate keluaran berubah.")
    samples = measure(reference, decoded)
    reasons = []
    if len(payload) > max_bytes:
        reasons.append("byte_cap")
    if any(p["psnr_millidb"] is not None and p["psnr_millidb"] < min_psnr for p in samples):
        reasons.append("pixel_error")
    report = {"schema": "ace.media.compress-receipt.v1", "plan_sha256": expected, "source_ref": source,
              "profile": profile, "source_sha256": anchor, "source_bytes": len(data),
              "byte_difference": len(data) - len(payload), "sampled_frames": samples,
              "status": "ready" if not reasons else "hold", "blocking": reasons, **result}
    return payload if not reasons else None, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, receipt = compress_movie(read(args.input, MAX_MOVIE), decode(read(args.plan)), args.expect_sha256)
        if payload is not None:
            with args.output.open("xb") as stream:
                stream.write(payload)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(payload is None)


if __name__ == "__main__":
    raise SystemExit(main())
