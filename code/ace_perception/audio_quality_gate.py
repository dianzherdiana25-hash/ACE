"""Ukur kelayakan audio sebelum jalur persepsi yang lebih mahal.

Clip, bias DC, fraksi jendela hening, dan rasio energi profil
noise diukur dari PCM mono hasil decode. Ambang datang dari
pemanggil. Rasio terhadap noise nol tetap tidak terdefinisi
dengan alasan yang bisa dibaca oleh gerbang.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from math import isqrt
from pathlib import Path
import sys

from . import _audio, _raster, _vision
from .audio_pipeline import _canonical, _integer, _span


def _ratio(a, b):
    if not b:
        return None
    value = Fraction(a, b)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _energy(values):
    return sum(sample*sample for sample in values)


def assess(data, policy):
    audio = _audio.decode(data)
    raw = _vision.spec(policy, "ace.perception-audio-quality.v1",
                       ("minimum_duration_ms", "minimum_rms", "clipping_abs", "maximum_clip_bp", "maximum_dc_abs",
                        "quiet_rms", "maximum_quiet_window_bp", "frame_ms", "noise_box_ms", "minimum_signal_noise_ratio"))
    rate = audio.sample_rate
    count = audio.sample_count
    rms_min = _integer(raw["minimum_rms"], 0, 32768, "RMS minimum")
    min_ms = _integer(raw["minimum_duration_ms"], 1, 600_000, "Durasi minimum")
    clip = _integer(raw["clipping_abs"], 1, 32768, "Amplitudo clip")
    clip_limit = _integer(raw["maximum_clip_bp"], 0, 10_000, "Clip maksimum")
    dc_limit = _integer(raw["maximum_dc_abs"], 0, 32768, "Bias DC maksimum")
    silence = _integer(raw["quiet_rms"], 0, 32768, "Ambang hening")
    quiet_limit = _integer(raw["maximum_quiet_window_bp"], 0, 10_000, "Hening maksimum")
    frame = _integer(raw["frame_ms"], 5, 500, "Jendela RMS")*rate//1000
    required_snr = _integer(raw["minimum_signal_noise_ratio"], 1, 10_000, "Rasio signal/noise minimum")

    pcm = audio.mono
    signal_energy = _energy(pcm)
    rms = isqrt(signal_energy//count)
    clipped = sum(abs(sample) >= clip for sample in pcm)
    quiet = 0
    frames = 0
    for start in range(0, count, frame):
        samples = pcm[start:start+frame]
        quiet += _energy(samples) <= silence*silence*len(samples)
        frames += 1
    dc = sum(pcm)
    blockers = []
    for problem, bad in (
        ("too_short", count*1000 < min_ms*rate), ("low_rms", rms < rms_min),
        ("excess_clipping", clipped*10_000 > clip_limit*count),
        ("excess_dc", abs(dc) > dc_limit*count),
        ("excess_quiet", quiet*10_000 > quiet_limit*frames),
    ):
        if bad:
            blockers.append(problem)
    pointer = raw["noise_box_ms"]
    snr = None
    if pointer is None:
        snr_status = "noise_reference_missing"
    elif isinstance(pointer, list) and len(pointer) == 2:
        duration = count*1000//rate
        a = _integer(pointer[0], 0, duration, "Awal profil noise")*rate//1000
        b = _integer(pointer[1], pointer[0]+1, duration, "Akhir profil noise")*rate//1000
        noise_energy = _energy(pcm[a:b])
        use = count-b+a
        if not use:
            snr_status = "signal_reference_empty"
        elif not noise_energy:
            snr_status = "noise_energy_zero"
        else:
            n = (signal_energy-noise_energy)*(b-a)
            d = noise_energy*use
            snr = _ratio(n, d)
            snr_status = "measured"
            if n < required_snr*d:
                blockers.append("signal_noise_ratio_low")
        pointer = _span(a, b, rate)
    else:
        raise ValueError("Profil noise perlu dua titik milidetik.")
    state = "held" if blockers else "incomplete" if snr is None else "pass"
    return {"schema": "ace.perception-audio-quality-report.v1", "source_sha256": sha256(data).hexdigest(),
            "policy_sha256": sha256(policy).hexdigest(), "view": "decoded_mono", "input_channels": audio.channels,
            "sample_rate": rate, "sample_count": count, "status": state, "blockers": blockers,
            "rms": rms, "clip_count": clipped, "clip_fraction": _ratio(clipped, count),
            "dc_mean": _ratio(dc, count), "quiet_windows": quiet, "windows": frames,
            "noise_span": pointer, "snr_status": snr_status, "signal_noise_energy_ratio": snr}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("policy", type=Path)
    args = parser.parse_args(argv)
    try:
        result = assess(_raster.read(args.wav, _audio.MAX_BYTES), _raster.read(args.policy, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
