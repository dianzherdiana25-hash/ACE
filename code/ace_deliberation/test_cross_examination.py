"""Uji urutan, konsesi, dan rujukan bukti tanya silang."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import cross_examination as cross


def claim():
    return {"id": "claim-1", "claimant": "author", "description": "Hasil cukup untuk cakupan A",
            "source_ref": "fixture/claim"}


def question(identifier="q1", **edits):
    return {"id": identifier, "kind": "question", "actor": "reviewer", "text": "Apa batas sampel?",
            "source_ref": f"fixture/{identifier}", "claim_id": "claim-1", "category": "measurement", **edits}


def answer(identifier="a1", **edits):
    return {"id": identifier, "kind": "response", "actor": "author", "text": "Sampel berasal dari kelompok A",
            "source_ref": f"fixture/{identifier}", "question_id": "q1", "disposition": "answered",
            "evidence_refs": ["fixture/sample"], **edits}


class CrossExaminationTests(unittest.TestCase):
    def test_defer_then_answer_retains_provenance_and_removes_unresolved(self):
        events = [question(), answer("a0", disposition="deferred", evidence_refs=[]), answer()]
        report = cross.examine({"claims": [claim()], "events": events})
        row, = report["questions"]
        self.assertEqual((row["question_id"], row["status"]), ("q1", "answered"))
        self.assertEqual(row["response_refs"], ["fixture/a0", "fixture/a1"])
        self.assertEqual(row["evidence_refs"], ["fixture/sample"])
        self.assertEqual(report["unresolved"], [])

    def test_concession_and_open_question_remain_distinct(self):
        raw = {"claims": [claim()], "events": [
            question(), question("q2", category="scope"), question("q3", category="provenance"),
            answer(disposition="conceded", evidence_refs=[]),
            answer("a2", question_id="q2", disposition="deferred", evidence_refs=[]),
        ]}
        report = cross.examine(raw)
        self.assertEqual(report["concessions"], ["q1"])
        self.assertEqual(report["unresolved"], ["q2", "q3"])
        self.assertEqual([row["status"] for row in report["questions"]],
                         ["conceded", "deferred", "awaiting"])

    def test_wrong_actor_unknown_claim_or_unsourced_response_does_not_mutate_session(self):
        session = cross.CrossExamination([claim()])
        with self.assertRaises(cross.ExaminationError):
            session.submit(answer())
        session.submit(question())
        expected = session.report()
        for bad in (answer(actor="intruder"), answer(evidence_refs=[]), question("q2", claim_id="x"),
                    question("q3", actor="author"), answer("a2", source_ref="fixture/q1")):
            with self.subTest(bad=bad), self.assertRaises(cross.ExaminationError):
                session.submit(bad)
            self.assertEqual(session.report(), expected)

    def test_terminal_response_cannot_be_replaced(self):
        session = cross.CrossExamination([claim()])
        session.submit(question())
        session.submit(answer())
        before = session.report()
        with self.assertRaisesRegex(cross.ExaminationError, "terminal"):
            session.submit(answer("a2", disposition="conceded"))
        self.assertEqual(session.report(), before)

    def test_export_does_not_leak_mutable_references_to_session(self):
        session = cross.CrossExamination([claim()])
        session.submit(question())
        session.submit(answer())
        snapshots = session.report(), session.report()
        snapshots[0]["events"][1]["evidence_refs"].clear()
        self.assertEqual(session.report(), snapshots[1])

    def test_cli_report_matches_replay(self):
        raw = {"claims": [claim()], "events": [question()]}
        path = Path(self.enterContext(TemporaryDirectory())) / "case.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(cross.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), cross.examine(raw))

    def test_plan_rejects_noncanonical_unknown_categories_and_duplicate_ids(self):
        for raw in ({"claims": [claim(), claim()], "events": []},
                    {"claims": [claim()], "events": [question(category="novel")]},
                    {"claims": [claim()], "events": [question(), question()]}):
            with self.subTest(raw=raw), self.assertRaises(cross.ExaminationError):
                cross.examine(raw)

    def test_unresolved_questions_are_partitioned_by_their_claims(self):
        second = {**claim(), "id": "claim-2", "source_ref": "fixture/claim-2"}
        raw = {"claims": [claim(), second], "events": [
            question(), question("q2", claim_id="claim-2"), answer(),
        ]}
        first, second = cross.examine(raw)["claims"]
        self.assertEqual(first["question_counts"], {"awaiting": 0, "deferred": 0, "answered": 1, "conceded": 0})
        self.assertEqual(second["question_counts"], {"awaiting": 1, "deferred": 0, "answered": 0, "conceded": 0})

    def test_rejects_question_source_reusing_the_underlying_claim(self):
        with self.assertRaisesRegex(cross.ExaminationError, "rujukan event ganda"):
            cross.examine({"claims": [claim()], "events": [question(source_ref="fixture/claim")]})
