from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from .highlight_reel import highlight
from .test_video_assembler import make_clip


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class HighlightsTests(unittest.TestCase):
    def test_high_motion_windows_selected_without_overlap_in_source_order(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            shades = [(10, 10, 12), (250, 250, 250), (15, 15, 15),
                      (20, 20, 20), (20, 20, 20), (100, 150, 245), (20, 20, 20), (20, 20, 20)]
            data = make_clip(root, shades, audio=True)
            (root / "sample.mp4").write_bytes(data)
            plan = {"schema": "ace.media.highlight-plan.v1", "source": {"path": "sample.mp4", "sha256": sha256(data).hexdigest()},
                    "window_frames": 2, "clips": 2, "separation_frames": 1}
            _, report = highlight(plan, identity(plan), root)
            self.assertEqual(report["frames"], 4)
            self.assertEqual(report["audio"], "aac")
            self.assertEqual([r["source_frames"] for r in report["selections"]], [[0, 2], [4, 6]])
            self.assertEqual([r["output_frames"] for r in report["selections"]], [[0, 2], [2, 4]])
            plan["clips"] = 4
            with self.assertRaisesRegex(ContractError, "belum tersedia"):
                highlight(plan, identity(plan), root)
