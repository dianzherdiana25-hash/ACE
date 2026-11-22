from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from ._raster import Raster, png, raster
from .character_keeper import portrait, verify


def bible():
    return {"schema": "ace.media.character-bible.v1", "id": "aria", "source_ref": "fixture:original-sketch",
            "palette": {"background": "#402070", "body": "#E4A678", "hair": "#60231F", "eyes": "#202033",
                        "mark": "#D02836", "shirt": "#357030"},
            "mark_side": "right", "face_width": 22, "hair_height": 10}


class CharacterTests(unittest.TestCase):
    def test_original_character_matches_landmarks_across_poses(self):
        plan = bible()
        anchor = identity(plan)
        frames = []
        for pose in ("front", "lean_left", "lean_right", "smile"):
            raw, report = portrait(plan, anchor, pose)
            self.assertEqual(report["actor"], "aria")
            self.assertEqual(report["image_sha256"], sha256(raw).hexdigest())
            frames.append((pose, raw))
        audit = verify(plan, anchor, frames)
        self.assertEqual((audit["passed_landmarks"], audit["landmarks"], audit["score_bp"]), (20, 20, 10000))
        self.assertEqual(len({raw for _, raw in frames}), 4)

    def test_tampered_mark_is_located_and_bad_bible_rejected(self):
        plan = bible()
        raw, report = portrait(plan, identity(plan), "front")
        frame = raster(raw)
        data = bytearray(frame.pixels)
        x, y = report["landmarks"]["mark"]["point"]
        start = (y * frame.width + x) * 3
        data[start:start + 3] = b"\x01\x02\x03"
        actual = png(Raster(frame.width, frame.height, bytes(data)))
        result = verify(plan, identity(plan), [("front", actual)])
        self.assertEqual(8000, result["score_bp"])
        self.assertEqual(["mark"], [rule["feature"] for rule in result["variants"][0]["checks"] if not rule["pass"]])
        with self.assertRaisesRegex(ContractError, "ganda"):
            verify(plan, identity(plan), [("front", raw), ("front", raw)])
