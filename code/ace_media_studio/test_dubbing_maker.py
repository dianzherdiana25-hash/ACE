from hashlib import sha256
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, wav
from ._contracts import ContractError, identity
from ._video import load_movie
from .dubbing_maker import dub
from .test_video_assembler import make_clip


@unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "FFmpeg lokal diperlukan")
class DubbingTests(unittest.TestCase):
    def test_languages_are_aligned_and_consume_their_own_verified_pcm(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)

            def save(name, data):
                (root / name).write_bytes(data)
                return {"path": name, "sha256": sha256(data).hexdigest()}

            source = save("video.mp4", make_clip(root, [(45, 60, 85)] * 3))
            refs = {}
            for lang, magnitude in (("id", 5000), ("en", 14000)):
                pcm = Audio(8000, 1, (magnitude, 0, -magnitude, 0) * 400)
                refs[lang] = save(f"{lang}.wav", wav(pcm)) | {"source_ref": f"fixture:{lang}"}
            plan = {"schema": "ace.media.dub-plan.v1", "source": source,
                    "segments": [{"id": "only", "start_frame": 1, "end_frame": 2, "voices": refs}]}
            files, report = dub(plan, identity(plan), root)
            self.assertEqual(set(files), {"dub_id.mp4", "dub_en.mp4"})
            self.assertNotEqual(report["languages"]["id"]["wav_sha256"], report["languages"]["en"]["wav_sha256"])
            for lang in refs:
                with TemporaryDirectory(dir=root) as stage:
                    decoded, fps, audio = load_movie(Path(stage), files[f"dub_{lang}.mp4"])
                self.assertEqual((len(decoded), fps, audio.frames), (3, 4, 18000))
                self.assertLess(max(map(abs, audio.samples[:4000])), 800)
                self.assertGreater(max(map(abs, audio.samples[6500:8500])), 2600)
            refs["id"].update(save("long.wav", wav(Audio(8000, 1, (500,) * 2200))))
            with self.assertRaisesRegex(ContractError, "melampaui slot"):
                dub(plan, identity(plan), root)
