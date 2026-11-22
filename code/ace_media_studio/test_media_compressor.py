from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from ._raster import blank
from .media_compressor import compress_movie, measure
from .test_video_assembler import make_clip


class CompressionTests(unittest.TestCase):
    @unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
    def test_profile_scales_receipt_validates_decoded_frames_and_enforces_caps(self):
        with TemporaryDirectory() as temporary:
            raw = make_clip(Path(temporary), [(24, 55, 62), (65, 111, 166), (100, 125, 180)], width=64, height=48)
            plan = {"schema": "ace.media.compress-plan.v1", "profile": "Local short",
                    "source_ref": "fixture:color-deltas", "video_sha256": sha256(raw).hexdigest(),
                    "max_width": 32, "max_height": 36, "max_bytes": 100_000, "crf": 22,
                    "minimum_psnr_millidb": 25_000}
            payload, report = compress_movie(raw, plan, identity(plan))
            self.assertEqual((report["width"], report["height"], report["frames"]), (32, 24, 3))
            self.assertEqual(report["status"], "ready")
            self.assertEqual(report["mp4_sha256"], sha256(payload).hexdigest())
            self.assertEqual([item["frame"] for item in report["sampled_frames"]], [0, 1, 2])
            self.assertEqual(report["byte_difference"], len(raw) - len(payload))
            plan["max_bytes"] = 256
            plan["minimum_psnr_millidb"] = 60_000
            blocked, report = compress_movie(raw, plan, identity(plan))
            self.assertIsNone(blocked)
            self.assertEqual(report["blocking"], ["byte_cap", "pixel_error"])

    def test_identical_frame_is_explicitly_lossless_and_shape_mismatch_refused(self):
        image = blank(20, 20, (18, 23, 54))
        self.assertEqual(measure([image], [image]), [{"frame": 0, "squared_error": 0, "psnr_millidb": None}])
        with self.assertRaisesRegex(ContractError, "Dimensi"):
            measure([image], [blank(21, 20, (18, 23, 54))])
