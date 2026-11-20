"""Uji bahwa brief menerbitkan kembali alasan dan rujukan yang tercatat."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import debate_protocol, decision_brief as briefs
from ace_deliberation.test_debate_protocol import fixture as debate_fixture
from ace_deliberation.test_precedent_memory import case


def fixture(debate=None):
    if debate is None:
        debate = debate_fixture()
    issue = debate["plan"]["question"]
    return {
        "debate": debate_protocol.replay(debate),
        "archive": [case("applicable", issue=issue),
                    case("opposition", issue=issue, conditions=["clearance"], outcome="reject")],
        "precedent_query": {"as_of": "2026-11-20", "tags": ["bridge"], "conditions": ["draf"], "limit": 5},
    }


class DecisionBriefTests(unittest.TestCase):
    def test_brief_cites_basis_dissent_and_good_precedent(self):
        raw = fixture()
        brief = briefs.make_brief(raw)
        self.assertEqual(brief["reason_recorded"], raw["debate"]["decision"]["rationale"])
        self.assertEqual(brief["basis"][0]["source"],
                         {"turn_id": "c1", "debate_sha256": raw["debate"]["sha256"]})
        note, = brief["dissent"]
        self.assertEqual(note["source"]["turn_id"], "b1")
        self.assertEqual([row["source"]["turn_id"] for row in note["responses"]], ["c1"])
        self.assertEqual(brief["unanswered_dissent_count"], 0)
        self.assertEqual(brief["precedent_status"], "cited")
        self.assertEqual(brief["precedent"]["source_ref"], "fixture/cases/applicable")
        self.assertEqual(brief["different_outcome_precedent"]["conditions_missing"], ["clearance"])

    def test_absent_or_inapplicable_history_does_not_fill_precedent(self):
        raw = fixture()
        raw["precedent_query"]["conditions"] = []
        report = briefs.make_brief(raw)
        self.assertIsNone(report["precedent"])
        self.assertEqual(report["precedent_status"], "no_applicable_candidate")
        self.assertEqual(len(report["precedent_candidates"]), 2)

    def test_unanswered_dissent_survives_outcome_defer(self):
        debate = debate_fixture()
        debate["turns"][-1]["targets"] = ["a1"]
        debate["decision"]["outcome"] = "defer"
        report = briefs.make_brief(fixture(debate))
        self.assertEqual(report["unanswered_dissent_count"], 1)
        self.assertEqual(report["dissent"][0]["responses"], [])
        self.assertIn("Belum ada tanggapan tercatat.", briefs.render_markdown(report))

    def test_rejects_tampered_and_unfinished_transcript(self):
        raw = fixture()
        tampered = deepcopy(raw)
        tampered["debate"]["decision"]["rationale"] = "dibuat ulang"
        incomplete = debate_fixture()
        incomplete["decision"] = None
        for candidate in (tampered, fixture(incomplete)):
            with self.subTest(candidate=candidate), self.assertRaises(briefs.BriefError):
                briefs.make_brief(candidate)

    def test_markdown_escapes_deliberation_text_and_is_deterministic(self):
        raw = debate_fixture()
        raw["decision"]["rationale"] = "# Uji\n[tautan](bad)"
        report = briefs.make_brief(fixture(raw))
        rendered = briefs.render_markdown(report)
        self.assertIn(r"\# Uji \[tautan\]\(bad\)", rendered)
        self.assertEqual(rendered, briefs.render_markdown(report))

    def test_cli_uses_same_structured_brief(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "brief.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(briefs.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), briefs.make_brief(raw))

    def test_shared_reference_is_indexed_once_with_distinct_uses(self):
        debate = debate_fixture()
        debate["turns"][1]["evidence_refs"] = ["fixture/shared"]
        debate["turns"][2]["evidence_refs"] = ["fixture/shared"]
        raw = fixture(debate)
        raw["archive"][0]["evidence_refs"] = ["fixture/shared"]
        brief = briefs.make_brief(raw)
        self.assertEqual(brief["reference_index"], [{
            "source_ref": "fixture/shared", "uses": [
                {"kind": "basis", "id": "c1"},
                {"kind": "dissent", "id": "b1"},
                {"kind": "precedent", "id": "applicable"},
                {"kind": "response", "id": "c1"},
            ],
        }])
        self.assertIn("basis c1, dissent b1, precedent applicable, response c1", briefs.render_markdown(brief))

    def test_preserves_all_challenges_instead_of_only_the_normative_basis(self):
        debate = debate_fixture()
        debate["turns"][1]["evidence_refs"] = ["fixture/challenge"]
        debate["turns"][0]["evidence_refs"] = ["fixture/ignored-argument"]
        brief = briefs.make_brief(fixture(debate))
        refs = {entry["source_ref"] for entry in brief["reference_index"]}
        self.assertIn("fixture/challenge", refs)
        self.assertNotIn("fixture/ignored-argument", refs)

    def test_same_day_precedent_is_excluded_from_decision_brief(self):
        raw = fixture()
        raw["archive"] = [case("same-day", day="2026-11-20")]
        brief = briefs.make_brief(raw)
        self.assertEqual(brief["precedent_status"], "no_applicable_candidate")
        self.assertEqual(brief["precedent_candidates"], [])

    def test_detached_exports_cannot_change_transcript_used_for_replay(self):
        raw = fixture()
        first = briefs.make_brief(raw)
        first["basis"][0]["evidence_refs"].append("fake")
        first["dissent"][0]["responses"].clear()
        self.assertTrue(debate_protocol.verify_report(raw["debate"]))
        second = briefs.make_brief(raw)
        self.assertNotIn("fake", second["basis"][0]["evidence_refs"])
        self.assertEqual(len(second["dissent"][0]["responses"]), 1)

    def test_reference_status_is_explicit_for_empty_archive(self):
        result = briefs.make_brief({**fixture(), "archive": []})
        self.assertEqual(result["precedent_status"], "no_applicable_candidate")
        self.assertIsNone(result["different_outcome_precedent"])
