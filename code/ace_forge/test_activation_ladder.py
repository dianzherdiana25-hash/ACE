"""Verifier rantai persetujuan dengan artefak, bukti, dan peran terikat."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import activation_ladder as model
from ace_forge._forge_io import canonical, identity


TARGET = "a"*64
INITIAL = "b"*64
SECOND = "c"*64
LAST = "d"*64


def vote(stage, role, sequence, evidence, **changed):
    fields = {"stage": stage, "role": role, "at": f"2026-11-21T00:{sequence:02}:00Z",
              "artifact_sha256": TARGET, "evidence_sha256": evidence, "decision": "approve",
              "receipt_ref": f"fixture/approval/{sequence}"}
    return {**fields, **changed}


def fixture():
    plan = {"policy_ref": "fixture/activation_policy", "artifact_sha256": TARGET, "stages": [
        {"stage": "smoke", "roles": ["runner"], "evidence_sha256": INITIAL},
        {"stage": "heldout", "roles": ["reviewer", "guard"], "evidence_sha256": SECOND},
        {"stage": "final", "roles": ["operator"], "evidence_sha256": LAST},
    ]}
    ledger = {"ledger_ref": "fixture/activation_ledger", "events": [
        vote("smoke", "runner", 1, INITIAL), vote("heldout", "reviewer", 2, SECOND),
        vote("heldout", "guard", 3, SECOND), vote("final", "operator", 4, LAST),
    ]}
    return plan, ledger


def evaluate(plan, ledger):
    return model.evaluate(plan, ledger, identity(plan), identity(ledger))


class LadderTests(unittest.TestCase):
    def test_all_explicit_roles_approve_each_stage_in_order(self):
        raw, ledger = fixture()
        result = evaluate(raw, ledger)
        self.assertEqual(result["status"], "approvals_complete")
        self.assertEqual(result["artifact_sha256"], TARGET)
        self.assertEqual(result["approved_stages"], 3)
        self.assertIsNone(result["pending_stage"])
        self.assertEqual([item["status"] for item in result["stages"]], ["approved"]*3)
        middle = result["stages"][1]
        self.assertEqual(middle["votes"][0]["role"], "guard")
        self.assertEqual(middle["votes"][1]["receipt_ref"], "fixture/approval/2")
        self.assertEqual(middle["missing_roles"], [])
        self.assertEqual(middle["evidence_sha256"], SECOND)
        self.assertEqual(result["ledger_sha256"], identity(ledger))

    def test_each_prefix_leaves_exact_pending_stage_and_missing_roles(self):
        cases = [(0, "smoke", ["runner"]), (1, "heldout", ["guard", "reviewer"]),
                 (2, "heldout", ["guard"]), (3, "final", ["operator"])]
        for count, stage, missing in cases:
            raw, ledger = fixture()
            ledger["events"] = ledger["events"][:count]
            with self.subTest(count=count):
                result = evaluate(raw, ledger)
                self.assertEqual(result["status"], "pending")
                self.assertEqual(result["pending_stage"], stage)
                pending = result["stages"][result["approved_stages"]]
                self.assertEqual(pending["missing_roles"], missing)
                self.assertEqual(pending["status"], "collecting" if count == 2 else "waiting")

    def test_single_rejection_is_terminal_even_if_another_role_approved(self):
        raw, ledger = fixture()
        ledger["events"].pop()
        ledger["events"][-1]["decision"] = "reject"
        result = evaluate(raw, ledger)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["approved_stages"], 1)
        self.assertIsNone(result["pending_stage"])
        self.assertEqual(result["stages"][1]["status"], "rejected")
        self.assertEqual(result["stages"][2]["status"], "waiting")
        self.assertEqual(result["stages"][1]["votes"][0]["decision"], "reject")
        ledger["events"].append(vote("final", "operator", 4, LAST))
        with self.assertRaisesRegex(model.InputError, "terminal"):
            evaluate(raw, ledger)

    def test_receipt_after_last_approval_always_rejected(self):
        raw, ledger = fixture()
        ledger["events"].append(vote("final", "operator", 5, LAST))
        with self.assertRaisesRegex(model.InputError, "terminal"):
            evaluate(raw, ledger)

    def test_cannot_skip_level_or_implicitly_satisfy_required_role(self):
        raw, ledger = fixture()
        ledger["events"].pop(1)
        with self.assertRaisesRegex(model.InputError, "melompati tahap"):
            evaluate(raw, ledger)
        raw, ledger = fixture()
        ledger["events"][2]["role"] = "reviewer"
        with self.assertRaisesRegex(model.InputError, "peran"):
            evaluate(raw, ledger)
        ledger["events"][2]["role"] = "external"
        with self.assertRaisesRegex(model.InputError, "peran"):
            evaluate(raw, ledger)

    def test_evidence_and_artifact_hashes_are_checked_per_vote(self):
        for changes, message in (({"evidence_sha256": INITIAL}, "bukti"),
                                 ({"artifact_sha256": INITIAL}, "artefak"),
                                 ({"decision": None}, "putusan")):
            raw, ledger = fixture()
            ledger["events"][2].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(model.InputError, message):
                evaluate(raw, ledger)

    def test_chronology_accepts_same_instant_and_rejects_go_back(self):
        raw, ledger = fixture()
        ledger["events"][1]["at"] = "2026-11-21T07:01:00+07:00"
        result = evaluate(raw, ledger)
        self.assertEqual(result["stages"][1]["votes"][1]["at"], "2026-11-21T00:01:00+00:00")
        ledger["events"][1]["at"] = "2026-11-21T07:00:59+07:00"
        with self.assertRaisesRegex(model.InputError, "mundur"):
            evaluate(raw, ledger)

    def test_same_receipt_cannot_cover_different_operator_slots(self):
        raw, ledger = fixture()
        ledger["events"][1]["receipt_ref"] = ledger["events"][0]["receipt_ref"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            evaluate(raw, ledger)

    def test_policy_and_ledger_anchors_detect_independent_edits(self):
        policy, ledger = fixture()
        p, l = identity(policy), identity(ledger)
        policy["policy_ref"] += "-edited"
        with self.assertRaisesRegex(model.InputError, "Kebijakan"):
            model.evaluate(policy, ledger, p, l)
        ledger["events"].pop()
        with self.assertRaisesRegex(model.InputError, "Ledger"):
            model.evaluate(policy, ledger, identity(policy), l)

    def test_invalid_policy_closes_before_loading_events(self):
        for stages in ([], [{"stage": "s", "roles": [], "evidence_sha256": INITIAL}],
                       [{"stage": "s", "roles": ["r", "r"], "evidence_sha256": INITIAL}]):
            raw, ledger = fixture()
            raw["stages"] = stages
            with self.subTest(stages=stages), self.assertRaises(model.InputError):
                evaluate(raw, ledger)
        raw, ledger = fixture()
        raw["stages"][1]["stage"] = raw["stages"][0]["stage"]
        with self.assertRaisesRegex(model.InputError, "ganda"):
            evaluate(raw, ledger)

    def test_cli_reports_pending_distinct_from_bad_payload(self):
        raw, ledger = fixture()
        root = Path(self.enterContext(TemporaryDirectory()))
        policy, events = root / "policy", root / "events"
        policy.write_bytes(canonical(raw))
        for rc in (0, 1):
            if rc:
                ledger["events"].pop()
            events.write_bytes(canonical(ledger))
            args = [str(policy), str(events), "--expect-policy-sha256", identity(raw),
                    "--expect-ledger-sha256", identity(ledger)]
            with self.subTest(rc=rc), redirect_stdout(StringIO()) as out:
                self.assertEqual(model.main(args), rc)
            self.assertEqual(json.loads(out.getvalue()), evaluate(raw, ledger))
            self.assertEqual(policy.read_bytes(), canonical(raw))
            self.assertEqual(events.read_bytes(), canonical(ledger))
        events.write_text("bad")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as failure:
            model.main(args)
        self.assertEqual(failure.exception.code, 2)

    def test_same_receipt_order_replays_with_no_canonical_input_change(self):
        policy, source = fixture()
        original = [canonical(policy), canonical(source)]
        first = evaluate(policy, source)
        self.assertEqual(first, evaluate(policy, source))
        self.assertEqual([canonical(policy), canonical(source)], original)
        self.assertEqual(first["stages"][0]["votes"][0]["decision"], "approve")
        self.assertEqual(first["stages"][2]["votes"][0]["receipt_ref"], "fixture/approval/4")

    def test_roles_inside_same_stage_can_be_ordered_independently(self):
        raw, ledger = fixture()
        old = evaluate(raw, ledger)
        first, second = ledger["events"][1:3]
        first["role"], second["role"] = second["role"], first["role"]
        new = evaluate(raw, ledger)
        self.assertEqual(new["status"], old["status"])
        self.assertEqual(new["stages"][1]["votes"][0]["receipt_ref"], "fixture/approval/2")
        self.assertNotEqual(new["ledger_sha256"], old["ledger_sha256"])
