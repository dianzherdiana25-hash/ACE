"""Batasi decoder raster lokal agar fixture dan artefak dapat diputar ulang."""
from dataclasses import dataclass
from pathlib import Path


MAX_PIXELS = 4_194_304
MAX_BYTES = 20_000_000
_WHITESPACE = b" \t\r\n\v\f"


@dataclass(frozen=True, slots=True)
class Image:
    width: int
    height: int
    maximum: int
    pixels: tuple[int, ...]

    def rectangle(self, box):
        x0, y0, x1, y1 = box
        if not (0 <= x0 < x1 <= self.width and 0 <= y0 < y1 <= self.height):
            raise ValueError("Wilayah raster di luar gambar.")
        return tuple(self.pixels[y*self.width+x] for y in range(y0, y1) for x in range(x0, x1))


def _token(data, start):
    cursor = start
    end = len(data)
    while cursor < end:
        if data[cursor] in _WHITESPACE:
            cursor += 1
        elif data[cursor] == ord("#"):
            stop = data.find(b"\n", cursor)
            cursor = end if stop < 0 else stop + 1
        else:
            break

    start = cursor
    while cursor < end and data[cursor] not in _WHITESPACE and data[cursor] != ord("#"):
        cursor += 1
        if cursor-start > 12:
            raise ValueError("Token PGM terlalu panjang.")
    return data[start:cursor], cursor


def _number(data, cursor, low, high):
    token, cursor = _token(data, cursor)
    if not token or not token.isdigit():
        raise ValueError("Sampel atau dimensi PGM bukan integer.")
    number = int(token)
    if not low <= number <= high:
        raise ValueError("Sampel atau dimensi PGM di luar batas.")
    return number, cursor


def decode(data):
    """Dekode tepat satu PGM P2/P5 8-bit dengan jumlah sampel eksak."""
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError("Berkas raster terlalu besar atau tidak berupa byte.")
    magic, cursor = _token(data, 0)
    if magic not in (b"P2", b"P5"):
        raise ValueError("Format raster perlu PGM P2 atau P5.")
    width, cursor = _number(data, cursor, 1, MAX_PIXELS)
    height, cursor = _number(data, cursor, 1, MAX_PIXELS)
    maximum, cursor = _number(data, cursor, 1, 255)
    size = width * height
    if size > MAX_PIXELS:
        raise ValueError("Jumlah piksel melebihi batas.")
    if magic == b"P5":
        if cursor >= len(data) or data[cursor] not in _WHITESPACE:
            raise ValueError("Kesempatan membaca raster P5 memerlukan pemisah header.")
        has_crlf = data[cursor:cursor+2] == b"\r\n" and len(data)-cursor == size+2
        separator = 2 if has_crlf else 1
        payload = data[cursor+separator:]
        if len(payload) != size or any(value > maximum for value in payload):
            raise ValueError("Panjang atau nilai raster biner tidak cocok.")
        samples = tuple(payload)
    else:
        parsed = []
        for _ in range(size):
            value, cursor = _number(data, cursor, 0, maximum)
            parsed.append(value)
        trailing, _ = _token(data, cursor)
        if trailing:
            raise ValueError("PGM teks punya sampel tambahan.")
        samples = tuple(parsed)
    return Image(width, height, maximum, samples)


def read(path: Path, maximum=MAX_BYTES):
    with path.open("rb") as stream:
        result = stream.read(maximum+1)
    if len(result) > maximum:
        raise ValueError("Berkas masukan persepsi melebihi batas byte.")
    return result
