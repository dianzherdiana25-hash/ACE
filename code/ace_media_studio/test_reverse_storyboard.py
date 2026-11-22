from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from ._raster import raster
from .reverse_storyboard import extract_storyboard
from .test_video_assembler import make_clip


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class ReverseBoardTests(unittest.TestCase):
    def test_distinct_shots_recover_timing_and_representative_raster(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = make_clip(root, ((240, 22, 32),) * 2 + ((20, 220, 25),) * 3)
            (root / "story.mp4").write_bytes(raw)
            plan = {"schema": "ace.media.reverse-storyboard.v1",
                    "source": {"path": "story.mp4", "sha256": sha256(raw).hexdigest()},
                    "cut_threshold": 32, "min_shot_frames": 2, "max_shots": 4}
            files, report = extract_storyboard(plan, identity(plan), root)
            self.assertEqual([r["range_frames"] for r in report["shots"]], [[0, 2], [2, 5]])
            self.assertEqual(report["shots"][1]["representative_frame"], 3)
            self.assertEqual(report["shots"][1]["range_ms"], [500, 1250])
            self.assertGreater(raster(files["shot_002.png"]).at(10, 10)[1], 160)
            plan["max_shots"] = 1
            with self.assertRaisesRegex(ContractError, "jumlah shot"):
                extract_storyboard(plan, identity(plan), root)
