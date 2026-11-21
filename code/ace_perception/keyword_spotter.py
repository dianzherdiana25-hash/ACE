"""Cari kecocokan kata kunci berbasis contoh WAV tanpa decoder bahasa.

Pengukuran menggeser deret energi spektral ternormalisasi dan
membandingkannya dengan contoh yang ditambatkan. Jendela noise
dan kandidat bertumpuk diperlakukan eksplisit. Hasil adalah
kandidat kecocokan contoh dengan rentang waktu dan jarak.
"""
import argparse
from hashlib import sha256
from math import cos, tau
from pathlib import Path
import sys

from . import _audio, _perception_io, _raster, _vision, speaker_diarization
from .audio_pipeline import _canonical, _integer, _sha, _span
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_TEMPLATES = 20
MAX_SEARCH_WORK = 18_000_000
MAX_TEMPLATE_BYTES = 500_000


def _features(audio, frame, coeffs, rms, *, maximum_frames=100_000):
    rows = []
    for start in range(0, audio.sample_count-frame+1, frame):
        data = audio.mono[start:start+frame]
        energy = sum(value*value for value in data)
        if energy < rms*rms*frame:
            rows.append(None)
        else:
            supported, band = speaker_diarization._spectral([data], coeffs)
            rows.append(band if supported >= 100 else None)
        if len(rows) > maximum_frames:
            raise ValueError("Jumlah jendela fitur melampaui batas.")
    return rows


def _distance(a, b):
    if a is None or b is None:
        return 0 if a is b else 10_000
    return sum(abs(x-y) for x, y in zip(a, b, strict=True))//2


def _matches(stream, sample, cutoff, maximum):
    plausible = []
    for start in range(len(stream)-len(sample)+1):
        difference = 0
        for left, right in zip(stream[start:start+len(sample)], sample, strict=True):
            difference += _distance(left, right)
            if difference > cutoff*len(sample):
                break
        if difference <= cutoff*len(sample):
            plausible.append((difference, start))
    kept = []
    for distance, first in sorted(plausible):
        last = first+len(sample)
        if any(first < other[2] and other[1] < last for other in kept):
            continue
        kept.append((distance, first, last))
        if len(kept) >= maximum:
            break
    return sorted(kept, key=lambda row: row[1]), len(plausible)


def detect(wav, root, plan, expected):
    audio = _audio.decode(wav)
    raw = _vision.spec(plan, "ace.perception-keyword-templates.v1",
                       ("plan_ref", "frame_ms", "frequencies_hz", "minimum_rms", "maximum_distance_bp",
                        "maximum_hits_per_template", "templates"))
    if _sha(raw) != _digest(expected):
        raise ValueError("Rencana kata kunci berbeda dari anchor.")
    rate = audio.sample_rate
    frame = _integer(raw["frame_ms"], 10, 200, "Jendela fitur")*rate//1000
    rms = _integer(raw["minimum_rms"], 1, 32768, "Ambang RMS")
    cutoff = _integer(raw["maximum_distance_bp"], 0, 10_000, "Jarak kata kunci")
    maximum = _integer(raw["maximum_hits_per_template"], 1, 100, "Kandidat maksimum")
    bands = speaker_diarization._frequencies(raw["frequencies_hz"], rate)
    coeffs = [2*cos(tau*f/rate) for f in bands]
    rows = raw["templates"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_TEMPLATES:
        raise ValueError("Daftar contoh kata kunci di luar batas.")
    specs = []
    keys = set()
    search_work = 0
    for item in rows:
        if not isinstance(item, dict) or set(item) != {"id", "path", "label", "bytes", "sha256", "source_ref"}:
            raise ValueError("Bentuk contoh kata kunci tidak sah.")
        key, label, ref = (_token(item[field], field) for field in ("id", "label", "source_ref"))
        if key in keys:
            raise ValueError("ID contoh kata kunci ganda.")
        keys.add(key)
        size = _integer(item["bytes"], 1, MAX_TEMPLATE_BYTES, "Ukuran contoh")
        checksum = _digest(item["sha256"])
        source = _perception_io.read_relative(root, item["path"], size, checksum)
        prototype = _audio.decode(source)
        if len(source) != size or prototype.sample_rate != rate or not frame <= prototype.sample_count <= 3*rate:
            raise ValueError("Rekaman contoh tidak cocok dengan laju atau durasi yang diizinkan.")
        search_work += (audio.sample_count//frame)*(prototype.sample_count//frame)*len(bands)
        if search_work > MAX_SEARCH_WORK:
            raise ValueError("Batas kerja pencarian spektral terlampaui.")
        specs.append((key, label, ref, checksum, prototype))
    stream = _features(audio, frame, coeffs, rms)
    found = []
    for key, label, ref, checksum, prototype in sorted(specs):
        sample = _features(prototype, frame, coeffs, rms)
        if not any(row is not None for row in sample):
            raise ValueError("Contoh kata kunci tidak memiliki cukup energi.")
        choices, total = _matches(stream, sample, cutoff, maximum)
        found.append({"id": key, "label": label, "ref": ref, "template_sha256": checksum,
                      "plausible_windows": total, "hits": [{**_span(start*frame, end*frame, rate),
                          "distance_sum_bp": score, "frames": len(sample)} for score, start, end in choices]})
    return {"schema": "ace.perception-keyword-candidates.v1", "audio_sha256": sha256(wav).hexdigest(),
            "plan_sha256": expected, "plan_ref": _token(raw["plan_ref"], "Rujukan kata kunci"),
            "sample_rate": rate, "frame_samples": frame, "frequencies_hz": bands,
            "unexamined_end_samples": audio.sample_count%frame, "templates": found}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        output = detect(_raster.read(args.wav, _audio.MAX_BYTES), args.root,
                        _raster.read(args.plan, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(output)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
