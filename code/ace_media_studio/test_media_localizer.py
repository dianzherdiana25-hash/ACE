import unittest

from ._contracts import ContractError, identity
from .media_localizer import localize


class LocalizeTests(unittest.TestCase):
    def test_localization_preserves_quantities_terms_placeholders_and_origin(self):
        plan = {"schema": "ace.media.localization.v1", "source_language": "id", "target_language": "en",
                "max_chars_per_sec": 20, "glossary": [
                    {"source": "cahaya", "target": "light", "source_ref": "fixture:dictionary"}],
                "translations": [
                    {"source": "Cahaya 12 lux untuk {name}.", "target": "Light 12 lux for {name}.",
                     "source_ref": "fixture:translator"},
                    {"source": "Cahaya 2 untuk {name}.", "target": "Brightness 3 for {recipient}.",
                     "source_ref": "fixture:translator"}],
                "segments": [
                    {"id": "valid", "start_ms": 0, "end_ms": 4000, "text": "Cahaya 12 lux untuk {name}.",
                     "source_ref": "fixture:source1"},
                    {"id": "wrong", "start_ms": 4000, "end_ms": 4350, "text": "Cahaya 2 untuk {name}.",
                     "source_ref": "fixture:source2"},
                    {"id": "missing", "start_ms": 4350, "end_ms": 6350, "text": "Belum diterjemahkan.",
                     "source_ref": "fixture:source3"}]}
        report = localize(plan, identity(plan))
        good, wrong, missing = report["segments"]
        self.assertEqual((report["ready"], report["holding"]), (1, 2))
        self.assertEqual(good["localized"], "Light 12 lux for {name}.")
        self.assertEqual(good["translation_source_ref"], "fixture:translator")
        self.assertEqual(good["glossary"][0]["source_ref"], "fixture:dictionary")
        self.assertEqual(wrong["reasons"], ["placeholder_drift", "number_drift", "reading_rate", "terminology_drift"])
        self.assertIsNone(wrong["localized"])
        self.assertEqual(missing["reasons"], ["missing_translation"])
        plan["segments"][-1]["start_ms"] -= 1
        with self.assertRaisesRegex(ContractError, "Waktu awal"):
            localize(plan, identity(plan))
