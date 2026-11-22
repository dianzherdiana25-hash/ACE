from hashlib import sha256
import unittest

from ._audio import parse_wav
from ._contracts import ContractError, identity
from .scene_scorer import score_scenes


class ScoreTests(unittest.TestCase):
    def test_distinct_motifs_fill_only_declared_cues(self):
        plan = {"schema": "ace.media.scene-score.v1", "rate": 8000, "duration_ms": 600, "cues": [
            {"id": "intro", "source_ref": "fixture:opening", "start_ms": 50, "end_ms": 210,
             "tonic": 56, "mood": "warm", "peak": 12000},
            {"id": "close", "source_ref": "fixture:final", "start_ms": 320, "end_ms": 540,
             "tonic": 56, "mood": "resolve", "peak": 12000}]}
        raw, report = score_scenes(plan, identity(plan))
        pcm = parse_wav(raw)
        self.assertEqual(pcm.frames, 4800)
        self.assertEqual(set(pcm.samples[1680:2560]), {0})
        self.assertGreater(max(pcm.samples[400:1680]), 7000)
        self.assertEqual([r["midi_notes"] for r in report["cues"]], [[56, 60, 63, 68], [63, 60, 58, 56]])
        self.assertEqual(report["wav_sha256"], sha256(raw).hexdigest())
        plan["cues"][1]["start_ms"] = 200
        with self.assertRaisesRegex(ContractError, "Mulai cue"):
            score_scenes(plan, identity(plan))
