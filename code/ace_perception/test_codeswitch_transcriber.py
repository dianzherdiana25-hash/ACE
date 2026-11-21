"""Verifier cap waktu per kata, peralihan, dan pilihan konteks terbatas."""
import unittest

from ace_perception import codeswitch_transcriber as model
from ace_perception.test_audio_language_detector import evidence, profiles
from ace_perception.test_audio_pipeline import fixture


class CodeSwitchTests(unittest.TestCase):
    def test_switch_alignment_and_same_language_context_label(self):
        wav = fixture()
        text = evidence(wav, ("hello", "unseen", "world", "halo", "dunia"), ("uji", "hello"))
        result = model.transcribe(wav, text, profiles(), bridge_unknown=1)
        first = result["segments"][0]
        self.assertEqual([row["language"] for row in first["words"]], ["en", "en", "en", "id", "id"])
        self.assertEqual(first["words"][1]["language_source"], "neighbor_context")
        self.assertEqual(first["language_runs"][0]["marker_count"], 2)
        self.assertEqual(result["switches"], [
            {"segment": "s0001", "from": "en", "to": "id", "start_us": 33125,
             "receipt_ref": "fixture/receipt/1", "left_profile_ref": "fixture/en", "right_profile_ref": "fixture/id"},
            {"segment": "s0002", "from": "id", "to": "en", "start_us": 204375,
             "receipt_ref": "fixture/receipt/2", "left_profile_ref": "fixture/id", "right_profile_ref": "fixture/en"},
        ])

    def test_mixed_neighbors_leave_unknown_and_do_not_invent_switch_time(self):
        source = fixture()
        words = evidence(source, ("hello", "radar", "halo"), ("uji",), missing=True)
        result = model.transcribe(source, words, profiles(), bridge_unknown=3)
        self.assertIsNone(result["segments"][0]["words"][1]["language"])
        self.assertEqual(result["segments"][0]["unlabelled_words"], 1)
        self.assertEqual(result["switches"], [])
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["segments"][1]["status"], "missing")
