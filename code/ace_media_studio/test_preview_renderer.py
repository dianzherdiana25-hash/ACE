from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from ._raster import blank, png, raster
from .preview_renderer import preview
from .test_video_assembler import make_clip


def plan_for(raw, media_type):
    return {"schema": "ace.media.preview-plan.v1", "source_ref": "fixture:media",
            "source_sha256": sha256(raw).hexdigest(), "media_type": media_type,
            "samples": 3, "columns": 2, "tile_width": 60, "tile_height": 32}


class PreviewTests(unittest.TestCase):
    def test_preview_keeps_aspect_and_uses_letterboxed_pixels(self):
        raw = png(blank(60, 60, (25, 50, 175)))
        plan = plan_for(raw, "image")
        sheet, receipt = preview(raw, plan, identity(plan))
        self.assertEqual(receipt["tiles"][0]["tile"], [19, 20, 32, 32])
        self.assertEqual(raster(sheet).at(19, 20), (25, 50, 175))
        self.assertEqual(raster(sheet).at(5, 20), (24, 28, 38))
        self.assertEqual(receipt["preview_png_sha256"], sha256(sheet).hexdigest())

    @unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
    def test_video_frame_selection_includes_endpoints_and_timestamps(self):
        with TemporaryDirectory() as temporary:
            shades = [(30, 15, 60), (35, 70, 30), (50, 80, 140), (120, 40, 50), (195, 120, 35)]
            raw = make_clip(Path(temporary), shades)
            plan = plan_for(raw, "video")
            _, receipt = preview(raw, plan, identity(plan))
            self.assertEqual(receipt["decoded_frames"], 5)
            self.assertEqual([(row["frame"], row["timestamp_ms"]) for row in receipt["tiles"]],
                             [(0, 0), (2, 500), (4, 1000)])
            self.assertEqual(len({row["source_frame_sha256"] for row in receipt["tiles"]}), 3)
