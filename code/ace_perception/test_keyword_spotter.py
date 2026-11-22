"""Verifier pencarian pola akustik bersumber dan jendela kandidat eksak."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import keyword_spotter as model
from ace_perception.test_audio_pipeline import tone, wav


class KeywordTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.seed = tone(250, 320)+tone(500, 320)
        self.example = wav(self.seed)
        (self.root/"template.wav").write_bytes(self.example)
        self.plan = {"schema": "ace.perception-keyword-templates.v1", "plan_ref": "fixture/sound-pattern",
                     "frame_ms": 20, "frequencies_hz": [250, 500, 1000], "minimum_rms": 100,
                     "maximum_distance_bp": 0, "maximum_hits_per_template": 4,
                     "templates": [{"id": "sample", "label": "marker", "path": "template.wav", "source_ref": "fixture/example",
                                    "bytes": len(self.example), "sha256": sha256(self.example).hexdigest()}]}

    def run_detect(self, source):
        return model.detect(source, self.root, model._canonical(self.plan), model._sha(self.plan))

    def test_two_occurrences_from_pcm_and_nonoverlap_selection(self):
        other = tone(1000, 640)
        samples = other+self.seed+[0]*320+self.seed+[0]*13
        data = wav(samples)
        report = self.run_detect(data)
        pattern, = report["templates"]
        self.assertEqual(pattern["plausible_windows"], 2)
        self.assertEqual(pattern["hits"], [
            {"start_sample": 640, "end_sample": 1280, "start_us": 80_000, "end_us": 160_000,
             "distance_sum_bp": 0, "frames": 4},
            {"start_sample": 1600, "end_sample": 2240, "start_us": 200_000, "end_us": 280_000,
             "distance_sum_bp": 0, "frames": 4},
        ])
        self.assertEqual(report["unexamined_end_samples"], 13)
        self.assertEqual(pattern["template_sha256"], sha256(self.example).hexdigest())

    def test_off_target_no_hit_and_changed_template_fails_hash(self):
        source = wav(tone(1000, 1600))
        self.assertEqual(self.run_detect(source)["templates"][0]["hits"], [])
        (self.root/"template.wav").write_bytes(wav(tone(125, 640)))
        with self.assertRaisesRegex(ValueError, "Hash byte"):
            self.run_detect(source)
