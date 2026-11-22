"""Satukan klip lokal terikat hash dengan trim bernomor frame dan kebijakan audio eksplisit."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._assets import asset
from ._audio import Audio, wav
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema)
from ._video import MAX_MOVIE, encode_frames, load_movie


def assemble(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.assembly-plan.v1", ("clips", "audio_policy"))
    policy = plan["audio_policy"]
    if policy not in ("mute", "preserve"):
        raise ContractError("Kebijakan audio perlu mute atau preserve.")
    spans = []
    frames = []
    samples = []
    fps = 0
    size = None
    used = set()
    for link in entries(plan["clips"], 20, 1):
        obj(link, ("id", "path", "sha256", "from_frame", "to_frame"))
        key = identifier(link["id"], "Klip")
        if key in used:
            raise ContractError("ID segmen klip ganda.")
        used.add(key)
        raw = asset(root, link["path"], link["sha256"], MAX_MOVIE)
        with TemporaryDirectory(prefix="ace-media-decode-") as temporary:
            source, cadence, audio = load_movie(Path(temporary), raw)
        if size is None:
            size = (source[0].width, source[0].height)
            fps = cadence
        if (source[0].width, source[0].height, cadence) != (*size, fps) or any(axis % 2 for axis in size):
            raise ContractError("Klip wajib memiliki dimensi genap dan frame rate sama.")
        start = integer(link["from_frame"], "Frame awal", 0, len(source) - 1)
        finish = integer(link["to_frame"], "Frame akhir eksklusif", start + 1, len(source))
        offset = len(frames)
        if offset + finish - start > 450 or (offset + finish - start) * size[0] * size[1] > 27_000_000:
            raise ContractError("Anggaran frame gabungan melampaui batas.")
        frames.extend(source[start:finish])
        if policy == "preserve":
            if 24000 % cadence:
                raise ContractError("Frame rate harus membagi sample rate PCM untuk trim presisi.")
            if audio is None:
                raise ContractError("Audio preserve membutuhkan audio pada setiap klip.")
            samples.extend(audio.samples[start * 24000 // fps:finish * 24000 // fps])
        spans.append({"id": key, "source_sha256": link["sha256"], "source_frames": [start, finish],
                      "output_frames": [offset, len(frames)]})
    mixed = wav(Audio(24000, 1, tuple(samples))) if policy == "preserve" else None
    with TemporaryDirectory(prefix="ace-media-assemble-") as temporary:
        payload, report = encode_frames(Path(temporary), frames, *size, fps, mixed)
    return payload, {"schema": "ace.media.assembly-receipt.v1", "plan_sha256": expected, "clips": spans,
                     "audio_policy": policy, "audio_intermediate_pcm_sha256": sha256(mixed).hexdigest() if mixed else None,
                     **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = assemble(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
