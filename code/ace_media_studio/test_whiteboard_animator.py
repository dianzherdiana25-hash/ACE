from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from ._video import extract_frame
from .whiteboard_animator import animate_board


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class WhiteboardTests(unittest.TestCase):
    def test_end_of_line_and_second_stroke_visible_only_when_due(self):
        plan = {"schema": "ace.media.whiteboard-plan.v1", "source_ref": "fixture:sketch",
                "width": 64, "height": 48, "fps": 4, "strokes": [
                    {"id": "across", "color": "#000000", "radius": 3, "points": [[8, 10], [54, 10]], "frames": 3},
                    {"id": "down", "color": "#101010", "radius": 3, "points": [[54, 10], [54, 34]], "frames": 3}]}
        raw, report = animate_board(plan, identity(plan))
        self.assertEqual(report["frames"], 6)
        self.assertEqual(report["strokes"][1]["first_frame"], 3)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result.mp4").write_bytes(raw)
            self.assertGreater(min(extract_frame(root, 0).at(54, 10)), 180)
            last = extract_frame(root, 5)
            self.assertLess(max(last.at(54, 10)), 75)
            self.assertLess(max(last.at(54, 34)), 75)
