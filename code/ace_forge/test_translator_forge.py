"""Verifier frasa, segmentasi global, dan pemisahan held-out."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import translator_forge as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


def pair(key, source, target, direction="en-id", split="train"):
    return {"id": key, "direction": direction, "source": source, "target": target, "split": split,
            "family_id": f"family/{key}", "evidence_ref": f"fixture/translation/{key}"}


def fixture():
    return {"recipe_ref": "fixture/translation", "minimum_support": 1, "pairs": [
        pair("a", "red book", "buku merah"), pair("b", "RED BOOK", "buku merah"),
        pair("c", "is big", "itu besar"), pair("d", "sky", "langit"),
        pair("e", "buku merah", "red book", "id-en"),
        pair("t1", "bank", "tepi"), pair("t2", "bank", "bank"),
        pair("held", "Red book is big.", "buku merah itu besar.", split="held_out"),
    ]}


def fit(raw):
    return model.forge(raw, identity(raw))


def translate(text, output, direction="en-id"):
    raw = {"source_ref": "fixture/query", "direction": direction, "text": text}
    return model.translate(raw, identity(raw), output["adapter"], output["adapter_sha256"])


class TranslationTests(unittest.TestCase):
    def test_translates_composed_holdout_and_records_training_sources(self):
        outcome = fit(fixture())
        self.assertEqual(outcome["held_out_exact_match"], q(1))
        self.assertEqual(outcome["held_out"][0]["coverage"], q(1))
        text = translate("Red book is big.", outcome)
        self.assertEqual(text["translation"], "buku merah itu besar.")
        self.assertEqual(text["segments"][0], {"start": 0, "end": 8, "target": "buku merah",
                                               "status": "translated", "evidence_refs": ["fixture/translation/a", "fixture/translation/b"]})
        self.assertEqual(text["segments"][-1]["status"], "punctuation")

    def test_global_segmentation_beats_early_greedy_match(self):
        raw = {**fixture(), "pairs": [pair("a", "one two", "gabung"), pair("b", "one", "satu"),
                                     pair("c", "two three four", "dua tiga empat")]}
        result = translate("one two three four", fit(raw))
        self.assertEqual(result["translation"], "satu dua tiga empat")
        self.assertEqual(result["translated_words"], 4)

    def test_two_languages_and_tied_phrases_separate_unknown_and_punctuation(self):
        report = fit(fixture())
        self.assertEqual(translate("buku merah?", report, "id-en")["translation"], "red book?")
        value = translate("bank sky unknown!", report)
        self.assertEqual(value["translation"], "bank langit unknown!")
        self.assertEqual(value["coverage"], q(1, 3))
        self.assertEqual([row["status"] for row in value["segments"]], ["unresolved", "translated", "unresolved", "punctuation"])
        self.assertEqual(report["unresolved_phrases"][0]["reason"], "tied")

    def test_can_match_nfc_equivalent_text_and_returns_documented_offsets(self):
        raw = {**fixture(), "pairs": [pair("a", "café", "kopi")]}
        result = translate("  cafe\u0301! ", fit(raw))
        self.assertEqual(result["translation"], "  kopi! ")
        self.assertEqual(result["segments"][0]["end"], 6)
        self.assertEqual(result["offset_basis"], "nfc_codepoints")

    def test_raising_support_floor_records_unmapped_phrase_without_fake_scores(self):
        result = fit({**fixture(), "minimum_support": 2})
        self.assertEqual(result["held_out_exact_match"], q(0))
        self.assertEqual(result["held_out"][0]["coverage"], q(1, 2))
        self.assertIn("insufficient_support", {row["reason"] for row in result["unresolved_phrases"]})
        self.assertEqual(translate("not recorded", result)["coverage"], q(0))

    def test_family_exact_phrase_and_source_receipt_overlap_each_stop_fit(self):
        for mode in ("family", "phrase", "ref"):
            raw = fixture()
            if mode == "family":
                raw["pairs"][-1]["family_id"] = raw["pairs"][0]["family_id"]
            elif mode == "phrase":
                raw["pairs"][-1]["source"] = "RED book"
            else:
                raw["pairs"][-1]["evidence_ref"] = raw["pairs"][0]["evidence_ref"]
            with self.subTest(mode=mode), self.assertRaises(model.InputError):
                fit(raw)

    def test_cli_exports_reproducible_phrase_table_and_read_only_dataset(self):
        raw = fixture()
        folder = Path(self.enterContext(TemporaryDirectory()))
        path = folder / "pairs.json"
        path.write_bytes(canonical(raw))
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(model.main([str(path), "--expect-input-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(out.getvalue()), fit(raw))
        self.assertEqual(path.read_bytes(), canonical(raw))

    def test_unknown_direction_and_altered_adapter_have_explicit_errors(self):
        report = fit(fixture())
        raw = {"source_ref": "fixture/query", "text": "sky", "direction": "en-fr"}
        with self.assertRaisesRegex(model.InputError, "Arah"):
            model.translate(raw, identity(raw), report["adapter"], report["adapter_sha256"])
        raw["direction"] = "en-id"
        report["adapter"]["phrases"].clear()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.translate(raw, identity(raw), report["adapter"], report["adapter_sha256"])
