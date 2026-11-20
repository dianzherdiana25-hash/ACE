"""Uji keterikatan argumen dan angka pada dua format brief."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import dual_brief
from ace_deliberation.test_debate_protocol import fixture as debate_fixture
from ace_deliberation.test_decision_brief import fixture as brief_fixture


def term(name, plain, label):
    return {"term": name, "plain": plain, "source_ref": f"fixture/glossary/{label}"}


def fixture():
    raw = debate_fixture()
    raw["decision"]["rationale"] = "Uji baseline laju dasar 95% sebelum adopsi."
    raw["turns"][1]["statement"] = "Baseline sumber perlu diuji pada 12 contoh."
    return {"brief_input": brief_fixture(raw), "glossary": [
        term("baseline laju dasar", "pembanding frekuensi awal", "full"),
        term("baseline", "pembanding", "base"), term("uji statistik", "periksa angka", "unused"),
    ]}


class DualBriefTests(unittest.TestCase):
    def test_two_views_keep_numbers_outcome_sources_and_original_text(self):
        report = dual_brief.create_dual(fixture())
        tech, plain = report["technical"], report["plain"]
        self.assertIn("baseline laju dasar 95%", tech["reason_recorded"])
        self.assertIn("pembanding frekuensi awal 95%", plain["reason_recorded"])
        self.assertEqual(tech["outcome"], plain["outcome"])
        self.assertEqual(tech["reference_index"], plain["reference_index"])
        self.assertEqual(tech["dissent"][0]["source"], plain["dissent"][0]["source"])
        self.assertIn("pembanding sumber perlu diuji pada 12", plain["dissent"][0]["statement"])
        self.assertEqual(report["glossary_unused"], ["uji statistik"])

    def test_glossary_numbers_cannot_be_translated_to_other_values(self):
        raw = fixture()
        raw["glossary"].append(term("95%", "94%", "numeric"))
        with self.assertRaisesRegex(dual_brief.DualBriefError, "angka literal"):
            dual_brief.create_dual(raw)

    def test_glossary_replacement_has_word_boundaries_and_never_cascades(self):
        raw = fixture()
        raw["glossary"].extend([term("pembanding", "pemeriksaan lain", "cascade"),
                                term("uji", "teliti", "test")])
        report = dual_brief.create_dual(raw)
        text = report["plain"]["dissent"][0]["statement"]
        self.assertIn("pembanding sumber perlu diuji", text)
        self.assertNotIn("pemeriksaan lain", text)
        self.assertIn("pembanding", report["glossary_unused"])

    def test_duplicate_casefold_term_and_unsupported_source_are_rejected(self):
        raw = fixture()
        for row in (term("BASELINE", "padanan", "dupe"), term("contoh", "sampel", "base")):
            with self.subTest(row=row), self.assertRaises(dual_brief.DualBriefError):
                dual_brief.create_dual({**raw, "glossary": [*raw["glossary"], row]})

    def test_cli_plain_and_technical_use_one_verified_digest(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "dual.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        texts = []
        for style in ("plain", "technical"):
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(dual_brief.main([str(path), "--format", style]), 0)
            texts.append(output.getvalue())
        digest = raw["brief_input"]["debate"]["sha256"]
        self.assertTrue(all(digest in payload for payload in texts))
        self.assertIn("versi awam", texts[0])
        self.assertNotEqual(*texts)

    def test_empty_glossary_leaves_same_words_and_all_refs(self):
        report = dual_brief.create_dual({**fixture(), "glossary": []})
        self.assertEqual(report["technical"]["reason_recorded"], report["plain"]["reason_recorded"])
        self.assertEqual(report["glossary_used"], [])

    def test_trace_recomputes_hashes_of_each_rewritten_field(self):
        import hashlib

        report = dual_brief.create_dual(fixture())
        first, second = report["rewrite_trace"]
        self.assertEqual(first["location"], "reason_recorded")
        self.assertEqual(first["numbers"], ["95%"])
        self.assertEqual(first["glossary_hits"], {"baseline laju dasar": 1})
        for format_name, field in (("technical", "technical_sha256"), ("plain", "plain_sha256")):
            value = report[format_name]["reason_recorded"].encode("utf-8")
            self.assertEqual(hashlib.sha256(value).hexdigest(), first[field])
        self.assertEqual(second["location"], "dissent/b1")
        self.assertEqual(second["numbers"], ["12"])

    def test_changing_plain_precedent_and_refs_does_not_change_technical_export(self):
        report = dual_brief.create_dual(fixture())
        report["plain"]["precedent"]["source_ref"] = "fake"
        report["plain"]["reference_index"].clear()
        self.assertEqual(report["technical"]["precedent"]["source_ref"], "fixture/cases/applicable")
        self.assertTrue(report["technical"]["reference_index"])

    def test_plain_markdown_exposes_precedent_provenance_and_conflicting_case(self):
        result = dual_brief.create_dual(fixture())
        exposed = dual_brief.render_plain(result)
        self.assertIn("## Putusan terdahulu", exposed)
        self.assertIn("fixture/cases/applicable", exposed)
        self.assertIn("fixture/cases/opposition", exposed)

    def test_rewriting_none_has_no_audit_trace(self):
        self.assertEqual(dual_brief.create_dual({**fixture(), "glossary": []})["rewrite_trace"], [])

    def test_signed_and_percent_literals_survive_rewriting_unmodified(self):
        source = debate_fixture()
        source["decision"]["rationale"] = "Baseline bergeser -1,5 poin dan +2.0%."
        raw = {**fixture(), "brief_input": brief_fixture(source)}
        result = dual_brief.create_dual(raw)
        self.assertEqual(result["rewrite_trace"][0]["numbers"], ["-1,5", "+2.0%"])
        self.assertIn("-1,5 poin dan +2.0%", result["plain"]["reason_recorded"])
