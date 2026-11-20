"""Uji undangan lokal, batas waktu, dan keterikatan testimoni."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import expert_witness


def invitation():
    return {"invitation_id": "i1", "case_id": "case", "topic": "sampling",
            "issued_at": "2026-11-20T00:00:00Z", "deadline": "2026-11-20T02:00:00Z",
            "expert": {"id": "outside-fixture", "topics": ["sampling"], "credential_ref": "fixture/credential",
                       "conflicts": []},
            "questions": [{"id": "bounds", "question": "Apa sekat sampelnya?", "source_ref": "fixture/bounds"}]}


def response(raw=None):
    packet = expert_witness.invite(invitation() if raw is None else raw)
    return {"invitation_sha256": packet["sha256"], "witness_id": "outside-fixture", "question_id": "bounds",
            "received_at": "2026-11-20T02:00:00Z", "status": "answered", "statement": "Satu sumber bukti tersisa",
            "evidence_refs": ["fixture/data"], "testimony_ref": "fixture/testimony"}


def fixture():
    return {"request": invitation(), "testimony": [response()], "as_of": "2026-11-20T02:01:00Z"}


class ExpertWitnessTests(unittest.TestCase):
    def test_complete_inclusive_at_deadline_and_reference_preserved(self):
        result = expert_witness.examine(fixture())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["open_questions"], [])
        event, = result["testimony"]
        self.assertEqual(event["question_ref"], "fixture/bounds")
        self.assertEqual(event["testimony_ref"], "fixture/testimony")
        self.assertEqual(event["evidence_refs"], ["fixture/data"])

    def test_late_testimony_is_retained_but_does_not_complete_request(self):
        raw = fixture()
        raw["testimony"][0]["received_at"] = "2026-11-20T02:00:01Z"
        result = expert_witness.examine(raw)
        self.assertEqual(result["status"], "expired_incomplete")
        self.assertEqual(result["open_questions"], ["bounds"])
        self.assertFalse(result["testimony"][0]["in_window"])

    def test_changed_question_or_witness_never_reuses_old_testimony(self):
        for bad in ("question", "witness"):
            raw = fixture()
            if bad == "question":
                raw["request"]["questions"][0]["question"] = "Apa ukuran baru?"
            else:
                raw["testimony"][0]["witness_id"] = "other"
            with self.subTest(bad=bad), self.assertRaisesRegex(expert_witness.WitnessError, "tidak terikat"):
                expert_witness.examine(raw)

    def test_lack_of_topic_or_declared_conflict_refuses_invitation(self):
        for changes in ({"topics": ["different"]}, {"conflicts": ["sampling"]}):
            raw = invitation()
            raw["expert"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(expert_witness.WitnessError):
                expert_witness.invite(raw)

    def test_abstention_keeps_question_open_and_has_no_false_answer(self):
        raw = fixture()
        raw["as_of"] = raw["request"]["deadline"]
        raw["testimony"][0].update(status="abstained", evidence_refs=[])
        report = expert_witness.examine(raw)
        self.assertEqual(report["status"], "awaiting_testimony")
        self.assertEqual(report["open_questions"], ["bounds"])

    def test_cli_invite_only_matches_request_packet(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "witness.json"
        path.write_text(json.dumps(invitation()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(expert_witness.main([str(path), "--invite-only"]), 0)
        self.assertEqual(json.loads(output.getvalue()), expert_witness.invite(invitation()))

    def test_missing_reference_or_future_testimony_refused(self):
        for updates in ({"received_at": "2026-11-20T03:00:00Z"}, {"evidence_refs": []},
                        {"question_id": "not-asked"}):
            raw = fixture()
            raw["testimony"][0].update(updates)
            with self.subTest(updates=updates), self.assertRaises(expert_witness.WitnessError):
                expert_witness.examine(raw)

    def test_changed_packet_cannot_be_reused_even_if_it_rehashes_itself(self):
        from ace_deliberation.debate_protocol import _sha

        raw = invitation()
        packet = expert_witness.invite(raw)
        self.assertTrue(expert_witness.verify_packet(packet, raw))
        packet["topic"] = "different"
        packet["sha256"] = _sha({key: value for key, value in packet.items() if key != "sha256"})
        self.assertFalse(expert_witness.verify_packet(packet, raw))

    def test_verifier_cli_reports_unsuccessful_request_matching(self):
        raw = invitation()
        packet = expert_witness.invite(raw)
        raw["deadline"] = "2026-11-20T02:05:00Z"
        path = Path(self.enterContext(TemporaryDirectory())) / "verify.json"
        path.write_text(json.dumps({"request": raw, "packet": packet}), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(expert_witness.main([str(path), "--verify-packet"]), 1)
        self.assertEqual(json.loads(output.getvalue()), {"valid": False})

    def test_multiple_questions_report_coverage_in_stable_order(self):
        raw = fixture()
        raw["request"]["questions"].insert(0, {"id": "extra", "question": "Apa data pembanding?",
                                                "source_ref": "fixture/extra"})
        raw["testimony"] = [response(raw["request"])]
        report = expert_witness.examine(raw)
        self.assertEqual(report["open_questions"], ["extra"])
        self.assertEqual(report["status"], "expired_incomplete")
        raw["request"]["questions"].reverse()
        self.assertEqual(expert_witness.examine(raw), report)

    def test_duplicate_evidence_and_answer_are_never_used_as_multiple_testimony(self):
        raw = fixture()
        raw["testimony"].append({**raw["testimony"][0], "testimony_ref": "fixture/replayed"})
        with self.assertRaises(expert_witness.WitnessError):
            expert_witness.examine(raw)

    def test_blank_roster_evidence_requires_valid_source_and_no_hidden_authorship(self):
        raw = invitation()
        raw["expert"]["credential_ref"] = ""
        with self.assertRaises(expert_witness.WitnessError):
            expert_witness.invite(raw)

    def test_invalid_request_does_not_pass_packet_verifier(self):
        self.assertFalse(expert_witness.verify_packet({}, {}))
