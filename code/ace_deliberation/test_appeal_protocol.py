"""Periksa kebaruan bukti, independensi ulasan, dan putusan asal."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from ace_deliberation import appeal_protocol as appeal


def fixture():
    old = {"source_ref": "fixture/old", "sha256": "a" * 64, "available_at": "2026-11-20T00:00:00Z"}
    new = {"source_ref": "fixture/new", "sha256": "b" * 64, "available_at": "2026-11-21T00:00:00Z"}
    return {"decision": {"id": "v1", "decided_at": "2026-11-20T00:00:00Z", "actor": "author",
                         "source_ref": "fixture/decision", "outcome": "adopt", "evidence": [old]},
            "rule": {"filing_deadline": "2026-11-22T00:00:00Z", "review_deadline": "2026-11-23T00:00:00Z",
                     "eligible_reviewers": ["auditor", "author", "appellant"]},
            "appeal": {"id": "a1", "decision_id": "v1", "appellant": "appellant", "filed_at": "2026-11-21T00:00:00Z",
                       "grounds": "Tambahkan bukti kontrol", "source_ref": "fixture/appeal", "new_evidence": [new]},
            "review": {"appeal_id": "a1", "reviewer": "auditor", "reviewed_at": "2026-11-21T10:00:00Z",
                       "outcome": "remand", "reasons": "Kontrol perlu diperiksa", "basis": ["fixture/new"],
                       "source_ref": "fixture/review"}}


class AppealTests(unittest.TestCase):
    def test_review_remand_retains_original_outcome_and_all_sources(self):
        raw = fixture()
        report = appeal.process_appeal(raw)
        self.assertEqual(report["status"], "reviewed")
        self.assertTrue(report["reconsideration_requested"])
        self.assertEqual(report["original_decision"]["outcome"], "adopt")
        self.assertEqual(report["review"]["basis"], ["fixture/new"])
        self.assertEqual(report["appeal"]["new_evidence"][0]["sha256"], "b" * 64)

    def test_reused_hash_or_ref_cannot_be_filed_as_new_evidence(self):
        for edit in ({"sha256": "a" * 64}, {"source_ref": "fixture/old"},
                     {"available_at": "2026-11-21T01:00:00Z"}):
            raw = fixture()
            raw["appeal"]["new_evidence"][0].update(edit)
            with self.subTest(edit=edit), self.assertRaises(appeal.AppealError):
                appeal.process_appeal(raw)

    def test_reviewers_must_be_authorized_and_distinct(self):
        for name in ("author", "appellant", "unknown"):
            raw = fixture()
            raw["review"]["reviewer"] = name
            with self.subTest(name=name), self.assertRaisesRegex(appeal.AppealError, "independen"):
                appeal.process_appeal(raw)

    def test_boundary_review_is_inclusive_and_evidence_cannot_be_future(self):
        raw = fixture()
        raw["review"]["reviewed_at"] = raw["rule"]["review_deadline"]
        self.assertEqual(appeal.process_appeal(raw)["status"], "reviewed")
        raw["review"]["reviewed_at"] = "2026-11-23T00:00:01Z"
        with self.assertRaises(appeal.AppealError):
            appeal.process_appeal(raw)

    def test_no_review_stays_pending_and_no_appeal_never_accepts_review(self):
        self.assertEqual(appeal.process_appeal({**fixture(), "review": None})["status"], "awaiting_review")
        with self.assertRaises(appeal.AppealError):
            appeal.process_appeal({**fixture(), "appeal": None})
        empty = appeal.process_appeal({**fixture(), "appeal": None, "review": None})
        self.assertEqual(empty["status"], "not_filed")

    def test_cli_dismiss_keeps_request_for_reconsideration_false(self):
        raw = fixture()
        raw["review"]["outcome"] = "dismiss"
        path = Path(self.enterContext(TemporaryDirectory())) / "appeal.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(appeal.main([str(path)]), 0)
        self.assertFalse(json.loads(output.getvalue())["reconsideration_requested"])

    def test_refuses_mismatched_appeal_id_and_unsupported_review_basis(self):
        for change in ({"appeal_id": "foreign"}, {"basis": []}, {"basis": ["fixture/old"]}):
            with self.subTest(change=change), self.assertRaises(appeal.AppealError):
                raw = fixture()
                raw["review"].update(change)
                appeal.process_appeal(raw)

    def test_as_of_marks_expired_review_and_refuses_future_evidence(self):
        raw = fixture()
        late = {**raw, "review": None, "as_of": "2026-11-24T00:00:00Z"}
        self.assertEqual(appeal.process_appeal(late)["status"], "review_expired")
        with self.assertRaisesRegex(appeal.AppealError, "Ulasan belum tersedia"):
            appeal.process_appeal({**raw, "as_of": "2026-11-21T01:00:00Z"})

    def test_closed_filing_window_retains_decision_without_appeal(self):
        raw = {**fixture(), "appeal": None, "review": None, "as_of": "2026-11-22T00:00:01Z"}
        report = appeal.process_appeal(raw)
        self.assertEqual(report["status"], "filing_closed")
        self.assertEqual(report["original_decision"]["id"], "v1")
        self.assertFalse(report["reconsideration_requested"])

    def test_separate_refs_are_required_even_for_simultaneous_filing_and_review(self):
        raw = fixture()
        raw["review"]["source_ref"] = raw["appeal"]["source_ref"]
        with self.assertRaisesRegex(appeal.AppealError, "tersendiri"):
            appeal.process_appeal(raw)
