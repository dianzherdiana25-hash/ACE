"""Akses rangkaian RGB dan audio dari aset MP4 lokal untuk penyuntingan."""
from pathlib import Path
from tempfile import TemporaryDirectory

from ._assets import asset
from ._audio import Audio, align, wav
from ._contracts import ContractError, obj
from ._video import MAX_MOVIE, load_movie


def open_clip(root, reference):
    obj(reference, ("path", "sha256"))
    payload = asset(root, reference["path"], reference["sha256"], MAX_MOVIE)
    with TemporaryDirectory(prefix="ace-media-clip-") as temporary:
        return load_movie(Path(temporary), payload)


def cut_audio(audio, fps, ranges):
    if audio is None:
        return None
    pcm = align(audio, 24000, 1)
    if pcm.rate % fps:
        raise ContractError("Laju frame tidak dapat dipotong presisi pada PCM 24 kHz.")
    stride = pcm.rate // fps
    return wav(Audio(pcm.rate, 1, tuple(sample for start, end in ranges
                                        for sample in pcm.samples[start * stride:end * stride])))
