from hashlib import sha256
from zlib import decompress
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .sticker_maker import make_stickers
from .test_character_keeper import bible


class StickerTests(unittest.TestCase):
    def test_actual_rgba_transparency_and_white_outline(self):
        plan = {"schema": "ace.media.sticker-plan.v1", "character": bible(),
                "poses": ["lean_left", "smile"], "border": 1}
        files, report = make_stickers(plan, identity(plan))
        self.assertEqual(set(files), {"lean_left.png", "smile.png"})
        for item in report["stickers"]:
            data = files[item["pose"] + ".png"]
            self.assertEqual(data[25], 6)
            self.assertEqual(raster(data).width, 48)
            size = int.from_bytes(data[33:37], "big")
            scanlines = decompress(data[41:41 + size])
            stride = 48 * 4 + 1
            alpha = [scanlines[y * stride + x * 4 + 4] for y in range(48) for x in range(48)]
            self.assertEqual(alpha.count(0), item["transparent_pixels"])
            self.assertGreater(item["border_pixels"], 0)
            self.assertEqual(item["sticker_sha256"], sha256(data).hexdigest())
        plan["poses"].append("smile")
        with self.assertRaisesRegex(ContractError, "ganda"):
            make_stickers(plan, identity(plan))
