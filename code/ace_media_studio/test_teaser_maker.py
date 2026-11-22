from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from .teaser_maker import teaser
from .test_video_assembler import make_clip


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class TeaserTests(unittest.TestCase):
    def test_teaser_selects_per_act_caps_ranges_and_appends_end_card(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = make_clip(root, [(val, val + 1, val + 5) for val in range(20, 100, 10)], width=120, height=80)
            (root / "story.mp4").write_bytes(raw)
            plan = {"schema": "ace.media.teaser-plan.v1", "source": {"path": "story.mp4", "sha256": sha256(raw).hexdigest()},
                    "frames_per_act": 2, "acts": [
                        {"id": "intro", "start": 0, "end": 3, "anchor": 0, "source_ref": "fixture:intro"},
                        {"id": "final", "start": 3, "end": 8, "anchor": 7, "source_ref": "fixture:final"}],
                    "end_card": {"title": "LIHAT", "note": "CERITA LENGKAP", "frames": 2, "source_ref": "fixture:title"}}
            _, report = teaser(plan, identity(plan), root)
            self.assertEqual(report["frames"], 6)
            self.assertEqual([r["source_frames"] for r in report["acts"]], [[0, 2], [6, 8]])
            self.assertEqual(report["end_card"]["first_frame"], 4)
            plan["acts"][1]["start"] = 2
            with self.assertRaisesRegex(ContractError, "Frame pertama"):
                teaser(plan, identity(plan), root)
