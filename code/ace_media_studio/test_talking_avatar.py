from shutil import which
import unittest

from ._contracts import ContractError, identity
from .talking_avatar import talk
from .test_character_keeper import bible


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class AvatarTests(unittest.TestCase):
    def test_generated_speech_changes_mouth_shapes_on_its_sample_timeline(self):
        plan = {"schema": "ace.media.avatar-plan.v1", "voice": {
            "schema": "ace.media.voice-plan.v1", "source_ref": "fixture:dialog", "text": "Mami, mau.",
            "language": "id", "rate": 8000, "pitch_hz": 125, "speed_milli": 1000, "peak": 10000, "seed": 11},
            "bible": bible(), "fps": 20}
        _, receipt = talk(plan, identity(plan))
        timeline = receipt["timeline"]
        self.assertEqual(len(timeline), receipt["frames"])
        self.assertEqual(receipt["audio"], "aac")
        self.assertTrue({"open", "wide", "round", "closed", "rest"} <= {row["viseme"] for row in timeline})
        self.assertEqual(len({row["source_frame_sha256"] for row in timeline}), 5)
        self.assertEqual([r["sample"] for r in timeline[:3]], [200, 600, 1000])
        plan["fps"] = 21
        with self.assertRaisesRegex(ContractError, "membagi"):
            talk(plan, identity(plan))
