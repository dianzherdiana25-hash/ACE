"""Tautkan transkrip tercatat ke waktu WAV memakai roster audio tertambat.

Analisis energi lokal memisahkan rentang yang perlu ditranskrip.
Receipt menyebut byte audio dan hash roster, serta kata dengan rentang
sampel di dalam segmen. Bagian tanpa receipt diberi status missing.
Decoder bahasa tetap berada di pihak pencatat receipt.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from . import _audio, _raster
from .document_extractor import _token
from .ocr_engine import _pairs


MAX_SEGMENTS = 1000
MAX_WORDS = 40_000
MAX_RECEIPT_BYTES = 8_000_000


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} di luar batas integer.")
    return value


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _sha(value):
    return sha256(_canonical(value)).hexdigest()


def _timestamp(value, rate):
    return value*1_000_000//rate


def _span(start, end, rate):
    return {"start_sample": start, "end_sample": end, "start_us": _timestamp(start, rate), "end_us": _timestamp(end, rate)}


def _windows(audio, frame, threshold):
    for start in range(0, audio.sample_count, frame):
        end = min(start+frame, audio.sample_count)
        values = audio.mono[start:end]
        voiced = sum(value*value for value in values) >= threshold*threshold*len(values)
        yield start, end, voiced


def _segments(audio, frame_ms, rms, silence_ms, minimum_ms):
    rate = audio.sample_rate
    frame = max(1, rate*frame_ms//1000)
    minimum = (rate*minimum_ms+999)//1000
    allowed_gap = rate*silence_ms//1000
    result = []
    beginning = end_of_voice = None
    for start, end, active in _windows(audio, frame, rms):
        if not active:
            continue
        if beginning is None or start-end_of_voice > allowed_gap:
            if beginning is not None and end_of_voice-beginning >= minimum:
                result.append(_span(beginning, end_of_voice, rate))
            beginning = start
        end_of_voice = end
        if len(result) > MAX_SEGMENTS:
            raise ValueError("Jumlah segmen audio melebihi batas.")
    if beginning is not None and end_of_voice-beginning >= minimum:
        result.append(_span(beginning, end_of_voice, rate))
    if len(result) > MAX_SEGMENTS:
        raise ValueError("Jumlah segmen audio melebihi batas.")
    return [{"id": f"s{index:04d}", **row} for index, row in enumerate(result, 1)]


def segment(audio_data, *, frame_ms=20, rms=300, silence_ms=100, minimum_ms=40):
    _integer(frame_ms, 5, 500, "frame_ms")
    _integer(rms, 1, 32768, "rms")
    _integer(silence_ms, 0, 5000, "silence_ms")
    _integer(minimum_ms, 1, 10000, "minimum_ms")
    audio = _audio.decode(audio_data)
    policy = {"frame_ms": frame_ms, "rms": rms, "silence_ms": silence_ms, "minimum_ms": minimum_ms}
    regions = _segments(audio, frame_ms, rms, silence_ms, minimum_ms)
    core = {"schema": "ace.perception-audio-roster.v1", "audio_sha256": sha256(audio_data).hexdigest(),
            "sample_rate": audio.sample_rate, "channels": audio.channels, "sample_count": audio.sample_count,
            "policy": policy, "segments": regions}
    return {**core, "roster_sha256": _sha(core)}


def _words(rows, region, sample_rate):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_WORDS:
        raise ValueError("Receipt tertranskrip memerlukan daftar kata.")
    words = []
    previous = region["start_sample"]
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != {"word", "start_sample", "end_sample"}:
            raise ValueError("Bentuk kata transkrip tidak sah.")
        start = _integer(raw["start_sample"], previous, region["end_sample"]-1, "Awal kata")
        end = _integer(raw["end_sample"], start+1, region["end_sample"], "Akhir kata")
        word = _token(raw["word"], "Kata")
        if any(char.isspace() for char in word):
            raise ValueError("Satu entri transkrip perlu tepat satu token.")
        words.append({"word": word, **_span(start, end, sample_rate)})
        previous = end
    return words


def align(audio_data, receipt_data, **policy):
    roster = segment(audio_data, **policy)
    if not isinstance(receipt_data, bytes) or len(receipt_data) > MAX_RECEIPT_BYTES:
        raise ValueError("Ukuran receipt audio melampaui batas.")
    raw = json.loads(receipt_data.decode("utf-8"), object_pairs_hook=_pairs)
    fields = {"schema", "audio_sha256", "roster_sha256", "source_ref", "segments"}
    if not isinstance(raw, dict) or set(raw) != fields or raw["schema"] != "ace.perception-transcript-receipts.v1":
        raise ValueError("Skema receipt transkrip tidak sah.")
    if any(raw[key] != roster[key] for key in ("audio_sha256", "roster_sha256")):
        raise ValueError("Receipt tidak menunjuk audio dan roster yang sama.")
    source = _token(raw["source_ref"], "Rujukan arsip transkrip")
    receipts = raw["segments"]
    expected = {row["id"]: row for row in roster["segments"]}
    if not isinstance(receipts, list) or len(receipts) > len(expected):
        raise ValueError("Jumlah receipt melebihi roster.")
    seen = {}
    refs = {source}
    total = 0
    for row in receipts:
        if not isinstance(row, dict) or set(row) != {"id", "receipt_ref", "status", "words"}:
            raise ValueError("Bentuk receipt segmen tidak sah.")
        key = _token(row["id"], "ID segmen")
        pointer = _token(row["receipt_ref"], "Rujukan receipt")
        if key in seen or key not in expected or pointer in refs or row["status"] not in ("read", "unintelligible"):
            raise ValueError("Receipt di luar roster, ganda, atau status tidak sah.")
        if row["status"] == "read":
            words = _words(row["words"], expected[key], roster["sample_rate"])
        elif row["words"] == []:
            words = []
        else:
            raise ValueError("Segmen tak terbaca tidak boleh menyatakan kata.")
        total += len(words)
        if total > MAX_WORDS:
            raise ValueError("Jumlah kata melampaui batas transkrip.")
        refs.add(pointer)
        seen[key] = {"receipt_ref": pointer, "status": row["status"], "words": words,
                     "text": " ".join(item["word"] for item in words) if words else None}
    rows = [{**item, **seen.get(item["id"], {"status": "missing", "receipt_ref": None,
                                            "words": [], "text": None})} for item in roster["segments"]]
    open_segments = [row["id"] for row in rows if row["status"] != "read"]
    return {"schema": "ace.perception-transcript.v1", "audio_sha256": roster["audio_sha256"],
            "roster_sha256": roster["roster_sha256"], "receipt_sha256": sha256(receipt_data).hexdigest(),
            "source_ref": source, "sample_rate": roster["sample_rate"], "segments": rows, "open_segments": open_segments,
            "status": "incomplete" if open_segments else "complete" if rows else "empty"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--frame-ms", type=int, default=20)
    parser.add_argument("--rms", type=int, default=300)
    parser.add_argument("--silence-ms", type=int, default=100)
    parser.add_argument("--minimum-ms", type=int, default=40)
    args = parser.parse_args(argv)
    params = {"frame_ms": args.frame_ms, "rms": args.rms, "silence_ms": args.silence_ms, "minimum_ms": args.minimum_ms}
    try:
        data = _raster.read(args.wav, _audio.MAX_BYTES)
        result = (align(data, _raster.read(args.receipts, MAX_RECEIPT_BYTES), **params)
                  if args.receipts else segment(data, **params))
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result.get("status") == "incomplete")


if __name__ == "__main__":
    raise SystemExit(main())
