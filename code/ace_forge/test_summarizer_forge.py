"""Verifier ekstraksi sumber, batas karakter, dan isolasi held-out."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import summarizer_forge as model
from ace_forge._forge_io import canonical, identity
from ace_forge.test_forgetting_guard import q


def sentences(key, *lines):
    return [{"id": f"s{i}", "source_ref": f"fixture/{key}/{i}", "text": text} for i, text in enumerate(lines)]


def fixture():
    return {"recipe_ref": "fixture/summary", "maximum_chars": 150, "maximum_sentences": 2, "documents": [
        {"id": "train", "family_id": "source-a", "split": "train", "annotation_ref": "fixture/gold/a",
         "sentences": sentences("learn", "Pasar naik cepat.", "Catatan lama biasa.", "Pasar naik lagi."),
         "selected_ids": ["s0", "s2"]},
        {"id": "held", "family_id": "source-b", "split": "held_out", "annotation_ref": "fixture/gold/b",
         "sentences": sentences("held", "Pasar naik hari ini.", "Catatan lama biasa.", "Pasar masih naik."),
         "selected_ids": ["s0", "s2"]},
    ]}


def fit(r):
    return model.forge(r, identity(r))


def apply(q_, result):
    return model.summarize(q_, identity(q_), result["adapter"], result["adapter_sha256"])


class SummaryTests(unittest.TestCase):
    def test_learns_positive_word_weight_and_retains_heldout_provenance(self):
        report = fit(fixture())
        self.assertGreater(report["adapter"]["word_weights"]["pasar"], 0)
        self.assertLess(report["adapter"]["word_weights"]["lama"], 0)
        self.assertEqual(report["precision"], q(1))
        self.assertEqual(report["recall"], q(1))
        self.assertEqual(report["held_out"][0]["selected"], [
            {"id": "s0", "source_ref": "fixture/held/0"}, {"id": "s2", "source_ref": "fixture/held/2"}])
        self.assertNotIn(b"hari ini", canonical(report))

    def test_applies_exact_source_text_in_document_order_and_counts_newline(self):
        trained = fit(fixture())
        raw = {"document_ref": "fixture/report", "maximum_chars": 80, "maximum_sentences": 2,
               "sentences": sentences("query", "Pasar naik lagi?", "Tidak dikenal.", " PASAR naik! ")}
        output = apply(raw, trained)
        self.assertEqual(output["summary"], "Pasar naik lagi?\n PASAR naik! ")
        self.assertEqual(output["chars"], len(output["summary"]))
        self.assertEqual(output["sentences"][1]["source_ref"], "fixture/query/2")
        raw["maximum_chars"] = len(raw["sentences"][2]["text"])
        self.assertEqual(apply(raw, trained)["summary"], " PASAR naik! ")
        raw["maximum_chars"] = 1
        held = apply(raw, trained)
        self.assertEqual(held["status"], "no_supported_selection")
        self.assertEqual(held["chars"], 0)

    def test_missing_support_no_synthetic_text_and_no_forced_fallback(self):
        raw = {"document_ref": "fixture/source", "maximum_chars": 6, "maximum_sentences": 1,
               "sentences": sentences("new", "???, kata asing")}
        report = apply(raw, fit(fixture()))
        self.assertEqual(report["summary"], "")
        self.assertEqual(report["sentences"], [])

    def test_no_selected_labels_in_train_or_family_leak_rejected(self):
        raw = fixture()
        raw["documents"][1]["family_id"] = raw["documents"][0]["family_id"]
        with self.assertRaisesRegex(model.InputError, "partisi"):
            fit(raw)
        raw = fixture()
        raw["documents"][0]["selected_ids"] = ["s0", "s1", "s2"]
        with self.assertRaisesRegex(model.InputError, "dilewatkan"):
            fit(raw)
        raw["documents"][0]["selected_ids"] = ["unknown"]
        with self.assertRaisesRegex(model.InputError, "Anotasi"):
            fit(raw)

    def test_heldout_labels_change_recall_without_touching_lexicon(self):
        raw = fixture()
        old = fit(raw)
        raw["documents"][1]["selected_ids"] = ["s1"]
        new = fit(raw)
        self.assertEqual(new["adapter_sha256"], old["adapter_sha256"])
        self.assertEqual(new["recall"], q(0))
        self.assertEqual(new["precision"], q(0))

    def test_cli_fits_sources_without_modifying_input(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "source.json"
        path.write_bytes(canonical(raw))
        with redirect_stdout(StringIO()) as result:
            self.assertEqual(model.main([str(path), "--expect-input-sha256", identity(raw)]), 0)
        self.assertEqual(json.loads(result.getvalue()), fit(raw))
        self.assertEqual(path.read_bytes(), canonical(raw))
