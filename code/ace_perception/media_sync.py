"""Sinkronkan kata transkrip dengan frame yang waktunya terverifikasi.

Dua titik mengikat offset dan drift linear. Sisa titik memeriksa
kesesuaian. Cap waktu di luar rentang terkalibrasi menahan
pencocokan. Setiap frame dan receipt melalui cek hash sebelum
diberi pasangan waktu dari sumber yang sama.
"""
import argparse
from bisect import bisect_left
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys

from . import _audio, _perception_io, _raster, _vision, audio_pipeline
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .ocr_engine import _pairs
from .perceptual_memory import _digest


MAX_TIME = 10**12
MAX_FRAMES = 256


def _anchors(raw, maximum_residual, maximum_drift):
    if not isinstance(raw, list) or not 2 <= len(raw) <= 32:
        raise ValueError("Sinkronisasi perlu sedikitnya dua anchor waktu.")
    knots = []
    marks = set()
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"audio_us", "visual_us", "ref"}:
            raise ValueError("Bentuk anchor media tidak sah.")
        a = _integer(row["audio_us"], 0, MAX_TIME, "Waktu audio")
        b = _integer(row["visual_us"], 0, MAX_TIME, "Waktu visual")
        ref = _token(row["ref"], "Rujukan anchor")
        if ref in marks:
            raise ValueError("Rujukan anchor ganda.")
        knots.append((a, b, ref))
        marks.add(ref)
    knots.sort()
    if any(a[0] >= b[0] or a[1] >= b[1] for a, b in zip(knots, knots[1:])):
        raise ValueError("Anchor waktu perlu meningkat pada kedua sumber.")
    low, high = knots[0], knots[-1]
    ratio = Fraction(high[1]-low[1], high[0]-low[0])
    if abs(ratio-1)*1_000_000 > maximum_drift or any(
            abs(low[1]+(a-low[0])*ratio-b) > maximum_residual for a,b,_ in knots):
        raise ValueError("Drift atau residual anchor melewati batas.")
    return low, high, ratio, knots


def _frames(root, manifest, expect):
    if not isinstance(manifest, bytes) or len(manifest) > _vision.MAX_SPEC_BYTES or sha256(manifest).hexdigest() != _digest(expect):
        raise ValueError("Manifest frame berbeda dari anchor.")
    parsed = json.loads(manifest.decode("utf-8"), object_pairs_hook=_pairs)
    if not isinstance(parsed, dict) or parsed.get("schema") != "ace.perception-video-keyframes.v1":
        raise ValueError("Manifest membutuhkan hasil video_frame_sampler.")
    raw = parsed.get("frames")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_FRAMES:
        raise ValueError("Jumlah frame sinkronisasi di luar batas.")
    frames = []
    filenames = set()
    times = set()
    for row in raw:
        if not isinstance(row, dict) or not {"time_us", "file", "sha256", "bytes"} <= row.keys():
            raise ValueError("Bentuk penunjuk frame tidak sah.")
        filename = row["file"]
        if len(_perception_io.relative_parts(filename)) != 1 or filename in filenames:
            raise ValueError("Nama frame harus unik dan langsung di dalam direktori.")
        size = _integer(row["bytes"], 1, 800_000, "Byte frame")
        key = _digest(row["sha256"])
        content = _perception_io.read_relative(root, filename, size, key)
        if len(content) != size:
            raise ValueError("Ukuran frame berubah.")
        _raster.decode(content)
        stamp = _integer(row["time_us"], 0, MAX_TIME, "Waktu frame")
        if stamp in times:
            raise ValueError("Cap waktu frame ganda.")
        times.add(stamp)
        filenames.add(filename)
        frames.append((stamp, filename, key))
    return sorted(frames)


def sync(wav, transcript, root, manifest, policy, **parameters):
    names = ("manifest_sha256", "anchors", "maximum_residual_us", "maximum_drift_ppm", "maximum_frame_gap_us")
    raw = _vision.spec(policy, "ace.perception-media-sync.v1", names)
    max_residual = _integer(raw["maximum_residual_us"], 0, 5_000_000, "Residual")
    max_drift = _integer(raw["maximum_drift_ppm"], 0, 200_000, "Drift")
    max_gap = _integer(raw["maximum_frame_gap_us"], 1, 120_000_000, "Jarak frame")
    low, high, velocity, knots = _anchors(raw["anchors"], max_residual, max_drift)
    frames = _frames(root, manifest, raw["manifest_sha256"])
    times = [item[0] for item in frames]
    answer = audio_pipeline.align(wav, transcript, **parameters)
    bound = []
    for row in answer["segments"]:
        for item in row["words"]:
            center = Fraction(item["start_us"]+item["end_us"], 2)
            found, projected = None, None
            status = "outside_anchors"
            if low[0] <= center <= high[0]:
                projected = low[1]+(center-low[0])*velocity
                index = bisect_left(times, projected)
                candidates = frames[max(0,index-1):min(len(frames),index+1)]
                best = min(candidates, key=lambda value: (abs(value[0]-projected), value[0]))
                status = "frame_gap"
                if abs(best[0]-projected) <= max_gap:
                    status = "paired"
                    found = {"time_us": best[0], "file": best[1], "sha256": best[2]}
            bound.append({"segment": row["id"], "word": item["word"], "start_us": item["start_us"], "end_us": item["end_us"],
                          "receipt_ref": row["receipt_ref"], "status": status,
                          "visual_us_rounded": round(projected) if projected is not None else None, "frame": found})
    return {"schema": "ace.perception-media-sync-result.v1", "audio_sha256": answer["audio_sha256"],
            "transcript_sha256": answer["receipt_sha256"], "transcript_status": answer["status"],
            "manifest_sha256": raw["manifest_sha256"], "policy_sha256": sha256(policy).hexdigest(),
            "anchors": [{"audio_us": a, "visual_us": b, "ref": ref} for a,b,ref in knots],
            "scale": {"numerator": velocity.numerator, "denominator": velocity.denominator}, "words": bound}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("wav", "transcript", "frames", "manifest", "policy"):
        parser.add_argument(arg, type=Path)
    parser.add_argument("--silence-ms", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        result = sync(_raster.read(args.wav, _audio.MAX_BYTES),
                      _raster.read(args.transcript, audio_pipeline.MAX_RECEIPT_BYTES), args.frames,
                      _raster.read(args.manifest, _vision.MAX_SPEC_BYTES), _raster.read(args.policy, _vision.MAX_SPEC_BYTES),
                      silence_ms=args.silence_ms)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["transcript_status"] == "incomplete" or any(row["status"] != "paired" for row in result["words"]))


if __name__ == "__main__":
    raise SystemExit(main())
