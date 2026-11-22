from shutil import which
import unittest

from ._contracts import ContractError, identity
from .loop_maker import make_loop


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class LoopTests(unittest.TestCase):
    def test_loop_keeps_period_without_appending_duplicate_terminal(self):
        plan = {"schema": "ace.media.loop-plan.v1", "source_ref": "fixture:orbit", "width": 64, "height": 48,
                "frames": 12, "fps": 6, "background": "#202035", "accent": "#F06010",
                "diameter": 8, "radius_x": 15, "radius_y": 10}
        raw, report = make_loop(plan, identity(plan))
        self.assertTrue(raw)
        self.assertEqual(report["frames"], 12)
        self.assertEqual(report["virtual_terminal"], report["centers"][0])
        self.assertNotEqual(report["source_frame_sha256"][0], report["source_frame_sha256"][-1])
        self.assertLessEqual(report["seam_jump_squared_px"], report["max_internal_jump_squared_px"])
        plan["radius_y"] = 35
        with self.assertRaisesRegex(ContractError, "Radius Y"):
            make_loop(plan, identity(plan))
