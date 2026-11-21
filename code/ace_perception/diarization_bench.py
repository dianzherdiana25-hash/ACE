"""Hitung error diarization dari interval gold dan receipt yang tertambat.

Satu bijeksi label global memaksimalkan durasi cocok antar pembicara.
Miss, false alarm, dan confusion dihitung terpisah. Interval overlap
di satu lengan ditolak agar benchmark single-speaker tidak
menghilangkan pembicara tumpang tindih secara diam-diam.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer, _sha
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_INTERVALS = 4096
MAX_SPEAKERS = 12


def _intervals(raw, duration, gold):
    if not isinstance(raw, list) or len(raw) > MAX_INTERVALS:
        raise ValueError("Roster diarization di luar batas.")
    rows = []
    for row in raw:
        if not isinstance(row, dict) or not {"start_us", "end_us", "speaker_id"} <= row.keys():
            raise ValueError("Bentuk interval pembicara tidak sah.")
        start = _integer(row["start_us"], 0, duration-1, "Awal segmen")
        end = _integer(row["end_us"], start+1, duration, "Akhir segmen")
        speaker = row["speaker_id"]
        if gold or speaker is not None:
            speaker = _token(speaker, "Label anonim")
        rows.append((start, end, speaker))
    rows.sort(key=lambda value: (value[0], value[1]))
    if any(a[1] > b[0] for a,b in zip(rows, rows[1:])):
        raise ValueError("Interval pembicara tumpang tindih di satu lengan.")
    return rows


def _overlaps(ref, hyp):
    overlap = defaultdict(int)
    first = second = 0
    while first < len(ref) and second < len(hyp):
        a,b,gold = ref[first]
        c,d,pred = hyp[second]
        length = min(b,d)-max(a,c)
        if length > 0 and pred is not None:
            overlap[gold, pred] += length
        if b <= d:
            first += 1
        if d <= b:
            second += 1
    return overlap


def _mapping(known, observed, overlaps):
    @lru_cache(maxsize=None)
    def match(i, occupied):
        if i == len(known):
            return 0, ()
        best_score, suffix = match(i+1, occupied)
        best = best_score, (-1, *suffix)
        for j, token in enumerate(observed):
            weight = overlaps.get((known[i], token), 0)
            if weight and not occupied & (1<<j):
                gain, tail = match(i+1, occupied | (1<<j))
                trial = gain+weight, (j,*tail)
                if trial[0] > best[0] or (trial[0] == best[0] and trial[1] < best[1]):
                    best = trial
        return best
    total, alignment = match(0, 0)
    return total, [{"gold": known[i], "predicted": observed[j], "overlap_us": overlaps[known[i], observed[j]]}
                   for i,j in enumerate(alignment) if j >= 0]


def score(plan, receipt, expected):
    raw = _vision.spec(plan, "ace.perception-diarization-gold.v1", ("audio_sha256", "gold_ref", "duration_us", "segments"))
    if _sha(raw) != _digest(expected):
        raise ValueError("Gold diarization berbeda dari anchor.")
    duration = _integer(raw["duration_us"], 1, 10**12, "Durasi audio")
    checksum = _digest(raw["audio_sha256"])
    ref = _intervals(raw["segments"], duration, True)
    pred = _vision.spec(receipt, "ace.perception-diarization.v1",
                        ("audio_sha256", "sample_rate", "config", "config_sha256", "speakers", "segments", "unattributed"))
    if _digest(pred["audio_sha256"]) != checksum:
        raise ValueError("Hasil diarization merujuk media berbeda.")
    if _sha(pred["config"]) != _digest(pred["config_sha256"]):
        raise ValueError("Konfigurasi receipt diarization berubah.")
    hyp = _intervals(pred["segments"], duration, False)
    actual_labels = sorted({value for _,_,value in ref})
    predicted_labels = sorted({value for _,_,value in hyp if value is not None})
    if max(len(actual_labels), len(predicted_labels)) > MAX_SPEAKERS:
        raise ValueError("Jumlah pembicara melampaui batas alignment.")
    reference_us = sum(b-a for a,b,_ in ref)
    predicted_us = sum(b-a for a,b,value in hyp if value is not None)
    overlaps = _overlaps(ref, hyp)
    shared = sum(overlaps.values())
    correct, alignment = _mapping(actual_labels, predicted_labels, overlaps)
    missing, extra, mistaken = reference_us-shared, predicted_us-shared, shared-correct
    rate = Fraction(missing+extra+mistaken, reference_us) if reference_us else None
    return {"schema": "ace.perception-diarization-score.v1", "gold_sha256": expected,
            "gold_ref": _token(raw["gold_ref"], "Rujukan gold"), "receipt_sha256": sha256(receipt).hexdigest(),
            "audio_sha256": checksum, "speaker_total": len(actual_labels), "predicted_speakers": len(predicted_labels),
            "reference_us": reference_us, "prediction_us": predicted_us, "miss_us": missing,
            "false_alarm_us": extra, "confusion_us": mistaken, "correct_us": correct,
            "der": {"numerator": rate.numerator, "denominator": rate.denominator} if rate is not None else None,
            "alignment": alignment}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = score(_raster.read(args.gold, _vision.MAX_SPEC_BYTES),
                       _raster.read(args.receipt, _vision.MAX_SPEC_BYTES), args.expect_sha256)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
