"""Verifier kelas bahasa yang bergantung pada receipt PCM dan penanda sumber."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_perception import audio_language_detector as model, audio_pipeline
from ace_perception.test_audio_pipeline import fixture, receipt


def profiles(**edits):
    return model._canonical({"schema": "ace.perception-language-profile.v1", "minimum_hits": 2,
                             "minimum_margin": 1, "mixed_minimum_hits": 2,
                             "profiles": [{"code": "id", "source_ref": "fixture/id", "terms": ["halo", "dunia", "uji", "radar"]},
                                          {"code": "en", "source_ref": "fixture/en", "terms": ["hello", "world", "radar"]}], **edits})


def evidence(src, first, second, missing=False):
    rows = receipt(audio_pipeline.segment(src))
    for row, terms in zip(rows["segments"], (first, second), strict=True):
        start = row["words"][0]["start_sample"]
        row["words"] = [{"word": term, "start_sample": start+offset*35, "end_sample": start+(offset+1)*35}
                        for offset, term in enumerate(terms)]
    if missing:
        rows["segments"].pop()
    return model._canonical(rows)


class LanguageTests(unittest.TestCase):
    def test_bound_receipt_classifies_distinct_language_or_no_transcript(self):
        src = fixture()
        report = model.detect(src, evidence(src, ("HALO", "dunia", "radar"), ("hello",), missing=True), profiles())
        self.assertEqual(report["shared_terms_excluded"], 1)
        self.assertEqual(report["counts"], {"classified": 1, "no_transcript": 1})
        first, second = report["segments"]
        self.assertEqual(first["language"], "id")
        self.assertEqual(first["tokens_examined"], 3)
        self.assertEqual(first["transcript_ref"], "fixture/receipt/1")
        self.assertEqual(first["evidence"], [{"code": "id", "distinct_hits": 2, "profile_ref": "fixture/id"}])
        self.assertEqual((first["start_us"], first["end_us"]), (20_000, 80_000))
        self.assertIsNone(second["language"])
        self.assertEqual(second["evidence"], [])

    def test_repeated_words_do_not_create_distinct_support(self):
        src = fixture()
        report = model.detect(src, evidence(src, ("hello",)*5, ("halo", "halo", "radar")), profiles())
        self.assertEqual([row["status"] for row in report["segments"]], ["insufficient_evidence"]*2)
        self.assertEqual(report["segments"][0]["evidence"][0]["distinct_hits"], 1)

    def test_mixed_distinguished_from_close_runner_up(self):
        src = fixture()
        text = evidence(src, ("halo", "world", "hello", "dunia"), ("hello", "world", "halo"))
        report = model.detect(src, text, profiles())
        self.assertEqual(report["segments"][0]["status"], "mixed")
        self.assertEqual(report["segments"][0]["mixed_languages"], ["en", "id"])
        self.assertEqual(report["segments"][1]["language"], "en")
        held = model.detect(src, text, profiles(minimum_margin=2, mixed_minimum_hits=3))
        self.assertEqual([row["status"] for row in held["segments"]], ["undecided"]*2)

    def test_transcript_anchor_and_profile_uniqueness_validation(self):
        src = fixture()
        words = evidence(src, ("halo", "dunia"), ("hello", "world"))
        with self.assertRaisesRegex(ValueError, "roster"):
            model.detect(src, words, profiles(), rms=500)
        spec = json.loads(profiles())
        spec["profiles"][1]["terms"].append("WORLD")
        with self.assertRaisesRegex(ValueError, "token unik"):
            model.detect(src, words, model._canonical(spec))

    def test_cli_reports_without_writing_any_input(self):
        folder = Path(self.enterContext(TemporaryDirectory()))
        audio, text, definitions = (folder/name for name in ("source.wav", "text", "profiles"))
        data = fixture()
        inputs = data, evidence(data, ("halo", "dunia"), ("hello", "world")), profiles()
        for path, payload in zip((audio, text, definitions), inputs, strict=True):
            path.write_bytes(payload)
        args = [sys.executable, "-m", "ace_perception.audio_language_detector", *map(str, (audio, text, definitions))]
        run = subprocess.run(args, capture_output=True, check=True)
        self.assertEqual(json.loads(run.stdout), model.detect(*inputs))
        self.assertEqual([path.read_bytes() for path in (audio, text, definitions)], list(inputs))
