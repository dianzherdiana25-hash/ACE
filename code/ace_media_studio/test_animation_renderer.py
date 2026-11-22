from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ContractError, identity
from ._video import extract_frame
from .animation_renderer import animate


def animation_plan():
    return {"schema": "ace.media.animation-plan.v1", "width": 48, "height": 32,
            "fps": 3, "frames": 3, "camera": [0, -6500, 2000],
            "objects": [{"id": "sphere", "shape": "sphere", "color": "#F04010", "scale": [650, 650, 650],
                         "keyframes": [{"frame": 1, "location": [-1700, 0, 0]},
                                       {"frame": 3, "location": [1700, 0, 0]}]}]}


class AnimationTests(unittest.TestCase):
    @unittest.skipUnless(all(map(which, ("blender", "ffmpeg", "ffprobe"))), "Backend animasi lokal diperlukan")
    def test_renderer_blender_decodes_real_left_to_right_motion(self):
        plan = animation_plan()
        movie, report = animate(plan, identity(plan))
        self.assertEqual(report["backend"], "cycles_cpu")
        self.assertEqual(len(set(report["rgb_frame_sha256"])), 3)
        self.assertEqual((report["frames"], report["fps"], report["width"]), (3, [3, 1], 48))
        self.assertEqual(report["mp4_sha256"], sha256(movie).hexdigest())
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "result.mp4").write_bytes(movie)
            positions = []
            for index in (0, 2):
                frame = extract_frame(root, index)
                xs = [x for x in range(frame.width) for y in range(frame.height)
                      if (pixel := frame.at(x, y))[0] - pixel[1] > 23]
                self.assertTrue(xs)
                positions.append(sum(xs) / len(xs))
            self.assertLess(positions[0], 20)
            self.assertGreater(positions[1], 28)

    def test_nonanchored_keyframes_and_bad_camera_fail_before_render(self):
        plan = animation_plan()
        plan["objects"][0]["keyframes"][-1]["frame"] = 2
        with self.assertRaisesRegex(ContractError, "Keyframe"):
            animate(plan, identity(plan))
        plan = animation_plan()
        plan["camera"] = [0, 0, 0]
        with self.assertRaisesRegex(ContractError, "kamera"):
            animate(plan, identity(plan))
