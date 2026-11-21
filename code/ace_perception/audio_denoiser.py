"""Kurangi noise dasar WAV dari interval hening yang ditunjuk pengguna.

Kekuatan noise diukur pada interval sumber. Gate menerapkan gain
bertahap di sekitar lantai tersebut dan interpolasi antarjendela.
Laporan menunjukkan energi sebelum/sesudah dan tidak mengekstrapolasi
kualitas percakapan dari penurunan energi.
"""
import argparse
from array import array
from hashlib import sha256
from io import BytesIO
from math import isqrt
from pathlib import Path
import sys
import wave

from . import _audio, _raster
from .audio_pipeline import _canonical, _integer, _span


UNITY = 10_000


def _energy(samples):
    return sum(value*value for value in samples)


def _pcm16(samples, rate):
    payload = array("h", samples)
    if sys.byteorder != "little":
        payload.byteswap()
    with BytesIO() as buffer:
        with wave.open(buffer, "wb") as result:
            result.setparams((1, 2, rate, 0, "NONE", "PCM"))
            result.writeframes(payload.tobytes())
        return buffer.getvalue()


def _suppress(samples, window, floor, ramp, minimum):
    gains = []
    result = array("h")
    previous = None
    for start in range(0, len(samples), window):
        frame = samples[start:start+window]
        rms = isqrt(_energy(frame)//len(frame))
        position = max(0, min(ramp, rms-floor))
        target = minimum+(UNITY-minimum)*position//ramp
        if previous is None:
            previous = target
        size = len(frame)
        for index, value in enumerate(frame, 1):
            gain = (previous*(size-index)+target*index)//size
            scaled = (abs(value)*gain + UNITY//2)//UNITY
            result.append(-scaled if value < 0 else scaled)
        gains.append(target)
        previous = target
    return result, gains


def denoise(audio_data, *, noise_start_ms, noise_end_ms, frame_ms=25, margin=16,
            transition_width=320, minimum_gain_bp=1500):
    audio = _audio.decode(audio_data)
    milliseconds = (audio.sample_count*1000)//audio.sample_rate
    start_ms = _integer(noise_start_ms, 0, milliseconds, "Awal profil noise")
    end_ms = _integer(noise_end_ms, start_ms+1, milliseconds, "Akhir profil noise")
    width = _integer(frame_ms, 5, 200, "Ukuran jendela")
    quiet_margin = _integer(margin, 0, 16000, "Margin noise")
    ramp = _integer(transition_width, 1, 32768, "Lebar transisi")
    minimum = _integer(minimum_gain_bp, 0, UNITY, "Gain minimum")
    start, end = (time*audio.sample_rate//1000 for time in (start_ms, end_ms))
    window = width*audio.sample_rate//1000
    if end-start < window:
        raise ValueError("Profil noise perlu setidaknya satu jendela penuh.")
    samples = audio.mono
    base = isqrt(_energy(samples[start:end])//(end-start))
    floor = min(32768, base+quiet_margin)
    updated, gains = _suppress(samples, window, floor, ramp, minimum)
    payload = _pcm16(updated, audio.sample_rate)
    return payload, {"schema": "ace.perception-denoise.v1", "source_sha256": sha256(audio_data).hexdigest(),
                     "output_sha256": sha256(payload).hexdigest(), "sample_rate": audio.sample_rate,
                     "input_channels": audio.channels, "output_channels": 1, "sample_count": audio.sample_count,
                     "profile": _span(start, end, audio.sample_rate), "profile_rms": base,
                     "gate_floor_rms": floor, "window_samples": window, "transition_width": ramp, "minimum_gain_bp": minimum,
                     "reduced_windows": sum(item < UNITY for item in gains), "windows": len(gains),
                     "input_sum_squares": _energy(samples), "output_sum_squares": _energy(updated),
                     "profile_output_sum_squares": _energy(updated[start:end])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--noise-start-ms", required=True, type=int)
    parser.add_argument("--noise-end-ms", required=True, type=int)
    parser.add_argument("--frame-ms", type=int, default=25)
    parser.add_argument("--margin", type=int, default=16)
    parser.add_argument("--transition-width", type=int, default=320)
    parser.add_argument("--minimum-gain-bp", type=int, default=1500)
    args = parser.parse_args(argv)
    try:
        result, report = denoise(_raster.read(args.wav, _audio.MAX_BYTES),
                                 noise_start_ms=args.noise_start_ms, noise_end_ms=args.noise_end_ms,
                                 frame_ms=args.frame_ms, margin=args.margin,
                                 transition_width=args.transition_width, minimum_gain_bp=args.minimum_gain_bp)
        with args.output.open("xb") as stream:
            stream.write(result)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
