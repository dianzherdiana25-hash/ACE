"""Rakit kanal suara lokal dua arah dari rekaman PCM yang bertambat ke turn dialog."""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import wave

from ._contracts import (
    PresenceError, anchor, canonical, decode, identifier, integer, items, obj, read, schema, source_bytes, text,
)
from ._journal import load_export


def _wav(raw):
    try:
        with wave.open(BytesIO(raw), "rb") as channel:
            rate = channel.getframerate()
            frames = channel.getnframes()
            if channel.getnchannels() != 1 or channel.getsampwidth() != 2 or not 8000 <= rate <= 48000:
                raise PresenceError("Kanal suara perlu WAV PCM16 mono dan sample rate 8–48 kHz.")
            if not 0 < frames <= rate * 30:
                raise PresenceError("Setiap segmen suara perlu lebih dari nol dan maksimal 30 detik.")
            data = channel.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise PresenceError("Segmen WAV tidak dapat dibaca.") from error
    if len(data) != frames * 2 or not any(data):
        raise PresenceError("Segmen kosong, hening atau tidak lengkap.")
    return rate, frames, data


def render_voice_exchange(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.duplex-plan.v1", ("dialogue", "clips", "pause_ms", "max_duration_ms"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    chain = load_export(source_bytes(root, ref["path"], ref["sha256"], 2_000_000))
    pauses = integer(plan["pause_ms"], "Jeda pergantian giliran", 0, 1000)
    cap = integer(plan["max_duration_ms"], "Durasi maksimum", 1000, 120000)
    input_ = {}
    for clip in items(plan["clips"], 160, 2):
        obj(clip, ("id", "turn_sha256", "path", "sha256", "permission_ref"))
        key = identifier(clip["id"], "Turn suara")
        if key in input_:
            raise PresenceError("Setiap turn suara punya satu klip.")
        input_[key] = clip
    observed = {item["turn"]["id"] for item in chain["events"]}
    if input_.keys() != observed:
        raise PresenceError("Klip suara harus mencakup turn yang sama dengan jurnal.")
    rate = None
    channels = bytearray()
    offset = 0
    timeline = []
    for item in chain["events"]:
        row = item["turn"]
        key = row["id"]
        indexed = input_[key]
        grant = text(indexed["permission_ref"], "Izin klip suara")
        if item["sha256"] != indexed["turn_sha256"]:
            raise PresenceError("Audio tidak tertambat pada hash turn yang ditunjuk.")
        content = source_bytes(root, indexed["path"], indexed["sha256"], 3_000_000)
        source_rate, span, sound = _wav(content)
        if rate is None:
            rate = source_rate
        if rate != source_rate:
            raise PresenceError("Semua klip harus memakai sample rate sama.")
        silent = rate * pauses // 1000 if timeline else 0
        if (offset + silent + span) * 1000 > cap * rate:
            raise PresenceError("Timeline audio melampaui anggaran.")
        channels.extend(b"\0\0\0\0" * silent)
        offset += silent
        destination = 0 if row["role"] == "user" else 1
        if destination == 0:
            interleaved = b"".join(sound[index:index + 2] + b"\0\0" for index in range(0, len(sound), 2))
        else:
            interleaved = b"".join(b"\0\0" + sound[index:index + 2] for index in range(0, len(sound), 2))
        channels.extend(interleaved)
        timeline.append({"id": key, "role": row["role"], "channel": destination, "samples": [offset, offset + span],
                         "turn_sha256": indexed["turn_sha256"], "source_audio_sha256": indexed["sha256"], "permission_ref": grant})
        offset += span
    with BytesIO() as output:
        with wave.open(output, "wb") as stream:
            stream.setparams((2, 2, rate, 0, "NONE", "not compressed"))
            stream.writeframes(channels)
        sound = output.getvalue()
    return sound, {"schema": "ace.presence.duplex-recording.v1", "plan_sha256": expected, "session": chain["session"],
                   "dialogue_head_sha256": chain["head_sha256"], "output_sha256": sha256(sound).hexdigest(),
                   "sample_rate": rate, "frames": offset, "timeline": timeline, "mode": "authorized_input_recordings"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    cfg = parser.parse_args(argv)
    try:
        audio, receipt = render_voice_exchange(decode(read(cfg.plan)), cfg.expect_sha256, cfg.root)
        with cfg.output.open("xb") as stream:
            stream.write(audio)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
