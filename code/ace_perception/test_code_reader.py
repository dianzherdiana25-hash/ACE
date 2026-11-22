"""Verifier ZBar lokal dengan EAN13 dan QR sintetis yang independen."""
from hashlib import sha256
import unittest
from unittest.mock import patch

from ace_perception import _vision, code_reader as model


def barcode():
    # EAN13 dengan leading digit 0 memakai pola LLLLLL.
    text = "0123456789012"
    table = ("0001101", "0011001", "0010011", "0111101", "0100011",
             "0110001", "0101111", "0111011", "0110111", "0001011")
    left = "".join(table[int(item)] for item in text[1:7])
    right = "".join(table[int(item)].translate(str.maketrans("01", "10")) for item in text[7:])
    row = "0"*15+"101"+left+"01010"+right+"101"+"0"*15
    pixels = bytes(value for item in row for value in ([0]*3 if item == "1" else [255]*3))
    return _vision.encode(len(pixels), 72, pixels*72), text


def multiply(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a <<= 1
        if a & 256:
            a ^= 0x11D
        b >>= 1
    return result


def qrcode():
    # Version 1-L, byte mode, mask 0 dan 7 codeword ECC.
    message = b"ACE-LOCAL"
    bits = "0100"+f"{len(message):08b}"+"".join(f"{char:08b}" for char in message)+"0000"
    bits += "0"*((-len(bits)) % 8)
    code = [int(bits[i:i+8], 2) for i in range(0, len(bits), 8)]
    code.extend([0xEC, 0x11]*10)
    code = code[:19]
    divisor = [1]
    root = 1
    for _ in range(7):
        target = [*divisor, 0]
        for i, coefficient in enumerate(divisor, 1):
            target[i] ^= multiply(coefficient, root)
        divisor, root = target, multiply(root, 2)
    division = code+[0]*7
    for index in range(len(code)):
        factor = division[index]
        for j, coefficient in enumerate(divisor):
            division[index+j] ^= multiply(factor, coefficient)
    bits = "".join(f"{word:08b}" for word in code+division[-7:])
    size = 21
    cells = [[None]*size for _ in range(size)]
    for cx, cy in ((3, 3), (17, 3), (3, 17)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                if 0 <= cy+dy < size and 0 <= cx+dx < size:
                    cells[cy+dy][cx+dx] = max(abs(dx), abs(dy)) not in (2, 4)
    for pixel in range(8, 13):
        cells[6][pixel] = cells[pixel][6] = pixel%2 == 0
    digit = lambda i: bool((0x77C4 >> i) & 1)
    for i in range(6):
        cells[i][8] = digit(i)
    cells[7][8], cells[8][8], cells[8][7] = digit(6), digit(7), digit(8)
    for i in range(9, 15):
        cells[8][14-i] = digit(i)
    for i in range(8):
        cells[8][size-1-i] = digit(i)
    for i in range(8, 15):
        cells[size-15+i][8] = digit(i)
    cells[size-8][8] = True
    length = 0
    right, upward = size-1, True
    while right >= 1:
        if right == 6:
            right -= 1
        for y in (range(size-1, -1, -1) if upward else range(size)):
            for x in (right, right-1):
                if cells[y][x] is None:
                    cells[y][x] = (bits[length] == "1") ^ ((x+y)%2 == 0)
                    length += 1
        right -= 2
        upward = not upward
    assert length == len(bits)
    width = (4+size+4)*6
    expanded = [255]*(width*24)
    for line in cells:
        expanded.extend(([255]*24+[0 if v else 255 for v in line for _ in range(6)]+[255]*24)*6)
    expanded.extend([255]*(width*24))
    return _vision.encode(width, width, expanded), message.decode()


class CodeReaderTests(unittest.TestCase):
    @unittest.skipUnless(model.find_library("zbar"), "libzbar lokal tidak tersedia")
    def test_actual_decoder_accepts_ean_and_qr_with_points_and_exact_payload(self):
        for function, kind in ((barcode, "EAN13"), (qrcode, "QRCODE")):
            source, expected = function()
            with self.subTest(kind=kind):
                found = model.scan(source, formats=[kind])
                self.assertEqual(found["source_sha256"], sha256(source).hexdigest())
                record, = found["codes"]
                self.assertEqual(record["format"], kind)
                self.assertEqual(record["data"], expected)
                self.assertEqual(record["payload_sha256"], sha256(expected.encode()).hexdigest())
                self.assertGreater(len(record["points"]), 1)
                masked, = model.scan(source, formats=[kind], hash_only=True)["codes"]
                self.assertNotIn("data", masked)
                self.assertEqual(masked["payload_sha256"], record["payload_sha256"])

    @unittest.skipUnless(model.find_library("zbar"), "libzbar lokal tidak tersedia")
    def test_whitelist_does_not_return_unrequested_code_and_blank_is_empty(self):
        source, _ = qrcode()
        self.assertEqual(model.scan(source, formats=("EAN13",))["codes"], [])
        self.assertEqual(model.scan(_vision.encode(32, 32, [255]*1024))["codes"], [])

    def test_bad_settings_and_missing_native_dependency(self):
        source, _ = barcode()
        for args in ({"formats": ["QRCODE", "QRCODE"]}, {"formats": ["UNKNOWN"]}, {"hash_only": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                model.scan(source, **args)
        with patch.object(model, "find_library", return_value=None), self.assertRaisesRegex(ValueError, "lokal diperlukan"):
            model.scan(source)
