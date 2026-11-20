"""Uji putusan sementara, review independen, dan keluaran saat tenggat lewat."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import emergency_decision as emergency


def vote(name, which="ratify", at="2026-11-20T00:10:00Z"):
    digest = emergency.review_emergency(fixture())["proposal_sha256"]
    return {"decision_id": "p1", "proposal_sha256": digest, "reviewer": name, "vote": which, "at": at,
            "source_ref": f"fixture/reviews/{name}"}


def fixture():
    return {
        "proposal": {"id": "p1", "proposed_by": "author", "proposed_at": "2026-11-20T00:00:00Z", "severity": 4,
                     "evidence_refs": ["fixture/incident"], "undo_ref": "fixture/rollback",
                     "description": "Tunda operasi internal fixture", "reversible": True, "external_effects": False},
        "policy": {"min_severity": 3, "review_window_seconds": 1_800,
                   "reviews_needed": 2, "reviewers": ["author", "a", "b", "c"]},
        "as_of": "2026-11-20T00:20:00Z", "reviews": [],
    }


class EmergencyTests(unittest.TestCase):
    def test_provisional_then_two_independent_votes_at_or_before_deadline(self):
        raw = fixture()
        provisional = emergency.review_emergency(raw)
        self.assertEqual(provisional["status"], "provisional")
        self.assertEqual(provisional["possible_yes"], 3)
        self.assertFalse(provisional["rollback_due"])
        raw["as_of"] = "2026-11-20T00:31:00Z"
        raw["reviews"] = [vote("b", at="2026-11-20T00:30:00Z"), vote("a")]
        result = emergency.review_emergency(raw)
        self.assertEqual(result["status"], "ratified")
        self.assertEqual([row["reviewer"] for row in result["reviews"]], ["a", "b"])

    def test_late_approval_is_reported_but_does_not_prevent_expiration(self):
        raw = fixture()
        raw["as_of"] = "2026-11-20T00:32:00Z"
        raw["reviews"] = [vote("a"), vote("b", at="2026-11-20T00:30:01Z")]
        result = emergency.review_emergency(raw)
        self.assertEqual(result["status"], "expired")
        self.assertTrue(result["rollback_due"])
        self.assertEqual(result["yes_count"], 1)
        self.assertFalse(result["reviews"][-1]["counted"])
        self.assertEqual(result["undo_ref"], "fixture/rollback")

    def test_two_nonapprovals_make_threshold_unreachable_early(self):
        raw = {**fixture(), "reviews": [vote("a", "revoke"), vote("b", "abstain")]}
        result = emergency.review_emergency(raw)
        self.assertEqual(result["status"], "revoked")
        self.assertEqual(result["possible_yes"], 1)
        self.assertTrue(result["rollback_due"])

    def test_scope_and_independence_are_checked_even_with_urgent_claim(self):
        raw = fixture()
        raw["proposal"].update(reversible=False, external_effects=True, severity=2)
        raw["policy"]["reviews_needed"] = 4
        result = emergency.review_emergency(raw)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reasons"],
                         ["insufficient_urgency", "not_reversible", "external_effects", "insufficient_independent_reviewers"])

    def test_rejects_self_review_duplicate_vote_and_backdated_review(self):
        for ballots in ([vote("author")], [vote("a"), vote("a", "revoke")],
                        [vote("a", at="2026-11-19T23:59:59Z")]):
            with self.subTest(ballots=ballots), self.assertRaises(emergency.EmergencyError):
                emergency.review_emergency({**fixture(), "reviews": ballots})

    def test_cli_refuses_nonratifiable_scope(self):
        raw = fixture()
        raw["proposal"]["external_effects"] = True
        path = Path(self.enterContext(TemporaryDirectory())) / "emergency.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(emergency.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "refused")

    def test_vote_is_bound_to_proposal_and_review_policy(self):
        for section, edits in (("proposal", {"description": "Langkah internal lain"}),
                               ("policy", {"reviews_needed": 1})):
            raw = {**fixture(), "reviews": [vote("a")]}
            raw[section].update(edits)
            with self.subTest(section=section), self.assertRaisesRegex(emergency.EmergencyError, "versi usulan"):
                emergency.review_emergency(raw)

    def test_ratification_receipt_stamps_first_time_threshold_was_met(self):
        raw = {**fixture(), "reviews": [vote("c", at="2026-11-20T00:19:00Z"),
                                        vote("b", at="2026-11-20T00:12:00Z"), vote("a")]}
        report = emergency.review_emergency(raw)
        self.assertEqual(report["ratified_at"], "2026-11-20T00:12:00+00:00")
        self.assertFalse(report["rollback_due"])
        self.assertEqual(report, emergency.review_emergency({**raw, "reviews": raw["reviews"][::-1]}))

    def test_hash_remains_stable_across_review_time_and_catalog_order(self):
        raw = fixture()
        before = emergency.review_emergency(raw)
        raw["as_of"] = "2026-11-20T00:21:00Z"
        raw["policy"]["reviewers"].reverse()
        self.assertEqual(before["proposal_sha256"], emergency.review_emergency(raw)["proposal_sha256"])

    def test_exact_deadline_remains_open_and_expiry_occurs_one_second_later(self):
        raw = {**fixture(), "as_of": "2026-11-20T00:30:00Z"}
        self.assertEqual(emergency.review_emergency(raw)["status"], "provisional")
        raw["as_of"] = "2026-11-20T00:30:01Z"
        self.assertEqual(emergency.review_emergency(raw)["status"], "expired")

    def test_uncertain_effects_type_cannot_be_used_as_false(self):
        raw = fixture()
        raw["proposal"]["external_effects"] = None
        with self.assertRaises(emergency.EmergencyError):
            emergency.review_emergency(raw)

    def test_invalid_future_review_cannot_supply_missing_quorum(self):
        raw = {**fixture(), "reviews": [vote("a", at="2026-11-20T00:20:01Z")]}
        with self.assertRaises(emergency.EmergencyError):
            emergency.review_emergency(raw)

    def test_refused_case_never_reports_rollback_for_an_unissued_action(self):
        raw = fixture()
        raw["proposal"]["severity"] = 1
        self.assertFalse(emergency.review_emergency(raw)["rollback_due"])
