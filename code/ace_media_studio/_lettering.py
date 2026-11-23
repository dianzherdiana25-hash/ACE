"""Huruf bitmap terbatas untuk artefak yang dapat direproduksi lintas mesin."""
from ._contracts import ContractError
from ._raster import Raster

_GLYPHS = """
A 0E 11 11 1F 11 11 11
B 1E 11 11 1E 11 11 1E
C 0F 10 10 10 10 10 0F
D 1E 11 11 11 11 11 1E
E 1F 10 10 1E 10 10 1F
F 1F 10 10 1E 10 10 10
G 0F 10 10 13 11 11 0F
H 11 11 11 1F 11 11 11
I 1F 04 04 04 04 04 1F
J 07 02 02 02 12 12 0C
K 11 12 14 18 14 12 11
L 10 10 10 10 10 10 1F
M 11 1B 15 15 11 11 11
N 11 19 15 13 11 11 11
O 0E 11 11 11 11 11 0E
P 1E 11 11 1E 10 10 10
Q 0E 11 11 11 15 12 0D
R 1E 11 11 1E 14 12 11
S 0F 10 10 0E 01 01 1E
T 1F 04 04 04 04 04 04
U 11 11 11 11 11 11 0E
V 11 11 11 11 11 0A 04
W 11 11 11 15 15 1B 11
X 11 11 0A 04 0A 11 11
Y 11 11 0A 04 04 04 04
Z 1F 01 02 04 08 10 1F
0 0E 11 13 15 19 11 0E
1 04 0C 04 04 04 04 0E
2 0E 11 01 02 04 08 1F
3 1E 01 01 0E 01 01 1E
4 02 06 0A 12 1F 02 02
5 1F 10 10 1E 01 01 1E
6 0E 10 10 1E 11 11 0E
7 1F 01 02 04 08 08 08
8 0E 11 11 0E 11 11 0E
9 0E 11 11 0F 01 01 0E
- 00 00 00 1F 00 00 00
. 00 00 00 00 00 0C 0C
: 00 04 04 00 04 04 00
/ 01 01 02 04 08 10 10
% 11 02 04 08 10 11 00
+ 00 04 04 1F 04 04 00
! 04 04 04 04 04 00 04
? 0E 11 01 02 04 00 04
, 00 00 00 00 0C 04 08
; 00 04 04 00 0C 04 08
' 04 04 08 00 00 00 00
" 0A 0A 0A 00 00 00 00
( 08 10 10 10 10 10 08
) 02 01 01 01 01 01 02
"""
GLYPHS = {key: tuple(int(row, 16) for row in values) for key, *values in
          (line.split() for line in _GLYPHS.strip().splitlines())}
GLYPHS[" "] = (0,) * 7


def width(label, scale):
    return (len(label) * 6 - 1) * scale


def break_lines(label, max_letters, max_lines):
    label = " ".join(label.upper().split())
    if not label or any(character not in GLYPHS for character in label):
        raise ContractError("Judul harus memakai huruf Latin A–Z, digit, spasi atau tanda yang tersedia.")
    lines = []
    for token in label.split():
        if len(token) > max_letters:
            raise ContractError("Kata judul belum muat pada lebar yang tersedia.")
        if not lines or len(lines[-1]) + len(token) + 1 > max_letters:
            lines.append(token)
        else:
            lines[-1] += " " + token
    if len(lines) > max_lines:
        raise ContractError("Judul melampaui jumlah baris.")
    return lines


def stamp(image, label, x, y, scale, ink):
    if x < 0 or y < 0 or x + width(label, scale) > image.width or y + 7 * scale > image.height:
        raise ContractError("Teks melampaui area raster.")
    pixels = bytearray(image.pixels)
    row_stride = image.width * 3
    bar = bytes(ink) * scale
    sampled = None
    for index, glyph in enumerate(label):
        for row, bits in enumerate(GLYPHS[glyph]):
            for column in range(5):
                if bits & (16 >> column):
                    px, py = x + (6 * index + column) * scale, y + row * scale
                    sampled = sampled or [px, py, scale, scale]
                    for line in range(py, py + scale):
                        offset = line * row_stride + 3 * px
                        pixels[offset:offset + len(bar)] = bar
    return Raster(image.width, image.height, bytes(pixels)), sampled
