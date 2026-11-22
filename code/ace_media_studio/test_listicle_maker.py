from shutil import which
import unittest

from ._contracts import ContractError, identity
from .listicle_maker import listicle


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class ListicleTests(unittest.TestCase):
    def test_categories_count_down_order_duration_and_distinct_frames(self):
        plan = {"schema": "ace.media.listicle-plan.v1", "style": "countdown", "width": 144, "height": 80, "fps": 2,
                "entries": [{"id": "window", "rank": 1, "title": "JENDELA", "note": "Cek cahaya.",
                             "source_ref": "fixture:window", "seconds": 2},
                            {"id": "desk", "rank": 2, "title": "MEJA", "note": "Ukur bayangan.",
                             "source_ref": "fixture:desk", "seconds": 1}]}
        _, report = listicle(plan, identity(plan))
        self.assertEqual(report["rank_order"], [2, 1])
        self.assertEqual(report["frames"], 6)
        self.assertEqual([(r["start_frame"], r["end_frame_exclusive"]) for r in report["sections"]], [(0, 2), (2, 6)])
        self.assertEqual(len({r["source_frame_sha256"] for r in report["sections"]}), 2)
        plan["entries"][1]["rank"] = 1
        with self.assertRaisesRegex(ContractError, "duplikat"):
            listicle(plan, identity(plan))
