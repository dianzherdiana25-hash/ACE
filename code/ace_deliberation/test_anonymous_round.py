"""Uji token terikat sesi, kerahasiaan awal, dan transcript setelah kuorum."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import anonymous_round as ballots


def fixture():
    plan = {"round_id": "r1", "members": ["member-x", "member-y", "member-z", "member-w"],
            "options": ["defer", "adopt"], "allowed_refs": ["fixture/second", "fixture/first"], "quorum": 3}
    return {"plan": plan, "votes": [
        {"member": member, "ballot": {"option": choice, "confidence": 75, "refs": ["fixture/first"]}}
        for member, choice in zip(plan["members"][:3], ("defer", "adopt", "adopt"))
    ]}


class AnonymousTests(unittest.TestCase):
    def test_public_bytes_have_no_roster_token_or_arrival_order(self):
        raw = fixture()
        first = ballots.simulate(raw)
        self.assertEqual(ballots.simulate({**raw, "votes": raw["votes"][::-1]}), first)
        text = json.dumps(first)
        self.assertTrue(all(name not in text for name in raw["plan"]["members"]))
        self.assertEqual(set(first["ballots"][0]), {"option", "confidence", "refs"})
        self.assertEqual(ballots.tally(first), {"adopt": 2, "defer": 1})

    def test_duplicate_token_and_cross_round_token_are_refused(self):
        raw = fixture()
        key = bytes(range(32))
        a = ballots.AnonymousRound(raw["plan"], key=key)
        b = ballots.AnonymousRound({**raw["plan"], "round_id": "r2"}, key=key)
        credential = a.private_token("member-x")
        ballot = raw["votes"][0]["ballot"]
        a.cast(credential, ballot)
        for session in (a, b):
            with self.subTest(session=session), self.assertRaises(ballots.BallotError):
                session.cast(credential, ballot)
        self.assertEqual(b.progress(), {"phase": "collecting", "quorum_reached": False})

    def test_small_round_cannot_release_any_votes_then_recovers(self):
        raw = fixture()
        session = ballots.AnonymousRound(raw["plan"])
        with self.assertRaisesRegex(ballots.BallotError, "Kuorum"):
            session.close()
        for row in raw["votes"]:
            session.cast(session.private_token(row["member"]), row["ballot"])
        self.assertTrue(session.progress()["quorum_reached"])
        token = session.private_token(raw["votes"][0]["member"])
        report = session.close()
        self.assertFalse(token in json.dumps(report))
        self.assertEqual(session.close(), report)
        with self.assertRaises(ballots.BallotError):
            session.private_token("member-x")

    def test_untrusted_vote_cannot_smuggle_free_text_or_spend_token_on_failure(self):
        raw = fixture()
        session = ballots.AnonymousRound(raw["plan"])
        token = session.private_token("member-x")
        valid = raw["votes"][0]["ballot"]
        for updates in ({"message": "member-x"}, {"refs": ["member-x"]}, {"confidence": True}):
            with self.subTest(updates=updates), self.assertRaises(ballots.BallotError):
                session.cast(token, {**valid, **updates})
        self.assertTrue(session.cast(token, valid))

    def test_tamper_detection_and_rejection_of_identifying_fields(self):
        raw = ballots.simulate(fixture())
        for patch in ({"option": "adopt"}, {"member": "member-x"}):
            changed = deepcopy(raw)
            changed["ballots"][-1].update(patch)
            if changed == raw:
                changed["ballots"][-1]["confidence"] -= 1
            self.assertFalse(ballots.verify_public(changed))

    def test_public_label_collision_is_refused(self):
        raw = fixture()
        plan = {**raw["plan"], "allowed_refs": ["member-x"]}
        with self.assertRaisesRegex(ballots.BallotError, "Label publik"):
            ballots.AnonymousRound(plan)

    def test_cli_verifies_export_with_fixture_round(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "anon.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as report:
            self.assertEqual(ballots.main([str(path)]), 0)
        path.write_text(report.getvalue(), encoding="utf-8")
        with redirect_stdout(StringIO()) as validation:
            self.assertEqual(ballots.main([str(path), "--verify"]), 0)
        self.assertEqual(json.loads(validation.getvalue()), {"valid": True})
