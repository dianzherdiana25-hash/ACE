"""Verifier kutipan berbukti, aturan yang menang, dan gap rapat."""
import unittest

from ace_perception import meeting_summarizer as model
from ace_perception.test_audio_language_detector import evidence
from ace_perception.test_audio_pipeline import fixture


def policy(maximum=4, context=1):
    return model._canonical({"schema": "ace.perception-meeting-rules.v1", "context_words": context,
                             "maximum_excerpts": maximum, "rules": [
        {"id": "topic", "kind": "topic", "phrase": "we", "source_ref": "fixture/topic"},
        {"id": "decision", "kind": "decision", "phrase": "we decided", "source_ref": "fixture/decision"},
        {"id": "action", "kind": "action", "phrase": "review 24", "source_ref": "fixture/action"},
    ]})


class MeetingTests(unittest.TestCase):
    def test_longer_rule_uses_exact_actual_words_and_time(self):
        src = fixture()
        text = evidence(src, ("We", "decided:", "open", "then"), ("review", "24", "tomorrow"))
        report = model.summarize(src, text, policy())
        self.assertEqual(report["counts"], {"action": 1, "decision": 1})
        decision, action = report["excerpts"]
        self.assertEqual(decision["quote"], "We decided: open")
        self.assertEqual(decision["word_interval"], [0, 3])
        self.assertEqual((decision["start_us"], decision["end_us"]), (20000, 33125))
        self.assertEqual(action["quote"], "review 24 tomorrow")
        self.assertEqual(action["receipt_ref"], "fixture/receipt/2")

    def test_missing_segment_and_limited_excerpts_are_separate(self):
        src = fixture()
        missing = evidence(src, ("we", "decided", "we"), ("review", "24"), missing=True)
        result = model.summarize(src, missing, policy(maximum=1, context=0))
        self.assertEqual(result["transcript_gaps"], [{"segment": "s0002", "status": "missing", "receipt_ref": None}])
        self.assertEqual(result["omitted_excerpts"], 1)
        self.assertEqual(result["counts"], {"decision": 1, "topic": 1})
        wrong = evidence(src, ("review", "25"), ("review", "23"))
        self.assertEqual(model.summarize(src, wrong, policy())["excerpts"], [])
