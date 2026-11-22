from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from ._raster import blank
from ._story_video import box, write_movie
from .text_legibility_qa import audit_text


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class LegibilityTests(unittest.TestCase):
    def test_contrast_reads_real_frames_and_missing_sampling_is_flagged(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = blank(32, 24, (44, 47, 49))
            good = box(base, 12, 6, 6, 8, (240, 224, 205))
            poor = box(base, 12, 6, 6, 8, (48, 51, 53))
            raw, _ = write_movie([good, good, poor, good], 32, 24, 4)
            (root / "clip.mp4").write_bytes(raw)
            plan = {"schema": "ace.media.legibility-plan.v1",
                    "source": {"path": "clip.mp4", "sha256": sha256(raw).hexdigest()},
                    "min_height_px": 7, "min_contrast_milli": 4500, "max_sample_gap": 1,
                    "regions": [{"id": "intro", "source_ref": "fixture:caption", "first_frame": 0, "end_frame": 4,
                                 "glyph_height": 8, "ink": [13, 7, 4, 6], "background": [3, 4, 4, 5], "samples": [0, 2, 3]}]}
            report = audit_text(plan, identity(plan), root)
            row = report["regions"][0]
            self.assertEqual(row["blocked_by"], ["sample_gap", "contrast"])
            self.assertEqual(row["missed_ranges"], [[0, 2]])
            self.assertEqual([item["pass"] for item in row["samples"]], [True, False, True])
            self.assertEqual(row["samples"][1]["time_ms"], 500)
