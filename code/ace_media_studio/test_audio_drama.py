from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._audio import Audio, parse_wav, wav
from ._contracts import ContractError, identity
from .audio_drama import produce_drama


class DramaTests(unittest.TestCase):
    def test_sources_overlap_and_episode_pointer_survive_mixing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            effect = wav(Audio(8000, 1, (1500, -1500) * 400))
            (root / "effect.wav").write_bytes(effect)
            item = {"id": "rustle", "kind": "effect", "path": "effect.wav", "sha256": sha256(effect).hexdigest(),
                    "license_ref": "fixture:original", "source_ref": "fixture:foley", "overlap_ms": 60, "after_ms": 70}
            plan = {"schema": "ace.media.drama-plan.v1", "series": "test", "episode": 2,
                    "predecessor": "a" * 64, "rate": 8000, "cast": [
                        {"id": "one", "pitch_hz": 120, "speed_milli": 1000, "peak": 13000},
                        {"id": "two", "pitch_hz": 240, "speed_milli": 1100, "peak": 11000}],
                    "sequence": [{"id": "first", "kind": "line", "character": "one", "text": "Halo.",
                                  "source_ref": "fixture:first", "after_ms": 0}, item,
                                 {"id": "second", "kind": "line", "character": "two", "text": "Mari.",
                                  "source_ref": "fixture:second", "after_ms": 40}]}
            audio, report = produce_drama(plan, identity(plan), root)
            start, sound, end = report["cues"]
            self.assertEqual(sound["start_ms"], start["end_ms"] - 60)
            self.assertEqual(end["start_ms"], sound["end_ms"] + 70)
            self.assertEqual(parse_wav(audio).frames, (end["end_ms"] + 40) * 8)
            self.assertEqual(sound["license_ref"], item["license_ref"])
            self.assertEqual(report["declared_predecessor_sha256"], "a" * 64)
            self.assertEqual((audio, report), produce_drama(plan, identity(plan), root))
            item["overlap_ms"] = 9000
            with self.assertRaisesRegex(ContractError, "Overlap"):
                produce_drama(plan, identity(plan), root)
