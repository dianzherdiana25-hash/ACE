"""Verifier lima pembicara, bijeksi label, dan tiap komponen DER."""
from hashlib import sha256
import unittest

from ace_perception import diarization_bench as model, speaker_diarization
from ace_perception.test_audio_pipeline import tone, wav


def segment(a, b, who):
    return {"start_us": a, "end_us": b, "speaker_id": who}


class DerTests(unittest.TestCase):
    def test_five_tone_speakers_roundtrip_real_fixture_pipeline(self):
        data = []
        for frequency in (125, 250, 500, 1000, 1500):
            if data:
                data.extend([0]*1120)
            data.extend(tone(frequency))
        source = wav(data)
        tone_report = speaker_diarization.diarize(source, frequencies=(125,250,500,1000,1500))
        plan = {"schema": "ace.perception-diarization-gold.v1", "audio_sha256": sha256(source).hexdigest(),
                "gold_ref": "fixture/gold", "duration_us": 860000,
                "segments": [segment(index*200000, index*200000+60000, f"expected-{index}") for index in range(5)]}
        report = model.score(model._canonical(plan), model._canonical(tone_report), model._sha(plan))
        self.assertEqual((report["speaker_total"], report["predicted_speakers"]), (5, 5))
        self.assertEqual(report["correct_us"], 300000)
        self.assertEqual(report["der"], {"numerator": 0, "denominator": 1})
        self.assertEqual(len(report["alignment"]), 5)

    def test_miss_false_alarm_and_confusion_independent_and_overlap_refused(self):
        raw = {"schema": "ace.perception-diarization-gold.v1", "audio_sha256": "f"*64, "gold_ref": "fixture/gold",
               "duration_us": 50, "segments": [segment(10, 20, "a"), segment(20,35,"b")]}
        prediction = {"schema": "ace.perception-diarization.v1", "audio_sha256": "f"*64, "config": {},
                      "config_sha256": model._sha({}), "sample_rate": 8000, "speakers": [], "unattributed": [],
                      "segments": [segment(0, 5, "m"), segment(10, 15, "m"), segment(20,35,"m")]}
        def score():
            return model.score(model._canonical(raw), model._canonical(prediction), model._sha(raw))
        result = score()
        self.assertEqual([result[key] for key in ("miss_us", "false_alarm_us", "confusion_us", "correct_us")], [5, 5, 5, 15])
        self.assertEqual(result["der"], {"numerator": 3, "denominator": 5})
        prediction["segments"].append(segment(11,12,"other"))
        with self.assertRaisesRegex(ValueError, "tumpang tindih"):
            score()
