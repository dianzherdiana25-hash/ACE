"""Susun dialog, jeda dan bed musik pada satu garis waktu yang bisa diaudit."""
import argparse
from array import array
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._audio import Audio, MAX_WAV, align, clamp, parse_wav, sample_rate, wav
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema)


ROLES = ("speech", "bed", "effect")
MIX_FIELDS = ("rate", "channels", "duration_ms", "headroom", "duck_threshold",
              "duck_milli", "attack_ms", "release_ms")
TRACK_FIELDS = ("id", "role", "start_ms", "gain_milli", "fade_in_ms", "fade_out_ms", "pan")


def _ramp(frame, length, fade_in, fade_out):
    rising = (frame + 1) * 1000 // max(1, fade_in) if fade_in else 1000
    falling = (length - frame) * 1000 // max(1, fade_out) if fade_out else 1000
    return min(rising, falling, 1000)


def _pan(channels, pan):
    if channels == 1:
        if pan:
            raise ContractError("Pan hanya dapat digunakan pada stereo.")
        return (1000,)
    return (1000 - max(0, pan), 1000 + min(0, pan))


def mix_tracks(settings, tracks):
    """Campur track PCM dan kembalikan audio plus pengukuran atas sampel."""
    obj(settings, MIX_FIELDS)
    rate = sample_rate(settings["rate"])
    channels = integer(settings["channels"], "Kanal", 1, 2)
    duration = integer(settings["duration_ms"], "Durasi", 1, 60_000)
    headroom = integer(settings["headroom"], "Headroom", 1, 32767)
    threshold = integer(settings["duck_threshold"], "Ambang dialog", 1, 32767)
    attenuation = integer(settings["duck_milli"], "Gain saat duck", 0, 1000)
    attack = integer(settings["attack_ms"], "Attack", 0, 1000) * rate // 1000
    release = integer(settings["release_ms"], "Release", 0, 5000) * rate // 1000
    frames = duration * rate // 1000
    if len(tracks) > 40 or frames * channels > 4_000_000:
        raise ContractError("Anggaran sampel atau jumlah track terlampaui.")
    buses = {role: array("i", [0]) * (frames * channels) for role in ROLES}
    report = []
    seen = set()
    for track, audio in tracks:
        obj(track, TRACK_FIELDS)
        track_id = identifier(track["id"], "Track")
        role = track["role"]
        if role not in ROLES or track_id in seen:
            raise ContractError("Peran atau ID track tidak sah.")
        seen.add(track_id)
        start = integer(track["start_ms"], "Waktu masuk", 0, duration) * rate // 1000
        gain = integer(track["gain_milli"], "Gain", 0, 2000)
        fade_in = integer(track["fade_in_ms"], "Fade in", 0, duration) * rate // 1000
        fade_out = integer(track["fade_out_ms"], "Fade out", 0, duration) * rate // 1000
        left_right = _pan(channels, integer(track["pan"], "Pan", -1000, 1000))
        clip = align(audio, rate, channels)
        if not clip.frames or start + clip.frames > frames or fade_in + fade_out > clip.frames:
            raise ContractError("Track atau fade melampaui rentang yang direncanakan.")
        bus = buses[role]
        for index, value in enumerate(clip.samples):
            frame, channel = divmod(index, channels)
            envelope = _ramp(frame, clip.frames, fade_in, fade_out)
            bus[start * channels + index] += value * gain * envelope * left_right[channel] // 10**9
        report.append({"id": track_id, "role": role, "start_frame": start,
                       "end_frame_exclusive": start + clip.frames, **clip.receipt()})
    attack = max(1, attack)
    release = max(1, release)
    attack_step = (1000 - attenuation + attack - 1) // attack
    release_step = (1000 - attenuation + release - 1) // release
    duck_gain = 1000
    ducked = 0
    speech_hold = 0
    mixed = array("i")
    for frame in range(frames):
        start = frame * channels
        if max(abs(buses["speech"][start + channel]) for channel in range(channels)) >= threshold:
            speech_hold = max(1, rate // 50)
        high = speech_hold > 0
        speech_hold = max(0, speech_hold - 1)
        if high:
            duck_gain = max(attenuation, duck_gain - attack_step)
        else:
            duck_gain = min(1000, duck_gain + release_step)
        ducked += duck_gain != 1000
        for channel in range(channels):
            index = start + channel
            mixed.append(buses["speech"][index] + buses["effect"][index]
                         + buses["bed"][index] * duck_gain // 1000)
    input_peak = max(map(abs, mixed), default=0)
    denominator = max(headroom, input_peak)
    output = Audio(rate, channels, tuple(clamp(value * headroom // denominator) for value in mixed))
    return output, {"tracks": report, "pre_normalize_peak": input_peak,
                    "normalization": [headroom, denominator], "ducked_frames": ducked,
                    **output.receipt()}


def mix(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.mix-plan.v1", ("settings", "tracks"))
    tracks = []
    source_hashes = {}
    for item in entries(plan["tracks"], 40, 1):
        obj(item, (*TRACK_FIELDS, "path", "sha256"))
        audio = parse_wav(asset(root, item["path"], item["sha256"], MAX_WAV))
        tracks.append(({field: item[field] for field in TRACK_FIELDS}, audio))
        source_hashes[item["id"]] = item["sha256"]
    output, report = mix_tracks(plan["settings"], tracks)
    data = wav(output)
    return data, {"schema": "ace.media.mix-receipt.v1", "plan_sha256": expected,
                  "wav_sha256": sha256(data).hexdigest(), "source_sha256": source_hashes, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        audio, report = mix(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(audio)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
