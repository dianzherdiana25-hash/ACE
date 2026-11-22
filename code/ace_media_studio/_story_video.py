"""Bangun kartu grafik dan enkode frame lokal bagi beberapa format studio."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from ._contracts import ContractError
from ._lettering import break_lines, stamp, width
from ._raster import Raster, blank
from ._video import encode_frames


def box(image, x, y, w, h, rgb):
    if w < 0 or h < 0 or x < 0 or y < 0 or x + w > image.width or y + h > image.height:
        raise ContractError("Batas bentuk kartu tidak sah.")
    pixels = bytearray(image.pixels)
    bar = bytes(rgb) * w
    for row in range(y, y + h):
        start = (row * image.width + x) * 3
        pixels[start:start + len(bar)] = bar
    return Raster(image.width, image.height, bytes(pixels))


def card(w, h, head, body, *, colors, progress=None):
    bg, foreground, emphasis = colors
    result = blank(w, h, bg)
    if progress is not None:
        result = box(result, 0, h - 5, progress, 5, emphasis)
    title = break_lines(head, (w - 12) // 12, 2)
    body = break_lines(body, (w - 12) // 6, 5)
    baseline = 8
    for line in title:
        result, _ = stamp(result, line, (w - width(line, 2)) // 2, baseline, 2, emphasis)
        baseline += 17
    baseline += 7
    if baseline + 9 * len(body) > h - 7:
        raise ContractError("Isi kartu terlalu tinggi untuk kanvas.")
    for line in body:
        result, _ = stamp(result, line, (w - width(line, 1)) // 2, baseline, 1, foreground)
        baseline += 9
    return result


def write_movie(frames, w, h, fps, sound=None):
    with TemporaryDirectory(prefix="ace-media-story-") as temporary:
        return encode_frames(Path(temporary), frames, w, h, fps, sound)


def frame_hash(image):
    return sha256(image.pixels).hexdigest()
