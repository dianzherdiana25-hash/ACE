"""Verifier nilai bertipe dari kata yang benar-benar ada pada receipt."""
import unittest

from ace_perception import voice_note_structurer as model
from ace_perception.test_audio_language_detector import evidence
from ace_perception.test_audio_pipeline import fixture


def rules(cap=10):
    ideas=[("task","action","task"),("due","due_date","due date"),("amount","decimal","amount"),
           ("time","clock_time","at")]
    return model._canonical({"schema":"ace.perception-voice-note-rules.v1","maximum_value_words":cap,
                             "rules":[{"id":i,"kind":k,"prefix":p,"source_ref":f"fixture/{i}"} for i,k,p in ideas]})


class VoiceTests(unittest.TestCase):
    def test_typed_date_and_action_keep_source_span(self):
        wav=fixture()
        text=evidence(wav,("Due","date:","2026-11-21"),("Task:","review","artifacts"))
        date,action=model.structure(wav,text,rules())["items"]
        self.assertEqual(date["value"],"2026-11-21")
        self.assertEqual(date["rule_ref"],"fixture/due")
        self.assertEqual((date["value_start_us"],date["value_end_us"]),(28750,33125))
        self.assertEqual(action["value"],"review artifacts")
        self.assertEqual(action["status"],"structured")
        self.assertEqual(action["receipt_ref"],"fixture/receipt/2")

    def test_invalid_date_clock_and_empty_or_excess_have_no_invented_data(self):
        wav=fixture()
        text=evidence(wav,("Due","date","2026-02-30"),("at","24:00"))
        self.assertEqual([row["status"] for row in model.structure(wav,text,rules())["items"]],["invalid_value"]*2)
        values=evidence(wav,("amount","-1,25"),("task","long","words"))
        a,b=model.structure(wav,values,rules(1))["items"]
        self.assertEqual(a["value"],{"unscaled":-125,"scale":2})
        self.assertIsNone(b["value"])
        self.assertEqual(b["value_words"],2)
