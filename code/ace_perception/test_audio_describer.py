"""Verifier jadwal narasi, clip tertambat, dan WAV tanpa overlap."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import _audio, audio_describer as model
from ace_perception.test_audio_pipeline import wav


class DescriberTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.plan = {"schema": "ace.perception-audio-description-plan.v1", "visual_sha256": "a"*64,
                     "duration_us": 300000, "sample_rate": 8000, "minimum_gap_us": 10000,
                     "maximum_delay_us": 100000, "characters_per_second": 20,
                     "silence": [{"start_us": 50000, "end_us": 130000, "source_ref": "fixture/s1"},
                                 {"start_us": 180000, "end_us": 290000, "source_ref": "fixture/s2"}],
                     "cues": []}

    def cue(self, key, at, text, clip=True):
        data = wav([600]*320)
        (self.root/f"{key}.wav").write_bytes(data)
        bound = {"path": f"{key}.wav", "bytes": len(data), "sha256": sha256(data).hexdigest(),
                 "quote_sha256": sha256(text.encode()).hexdigest(), "source_ref": f"fixture/narrated/{key}"} if clip else None
        self.plan["cues"].append({"id": key, "visual_time_us": at, "description": text,
                                  "source_ref": f"fixture/scene/{key}", "clip": bound})

    def run_plan(self):
        return model.build(self.root, model._canonical(self.plan))

    def test_joins_wav_clips_with_exact_quiet_gaps_and_source_evidence(self):
        self.cue("one", 0, "left")
        self.cue("two", 120000, "right")
        artifact, report = self.run_plan()
        self.assertEqual(report["status"], "audio_rendered")
        self.assertEqual([row["slot"] for row in report["cues"]], [
            {"start_us": 50000, "end_us": 90000, "source_ref": "fixture/s1"},
            {"start_us": 180000, "end_us": 220000, "source_ref": "fixture/s2"},
        ])
        decoded = _audio.decode(artifact)
        self.assertEqual(decoded.sample_count, 2400)
        self.assertEqual(sum(sample == 600 for sample in decoded.mono), 640)
        self.assertEqual(sum(decoded.mono[720:1440]), 0)
        self.assertEqual(report["output_sha256"], sha256(artifact).hexdigest())

    def test_unrendered_text_and_unscheduled_clip_diagnosed(self):
        self.cue("one", 0, "a", clip=False)
        self.cue("two", 280000, "too-late")
        artifact, report = self.run_plan()
        self.assertIsNone(artifact)
        self.assertEqual(report["status"], "plan_only")
        self.assertEqual([row["status"] for row in report["cues"]], ["scheduled", "no_silence_slot"])

    def test_clip_for_a_different_caption_rejected(self):
        self.cue("one", 5, "this")
        self.plan["cues"][0]["description"] = "different"
        with self.assertRaisesRegex(ValueError, "tidak tertambat"):
            self.run_plan()
