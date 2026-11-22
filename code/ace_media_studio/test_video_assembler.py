from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, wav
from ._contracts import ContractError, identity
from ._raster import blank
from ._video import encode_frames, extract_frame, load_movie
from .video_assembler import assemble


def make_clip(root, shades, fps=4, audio=False, width=32, height=24):
    with TemporaryDirectory(dir=root) as temporary:
        return encode_frames(Path(temporary), (blank(width, height, item) for item in shades),
                             width, height, fps,
                             wav(Audio(8000, 1, (0, 5000, 0, -5000) *
                                 (len(shades) * 2000 // fps))) if audio else None)[0]


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class AssemblyTests(unittest.TestCase):
    def test_trimmed_mp4_preserves_frame_order_and_audio_duration(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = make_clip(root, [(230, 20, 20), (20, 230, 20)], audio=True)
            second = make_clip(root, [(20, 20, 230), (230, 230, 20)], audio=True)
            clips = []
            for name, data, start, end in (("one", first, 1, 2), ("two", second, 0, 2)):
                path = root / f"{name}.mp4"
                path.write_bytes(data)
                clips.append({"id": name, "path": path.name, "sha256": sha256(data).hexdigest(),
                              "from_frame": start, "to_frame": end})
            plan = {"schema": "ace.media.assembly-plan.v1", "audio_policy": "preserve", "clips": clips}
            payload, report = assemble(plan, identity(plan), root)
            self.assertEqual(report["frames"], 3)
            self.assertEqual(report["audio"], "aac")
            self.assertEqual([(0, 1), (1, 3)], [tuple(clip["output_frames"]) for clip in report["clips"]])
            (root / "result.mp4").write_bytes(payload)
            self.assertGreater(extract_frame(root, 0).at(15, 12)[1], 200)
            self.assertGreater(extract_frame(root, 1).at(15, 12)[2], 200)
            _, _, audio = load_movie(root, payload)
            self.assertEqual(audio.frames, 18000)
            self.assertGreater(audio.receipt()["peak"], 3000)
            plan["clips"][0]["to_frame"] = 3
            with self.assertRaisesRegex(ContractError, "Frame akhir"):
                assemble(plan, identity(plan), root)

    def test_audio_policy_fails_for_missing_source_audio(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = make_clip(root, [(230, 20, 20)])
            (root / "one.mp4").write_bytes(first)
            plan = {"schema": "ace.media.assembly-plan.v1", "audio_policy": "preserve", "clips": [
                {"id": "one", "path": "one.mp4", "sha256": sha256(first).hexdigest(), "from_frame": 0, "to_frame": 1}]}
            with self.assertRaisesRegex(ContractError, "pada setiap klip"):
                assemble(plan, identity(plan), root)
            plan["audio_policy"] = "mute"
            self.assertIsNone(assemble(plan, identity(plan), root)[1]["audio"])
