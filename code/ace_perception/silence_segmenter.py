"""Temukan jeda yang dapat dipakai untuk memecah audio panjang.

Histeresis dua ambang mempertahankan jeda ketika energi dekat
batas. Durasi minimum mencegah jeda pendek menjadi titik potong.
Laporan berisi interval sampel lengkap, potongan audio
komplementer, dan usulan potong tepat di tengah setiap jeda.
"""
import argparse
from hashlib import sha256
from math import isqrt
from pathlib import Path
import sys

from . import _audio, _raster
from .audio_pipeline import _canonical, _integer, _span


MAX_INTERVALS = 2000


def _rms(samples):
    return isqrt(sum(item*item for item in samples)//len(samples))


def _intervals(samples, window, enter, leave, minimum):
    intervals = []
    start = None
    peak = 0
    for offset in range(0, len(samples), window):
        frame = samples[offset:offset+window]
        strength = _rms(frame)
        if start is None:
            if strength <= enter:
                start, peak = offset, strength
        elif strength >= leave:
            if offset-start >= minimum:
                intervals.append((start, offset, peak))
                if len(intervals) > MAX_INTERVALS:
                    raise ValueError("Jumlah interval hening melampaui batas.")
            start = None
        else:
            peak = max(peak, strength)
    if start is not None and len(samples)-start >= minimum:
        intervals.append((start, len(samples), peak))
    if len(intervals) > MAX_INTERVALS:
        raise ValueError("Jumlah interval hening melampaui batas.")
    return intervals


def split(audio_data, *, frame_ms=20, enter_rms=180, exit_rms=300, minimum_ms=300):
    audio = _audio.decode(audio_data)
    duration = _integer(frame_ms, 5, 500, "Jendela")
    enter = _integer(enter_rms, 0, 32767, "Ambang masuk")
    leave = _integer(exit_rms, enter+1, 32768, "Ambang keluar")
    required = _integer(minimum_ms, 1, 120_000, "Durasi hening")
    rate = audio.sample_rate
    window = duration*rate//1000
    silence = _intervals(audio.mono, window, enter, leave, (required*rate+999)//1000)
    quiet = []
    kept = []
    cuts = []
    previous = 0
    for start, end, peak in silence:
        quiet.append({**_span(start, end, rate), "peak_window_rms": peak})
        if previous < start:
            kept.append(_span(previous, start, rate))
        if start > 0 and end < audio.sample_count:
            position = (start+end)//2
            cuts.append({"sample": position, "time_us": position*1_000_000//rate})
        previous = end
    if previous < audio.sample_count:
        kept.append(_span(previous, audio.sample_count, rate))
    return {"schema": "ace.perception-silence.v1", "source_sha256": sha256(audio_data).hexdigest(),
            "sample_rate": rate, "sample_count": audio.sample_count,
            "measured_silence_samples": sum(end-start for start, end, _ in silence),
            "quiet_intervals": quiet, "remaining_intervals": kept, "suggested_cuts": cuts,
            "policy": {"frame_ms": duration, "enter_rms": enter, "exit_rms": leave, "minimum_ms": required}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--frame-ms", type=int, default=20)
    parser.add_argument("--enter-rms", type=int, default=180)
    parser.add_argument("--exit-rms", type=int, default=300)
    parser.add_argument("--minimum-ms", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        result = split(_raster.read(args.wav, _audio.MAX_BYTES), frame_ms=args.frame_ms, enter_rms=args.enter_rms,
                       exit_rms=args.exit_rms, minimum_ms=args.minimum_ms)
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
