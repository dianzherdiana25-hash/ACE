"""Uji bahwa pemetaan posisi tidak menelan dissent di luar mayoritas."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import debate_protocol, minority_report
from ace_deliberation.test_debate_protocol import fixture as debate_fixture


def fixture():
    raw = debate_fixture()
    raw["plan"]["seats"].insert(2, {"participant": "d", "role": "challenger"})
    raw["plan"]["budget"] += 2
    raw["turns"].insert(2, {**raw["turns"][1], "turn_id": "d1", "participant": "d",
                            "statement": "Batas data belum teruji", "evidence_refs": ["fixture/bounds"]})
    raw["decision"]["outcome"] = "defer"
    return {"debate": debate_protocol.replay(raw), "positions": [
        {"id": "independence", "title": "Dua sumber independen", "objections": ["b1"],
         "alternative": {"statement": "Ambil sumber kedua", "source_ref": "fixture/alternative"}},
    ]}


class MinorityTests(unittest.TestCase):
    def test_grouping_keeps_open_unassigned_and_independent_alternative(self):
        report = minority_report.build_report(fixture())
        self.assertEqual((report["objection_count"], report["author_count"], report["open_count"]), (2, 2, 1))
        position, = report["positions"]
        self.assertEqual(position["authors"], ["b"])
        self.assertEqual(position["open_objections"], [])
        self.assertEqual(position["alternative"]["source_ref"], "fixture/alternative")
        self.assertEqual(position["objections"][0]["response_status"], "referenced")
        leftover, = report["unassigned_objections"]
        self.assertEqual((leftover["turn_id"], leftover["response_status"]), ("d1", "open"))
        self.assertEqual(leftover["evidence_refs"], ["fixture/bounds"])
        self.assertEqual(report["contested_turns"][0]["objection_ids"], ["b1", "d1"])

    def test_same_position_across_two_authors_preserves_each_response_status(self):
        raw = fixture()
        raw["positions"][0]["objections"].append("d1")
        report = minority_report.build_report(raw)
        position, = report["positions"]
        self.assertEqual(position["authors"], ["b", "d"])
        self.assertEqual(position["open_objections"], ["d1"])
        self.assertEqual(report["unassigned_objections"], [])

    def test_bad_mapping_cannot_reference_majority_as_dissent_or_lose_objections(self):
        raw = fixture()
        position = raw["positions"][0]
        cases = [[{**position, "objections": ["a1"]}],
                 [position, {**position, "id": "duplicate-use"}],
                 [{**position, "alternative": {"statement": "unbound"}}]]
        for positions in cases:
            with self.subTest(positions=positions), self.assertRaises(minority_report.MinorityError):
                minority_report.build_report({**raw, "positions": positions})

    def test_no_alt_statement_is_synthesized_when_absent(self):
        raw = fixture()
        raw["positions"][0]["alternative"] = None
        report = minority_report.build_report(raw)
        self.assertIsNone(report["positions"][0]["alternative"])
        self.assertNotIn("Alternatif tercatat", minority_report.render_markdown(report))

    def test_input_provenance_and_objection_reports_are_detached(self):
        raw = fixture()
        initial = minority_report.build_report(raw)
        exported = minority_report.build_report(raw)
        exported["unassigned_objections"][0]["evidence_refs"].clear()
        self.assertEqual(initial, minority_report.build_report(raw))
        self.assertEqual(raw["debate"]["dissent_turns"], ["b1", "d1"])

    def test_unverified_transcript_is_refused(self):
        raw = fixture()
        raw["debate"]["dissent_turns"].remove("d1")
        with self.assertRaisesRegex(minority_report.MinorityError, "transcript sah"):
            minority_report.build_report(raw)

    def test_markdown_includes_open_dissent_and_escaped_title(self):
        raw = fixture()
        raw["positions"][0]["title"] = "## Aksi [tak menurut]"
        path = Path(self.enterContext(TemporaryDirectory())) / "minority.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(minority_report.main([str(path), "--format", "markdown"]), 0)
        text = output.getvalue()
        self.assertIn(r"\#\# Aksi \[tak menurut\]", text)
        self.assertIn("Belum ada tanggapan tercatat.", text)
        self.assertIn("fixture/bounds", text)

    def test_markdown_cites_contested_turn_and_all_objections(self):
        text = minority_report.render_markdown(minority_report.build_report(fixture()))
        self.assertIn("## Klaim yang dipersoalkan", text)
        self.assertIn("a1 — Gunakan dua sumber", text)
        self.assertIn("Sanggahan — b1, d1", text)

    def test_unassigned_output_keeps_transcript_order_and_hash(self):
        raw = fixture()
        report = minority_report.build_report({**raw, "positions": []})
        self.assertEqual([item["turn_id"] for item in report["unassigned_objections"]], ["b1", "d1"])
        self.assertTrue(all(item["source"]["sha256"] == raw["debate"]["sha256"]
                            for item in report["unassigned_objections"]))
        self.assertEqual(report["positions"], [])

    def test_incomplete_debate_cannot_be_called_minority_report_of_decision(self):
        raw = debate_fixture()
        raw.pop("decision")
        with self.assertRaises(minority_report.MinorityError):
            minority_report.build_report({"debate": debate_protocol.replay(raw), "positions": []})

    def test_duplicate_position_labels_are_refused_even_for_disjoint_objections(self):
        raw = fixture()
        raw["positions"].append({**raw["positions"][0], "objections": ["d1"]})
        with self.assertRaisesRegex(minority_report.MinorityError, "ID posisi ganda"):
            minority_report.build_report(raw)

    def test_position_metadata_order_does_not_change_report(self):
        raw = fixture()
        raw["positions"].append({"id": "bounds", "title": "Perlu data", "objections": ["d1"], "alternative": None})
        before = minority_report.build_report(raw)
        raw["positions"].reverse()
        self.assertEqual(minority_report.build_report(raw), before)
