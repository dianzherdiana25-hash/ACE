from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .still_poster import poster
from .test_video_assembler import make_clip


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class PosterTests(unittest.TestCase):
    def test_poster_uses_selected_frame_and_keeps_footer_distinct(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = make_clip(root, [(220, 40, 10), (18, 205, 30)])
            (root / "scene.mp4").write_bytes(source)
            plan = {"schema": "ace.media.still-poster.v1", "source": {"path": "scene.mp4", "sha256": sha256(source).hexdigest()},
                    "frame": 1, "width": 110, "height": 140, "focus_x_bp": 5000, "focus_y_bp": 5000,
                    "title": "POSTER", "source_ref": "fixture:scene-selection"}
            raw, report = poster(plan, identity(plan), root)
            self.assertEqual(report["timestamp_ms"], 250)
            self.assertEqual(report["poster_sha256"], sha256(raw).hexdigest())
            result = raster(raw)
            self.assertGreater(result.at(10, 10)[1], 180)
            self.assertEqual(result.at(0, 139), (20, 28, 42))
            plan["frame"] = 2
            with self.assertRaisesRegex(ContractError, "Posisi still"):
                poster(plan, identity(plan), root)
