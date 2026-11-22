from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, wav
from ._contracts import ContractError, identity
from ._video import extract_frame
from .video_composer import compose


def video_plan(audio=None):
    return {"schema": "ace.media.video-plan.v1", "width": 32, "height": 24,
            "fps": 4, "soundtrack": audio, "scenes": [
                {"id": "shift", "frames": 3, "source_ref": "fixture:act-one",
                 "instructions": "CANVAS 64 24 #101010\nRECT 32 0 32 24 #F00A10",
                 "from": [0, 0], "to": [32, 0]},
                {"id": "end", "frames": 1, "source_ref": "fixture:act-two",
                 "instructions": "CANVAS 32 24 #0AF020\nRECT 0 0 2 2 #0AF020", "from": [0, 0], "to": [0, 0]}]}


class VideoTests(unittest.TestCase):
    @unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
    def test_video_decodes_camera_motion_scene_cut_audio_and_frame_count(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            sound = wav(Audio(8000, 1, (0, 5000, 0, -5000) * 2000))
            (root / "source.wav").write_bytes(sound)
            plan = video_plan({"path": "source.wav", "sha256": sha256(sound).hexdigest()})
            movie, info = compose(plan, identity(plan), root)
            self.assertEqual((info["frames"], info["fps"], info["audio"], info["codec"]), (4, [4, 1], "aac", "h264"))
            self.assertEqual(info["mp4_sha256"], sha256(movie).hexdigest())
            self.assertEqual([(0, 3), (3, 4)], [(row["first_frame"], row["last_frame_exclusive"])
                                               for row in info["scene_timeline"]])
            (root / "result.mp4").write_bytes(movie)
            self.assertLess(max(extract_frame(root, 0).at(8, 8)), 30)
            self.assertGreater(extract_frame(root, 2).at(8, 8)[0], 200)
            self.assertGreater(extract_frame(root, 3).at(8, 8)[1], 200)
            self.assertEqual(movie, compose(plan, identity(plan), root)[0])

    def test_wrong_camera_and_sound_length_fail_before_encoding(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = video_plan()
            plan["scenes"][0]["to"] = [33, 0]
            with self.assertRaisesRegex(ContractError, "Kamera"):
                compose(plan, identity(plan), root)
            raw = wav(Audio(8000, 1, (0,) * 4000))
            (root / "short.wav").write_bytes(raw)
            plan = video_plan({"path": "short.wav", "sha256": sha256(raw).hexdigest()})
            with self.assertRaisesRegex(ContractError, "Durasi soundtrack"):
                compose(plan, identity(plan), root)
