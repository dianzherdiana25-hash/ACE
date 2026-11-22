from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, parse_wav, wav
from ._contracts import ContractError, identity
from .podcast_producer import produce


class PodcastTests(unittest.TestCase):
    def test_episode_cues_playable_clips_and_reproducibility(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            clip = wav(Audio(8000, 1, (1000,) * 640))
            (root / "local.wav").write_bytes(clip)
            media = {"path": "local.wav", "sha256": sha256(clip).hexdigest(),
                     "license_ref": "fixture:created-in-test"}
            plan = {"schema": "ace.media.podcast-plan.v1", "title": "Catatan cahaya", "rate": 8000,
                    "voice": {"pitch_hz": 130, "speed_milli": 1000, "peak": 12000, "seed": 9},
                    "segments": [
                        {"id": "opening", "kind": "voice", "title": "Pembuka",
                         "text": "Selamat datang.", "source_ref": "fixture:script"},
                        {"id": "rest", "kind": "pause", "title": "Jeda", "duration_ms": 80},
                        {"id": "closing", "kind": "clip", "title": "Penutup", **media}],
                    "bed": media | {"gain_milli": 250}}
            first = produce(plan, identity(plan), root)
            self.assertEqual(first, produce(plan, identity(plan), root))
            audio, receipt = first
            cues = receipt["chapters"]
            self.assertEqual([0, cues[0]["duration_ms"], cues[0]["duration_ms"] + 80],
                             [cue["start_ms"] for cue in cues])
            self.assertEqual(parse_wav(audio).frames, (cues[-1]["start_ms"] + 80) * 8)
            self.assertEqual(cues[-1]["asset_sha256"], media["sha256"])
            self.assertEqual(receipt["episode_wav_sha256"], sha256(audio).hexdigest())
            self.assertGreater(receipt["mix"]["ducked_frames"], 0)
            plan["segments"][2]["id"] = "opening"
            with self.assertRaisesRegex(ContractError, "ganda"):
                produce(plan, identity(plan), root)

    def test_all_pause_is_rejected(self):
        plan = {"schema": "ace.media.podcast-plan.v1", "title": "Jeda", "rate": 8000,
                "voice": {"pitch_hz": 130, "speed_milli": 1000, "peak": 10000, "seed": 4},
                "segments": [{"id": "rest", "kind": "pause", "title": "Jeda", "duration_ms": 80}],
                "bed": None}
        with TemporaryDirectory() as root, self.assertRaisesRegex(ContractError, "narasi"):
            produce(plan, identity(plan), root)
