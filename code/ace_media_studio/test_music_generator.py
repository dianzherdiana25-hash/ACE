from hashlib import sha256
import unittest

from ._audio import parse_wav
from ._contracts import ContractError, identity
from .music_generator import generate_music


class MusicTests(unittest.TestCase):
    def test_real_audio_tempo_chords_headroom_repeatability(self):
        plan = {"schema": "ace.media.music-plan.v1", "id": "fixture", "source_ref": "fixture:new-score",
                "rate": 8000, "bpm": 120, "tonic": 48, "mode": "major", "bars": 2,
                "progression": [{"degree": 1, "transpose": 0, "accent": 600},
                                {"degree": 5, "transpose": 0, "accent": 600}],
                "rhythm": "quarter", "seed": 9, "headroom": 10000}
        raw, report = generate_music(plan, identity(plan))
        self.assertEqual(report["bars"][0]["notes_midi"], [48, 52, 55])
        self.assertEqual(report["bars"][1]["notes_midi"], [55, 59, 62])
        self.assertEqual(report["bars"][1]["start_frame"], 16000)
        self.assertEqual(parse_wav(raw).frames, 32000)
        self.assertTrue(2000 < parse_wav(raw).receipt()["peak"] <= 10000)
        self.assertEqual(report["wav_sha256"], sha256(raw).hexdigest())
        self.assertEqual(raw, generate_music(plan, identity(plan))[0])
        plan["seed"] += 1
        self.assertNotEqual(raw, generate_music(plan, identity(plan))[0])
        plan["bars"] += 1
        with self.assertRaisesRegex(ContractError, "membagi"):
            generate_music(plan, identity(plan))
