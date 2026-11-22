from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from ._video import extract_frame
from .data_motion import animate_data


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class DataMotionTests(unittest.TestCase):
    def test_signed_bars_cross_fixed_baseline_and_retain_source(self):
        plan = {"schema": "ace.media.data-motion.v1", "width": 120, "height": 64, "fps": 4, "frames": 5,
                "series": ["one", "two"], "keyframes": [
                    {"frame": 0, "values": {"one": -8, "two": 4}, "source_ref": "fixture:first"},
                    {"frame": 4, "values": {"one": 8, "two": -4}, "source_ref": "fixture:last"}]}
        data, receipt = animate_data(plan, identity(plan))
        trace = receipt["measurement"]
        self.assertEqual(trace[2]["interpolated_numerators"], [0, 0])
        self.assertEqual(trace[1]["denominator"], 4)
        self.assertEqual(trace[0]["bar_lengths"], [-20, 10])
        self.assertEqual(trace[-1]["bar_lengths"], [20, -10])
        self.assertEqual(receipt["keyframes"][-1]["source_ref"], "fixture:last")
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result.mp4").write_bytes(data)
            y = receipt["zero_baseline_y"]
            self.assertGreater(extract_frame(root, 0).at(15, y + 5)[0], 150)
            self.assertGreater(extract_frame(root, 4).at(15, y - 5)[2], 150)
        plan["keyframes"][0]["frame"] = 1
        with self.assertRaisesRegex(ContractError, "wajib ada"):
            animate_data(plan, identity(plan))
