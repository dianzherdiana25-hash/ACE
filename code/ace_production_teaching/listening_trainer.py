"""Buat latihan dengar dari segmen PCM berizin dan pisahkan kunci jawaban dari paket latihan."""
import argparse
from io import BytesIO
from pathlib import Path
from random import Random
import sys
import wave

from ._artifacts import evidence
from ._contracts import (ProductionError, anchor, canonical, decode, identifier, identity,
                         integer, items, obj, read, schema, source_bytes, text)


def prepare_listening(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.listening-plan.v1", ("audio", "permission_ref", "seed", "clips"))
    ref = obj(plan["audio"], ("path", "sha256"))
    source = source_bytes(root, ref["path"], ref["sha256"], 16_000_000)
    rights = text(plan["permission_ref"], "Izin rekaman")
    generator = Random(integer(plan["seed"], "Seed", 0, 2**63 - 1))
    assets = {}
    cards = []
    keys = []
    seen = set()
    try:
        with wave.open(BytesIO(source), "rb") as recording:
            rate, channels, frames = recording.getframerate(), recording.getnchannels(), recording.getnframes()
            if recording.getsampwidth() != 2 or recording.getcomptype() != "NONE" or channels not in (1, 2) or not 8000 <= rate <= 48000:
                raise ProductionError("Sumber perlu WAV PCM16, mono atau stereo.")
            for item in items(plan["clips"], 50, 1):
                obj(item, ("id", "from_ms", "through_ms", "question", "options", "answer", "transcript_ref"))
                key = identifier(item["id"], "Latihan dengar")
                if key in seen:
                    raise ProductionError("Latihan dengar ber-ID ganda.")
                seen.add(key)
                start = integer(item["from_ms"], "Awal klip", 0, frames * 1000 // rate - 1)
                end = integer(item["through_ms"], "Akhir klip", start + 1, min(start + 16000, frames * 1000 // rate))
                skip = start * rate // 1000
                span = end * rate // 1000 - skip
                recording.setpos(skip)
                payload = recording.readframes(span)
                if len(payload) != span * channels * 2 or not any(payload):
                    raise ProductionError("Isi segmen audio terpotong atau nihil.")
                with BytesIO() as destination:
                    with wave.open(destination, "wb") as stream:
                        stream.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
                        stream.writeframes(payload)
                    raw = destination.getvalue()
                options = [text(value, "Opsi latihan", 100) for value in items(item["options"], 8, 2)]
                answer = text(item["answer"], "Jawaban", 100)
                if len(set(options)) != len(options) or answer not in options:
                    raise ProductionError("Opsi ganda atau jawaban tidak terdapat pada pilihan.")
                generator.shuffle(options)
                path = key + ".wav"
                assets[path] = raw
                card = {"id": key, "path": path, "first_sample": skip, "frames": span,
                        "question": text(item["question"], "Pertanyaan dengar", 350), "options": options}
                cards.append(card)
                keys.append({"id": key, "option_index": options.index(answer), "card_sha256": identity(card),
                             "transcript_ref": text(item["transcript_ref"], "Pointer transkrip")})
    except (wave.Error, EOFError) as error:
        raise ProductionError("Sumber WAV tidak dapat dibaca.") from error
    proof = {"schema": "ace.teaching.listening-receipt.v1", "plan_sha256": expected, "source": ref,
             "permission_ref": rights, "cards": cards, "answer_key_sha256": identity(keys), "output": evidence(assets)}
    return assets, keys, proof


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--answer-key", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, keys, report = prepare_listening(decode(read(args.plan)), args.expect_sha256, args.root)
        if args.answer_key.resolve().is_relative_to(args.output.resolve()):
            raise ProductionError("Simpan kunci jawaban di luar direktori latihan.")
        args.output.mkdir()
        with args.answer_key.open("xb") as stream:
            stream.write(canonical(keys) + b"\n")
        for name, payload in data.items():
            (args.output / name).write_bytes(payload)
        (args.output / "questions.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
