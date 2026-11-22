"""Ukur pengurangan derau, koreksi bias DC, dan headroom pada WAV hasil restorasi."""
import argparse
from hashlib import sha256
from math import isqrt
from pathlib import Path
import sys

from ._audio import Audio, MAX_WAV, clamp, parse_wav, wav
from ._contracts import (ContractError, canonical, checked, decode, digest, integer,
                         read, schema, text)


def _rms(samples):
    return isqrt(sum(item * item for item in samples) // len(samples))


def _floor(audio, size, percentile):
    windows = sorted(_rms(audio[start:start + size]) for start in range(0, len(audio), size))
    return windows[(len(windows) - 1) * percentile // 100]


def _constant_bias(values, source):
    samples = sorted(source)
    middle = len(samples) // 2
    bias = (samples[middle] + samples[(len(samples) - 1) // 2]) // 2
    return [value - bias for value in values]


def _restore_channel(values, rate, quiet_until, suppression):
    quiet = values[:quiet_until]
    centered = _constant_bias(values, quiet)
    quiet = centered[:quiet_until]
    size = max(1, rate // 100)
    noise = _floor(quiet, size, 75)
    baseline = max(1, noise)
    trace = []
    gains = []
    previous = None
    for start in range(0, len(centered), size):
        span = centered[start:start + size]
        level = _rms(span)
        amount = max(0, min(1000, (level - baseline) * 1000 // (2 * baseline)))
        gain = 1000 - suppression + suppression * amount // 1000
        previous = gain if previous is None else previous
        for offset, value in enumerate(span):
            envelope = previous + (gain - previous) * (offset + 1) // len(span)
            trace.append(value * envelope // 1000)
        previous = gain
        gains.append(gain)
    return trace, {"estimated_noise_rms": noise, "center_removed": values[0] - centered[0],
                   "gated_windows": sum(gain < 1000 for gain in gains),
                   "quiet_input_rms": _rms(quiet)}


def restore(data, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.restore-plan.v1", ("source_ref", "audio_sha256", "noise_sample_ms",
                                               "suppression_milli", "peak_target", "max_gain_milli"))
    source = text(plan["source_ref"], "Pointer rekaman")
    anchor = digest(plan["audio_sha256"])
    if sha256(data).hexdigest() != anchor:
        raise ContractError("Hash WAV sumber berbeda dari rencana.")
    audio = parse_wav(data)
    quiet_until = integer(plan["noise_sample_ms"], "Sampel hening awal", 50, 3000) * audio.rate // 1000
    suppression = integer(plan["suppression_milli"], "Kekuatan reduksi", 0, 1000)
    peak_target = integer(plan["peak_target"], "Puncak target", 100, 32767)
    max_gain = integer(plan["max_gain_milli"], "Batas amplifikasi", 1000, 6000)
    if audio.frames <= quiet_until or audio.frames > audio.rate * 90:
        raise ContractError("Batas sampel hening atau durasi rekaman tidak sah.")
    candidate = []
    statistics = []
    for channel in range(audio.channels):
        track, info = _restore_channel(audio.samples[channel::audio.channels], audio.rate, quiet_until, suppression)
        candidate.append(track)
        statistics.append(info)
    peak = max(max(map(abs, track)) for track in candidate)
    gain = min(max_gain, peak_target * 1000 // peak) if peak else 1000
    final = [[clamp(sample * gain // 1000) for sample in track] for track in candidate]
    for index, track in enumerate(final):
        statistics[index]["quiet_output_rms"] = _rms(track[:quiet_until])
    pcm = Audio(audio.rate, audio.channels, tuple(value for column in zip(*final, strict=True) for value in column))
    output = wav(pcm)
    return output, {"schema": "ace.media.restore-receipt.v1", "plan_sha256": expected, "source_ref": source,
                    "input_wav_sha256": anchor, "output_wav_sha256": sha256(output).hexdigest(),
                    "gain_milli": gain, "noise_reduction": statistics, "before": audio.receipt(), "after": pcm.receipt()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = restore(read(args.audio, MAX_WAV), decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
