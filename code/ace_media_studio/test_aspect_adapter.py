from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from ._raster import blank
from ._story_video import box, write_movie
from ._video import extract_frame
from .aspect_adapter import adapt_aspect


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class AspectTests(unittest.TestCase):
    def test_portrait_respects_right_focus_and_landscape_keeps_bounds(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pixels = box(blank(64, 32, (210, 60, 30)), 32, 0, 32, 32, (35, 190, 60))
            raw, _ = write_movie([pixels] * 2, 64, 32, 4)
            (root / "source.mp4").write_bytes(raw)
            plan = {"schema": "ace.media.aspect-plan.v1", "source": {"path": "source.mp4", "sha256": sha256(raw).hexdigest()},
                    "outputs": [{"id": "vertical", "width": 24, "height": 32, "focus_x_bp": 10000, "focus_y_bp": 5000},
                                {"id": "horizontal", "width": 64, "height": 32, "focus_x_bp": 0, "focus_y_bp": 5000}]}
            files, report = adapt_aspect(plan, identity(plan), root)
            self.assertEqual([r["source_crop"] for r in report["outputs"]], [[40, 0, 24, 32], [0, 0, 64, 32]])
            (root / "result.mp4").write_bytes(files["vertical"])
            self.assertGreater(extract_frame(root, 0).at(2, 12)[1], 160)
            (root / "result.mp4").write_bytes(files["horizontal"])
            self.assertGreater(extract_frame(root, 0).at(2, 12)[0], 180)
