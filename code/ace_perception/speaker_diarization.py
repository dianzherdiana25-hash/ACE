"""Kelompokkan segmen suara berurutan dari kemiripan energi spektral.

Jejak memakai bank frekuensi yang dideklarasikan dan diambil pada
awal, tengah, serta akhir segmen. Kode speaker anonim menyatakan
klaster yang stabil pada satu file. Segmen yang tidak cukup
informatif atau punya dua klaster dekat tetap tak teratribusi.
"""
import argparse
from dataclasses import dataclass, field
from hashlib import sha256
from math import cos, tau
from pathlib import Path
import sys

from . import _audio, _raster
from .audio_pipeline import _canonical, _integer, _segments, _sha


MAX_BANDS = 12
MAX_CLUSTERS = 32
MAX_WORK = 15_000_000


def _frequencies(values, rate):
    if not isinstance(values, (tuple, list)) or not 2 <= len(values) <= MAX_BANDS:
        raise ValueError("Bank spektral perlu sedikitnya dua frekuensi.")
    unique = {_integer(value, 30, rate//2-1, "Frekuensi") for value in values}
    if len(unique) != len(values):
        raise ValueError("Bank spektral berisi frekuensi ganda.")
    return sorted(unique)


def _power(samples, coefficient):
    prev = before = 0.0
    for item in samples:
        current = item + coefficient*prev - before
        before, prev = prev, current
    return max(0.0, prev*prev + before*before - coefficient*prev*before)


def _windows(audio, region, rate, window_ms):
    start, end = region["start_sample"], region["end_sample"]
    length = min(end-start, rate*window_ms//1000)
    starts = sorted({start, (start+end-length)//2, end-length})
    return [audio.mono[index:index+length] for index in starts]


def _spectral(windows, coefficients):
    shares = [0.0]*len(coefficients)
    energy = 0
    for samples in windows:
        energy += sum(item*item for item in samples)*len(samples)
        for index, coef in enumerate(coefficients):
            shares[index] += _power(samples, coef)
    measured = sum(shares)
    signal = min(10_000, round(10_000*measured/energy)) if energy else 0
    signature = [round(10_000*band/measured) for band in shares] if measured else [0]*len(shares)
    return signal, signature


@dataclass(slots=True)
class Cluster:
    key: str
    totals: list[int]
    members: list[str] = field(default_factory=list)

    def distance(self, signature):
        count = len(self.members)
        error = sum(abs(total-current*count) for total, current in zip(self.totals, signature, strict=True))
        return error//(2*count)

    def join(self, key, signature):
        self.members.append(key)
        for index, current in enumerate(signature):
            self.totals[index] += current

    def export(self):
        return {"speaker_id": self.key, "segments": self.members,
                "centroid_bp": [value//len(self.members) for value in self.totals]}


def _assign(clusters, key, signature, distance, separation, maximum):
    ranking = sorted((cluster.distance(signature), cluster.key, cluster) for cluster in clusters)
    scored = [{"speaker_id": item[1], "distance_bp": item[0]} for item in ranking[:2]]
    if ranking and ranking[0][0] <= distance:
        if len(ranking) > 1 and ranking[1][0]-ranking[0][0] < separation:
            return None, "ambiguous", scored
        selected = ranking[0][2]
        status = "assigned"
    elif len(clusters) >= maximum:
        return None, "cluster_limit", scored
    else:
        selected = Cluster(f"speaker-{len(clusters)+1}", [0]*len(signature))
        clusters.append(selected)
        status = "new_cluster"
    selected.join(key, signature)
    return selected.key, status, scored


def diarize(audio_data, *, frequencies=(125, 250, 500, 1000), spectral_window_ms=40,
            maximum_speakers=8, distance_bp=1500, separation_bp=350, minimum_signal_bp=1000,
            frame_ms=20, rms=300, silence_ms=100, minimum_ms=40):
    audio = _audio.decode(audio_data)
    bank = _frequencies(frequencies, audio.sample_rate)
    window = _integer(spectral_window_ms, 10, 160, "Jendela spektral")
    maximum = _integer(maximum_speakers, 1, MAX_CLUSTERS, "Jumlah klaster")
    distance = _integer(distance_bp, 0, 10_000, "Jarak maksimum")
    separation = _integer(separation_bp, 1, 10_000, "Jarak untuk memutus seri")
    minimum_signal = _integer(minimum_signal_bp, 1, 10_000, "Ambang bukti spektral")
    _integer(frame_ms, 5, 500, "frame_ms")
    _integer(rms, 1, 32768, "rms")
    _integer(silence_ms, 0, 5000, "silence_ms")
    _integer(minimum_ms, 1, 10000, "minimum_ms")
    regions = _segments(audio, frame_ms, rms, silence_ms, minimum_ms)
    rate = audio.sample_rate
    if len(regions)*3*len(bank)*(window*rate//1000) > MAX_WORK:
        raise ValueError("Analisis spektral melampaui batas kerja.")
    coefficients = [2*cos(tau*freq/rate) for freq in bank]
    clusters = []
    results = []
    for region in regions:
        signal, signature = _spectral(_windows(audio, region, rate, window), coefficients)
        if signal >= minimum_signal:
            speaker, status, scores = _assign(clusters, region["id"], signature, distance, separation, maximum)
        else:
            speaker, status, scores = None, "insufficient_signal", []
        results.append({**region, "speaker_id": speaker, "status": status, "signal_bp": signal,
                        "signature_bp": signature, "nearest": scores})
    config = {"frequencies_hz": bank, "spectral_window_ms": window, "maximum_speakers": maximum,
              "distance_bp": distance, "separation_bp": separation, "minimum_signal_bp": minimum_signal,
              "frame_ms": frame_ms, "rms": rms, "silence_ms": silence_ms, "minimum_ms": minimum_ms}
    return {"schema": "ace.perception-diarization.v1", "audio_sha256": sha256(audio_data).hexdigest(),
            "sample_rate": rate, "config": config, "config_sha256": _sha(config),
            "speakers": [item.export() for item in clusters], "segments": results,
            "unattributed": [row["id"] for row in results if row["speaker_id"] is None]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--frequency", type=int, action="append")
    parser.add_argument("--maximum-speakers", type=int, default=8)
    parser.add_argument("--distance-bp", type=int, default=1500)
    parser.add_argument("--minimum-signal-bp", type=int, default=1000)
    parser.add_argument("--silence-ms", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        result = diarize(_raster.read(args.wav, _audio.MAX_BYTES), frequencies=args.frequency or (125, 250, 500, 1000),
                         maximum_speakers=args.maximum_speakers, distance_bp=args.distance_bp,
                         minimum_signal_bp=args.minimum_signal_bp, silence_ms=args.silence_ms)
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(bool(result["unattributed"]))


if __name__ == "__main__":
    raise SystemExit(main())
