"""Verifier sandbox fiktif untuk idempotency, hold, refund, dan saldo."""
import unittest

from ace_software_factory import payment_sandbox_builder
from ace_software_factory._contracts import ContractError, identity


def plan():
    allow = {"status": "accepted", "reason": None}
    capture = {"id": "first", "kind": "capture", "authorization": "hold", "units": 8}
    return {"schema": "ace.factory-payment-sandbox.v1", "source_ref": "fixture/billing",
            "fixture_accounts": [{"id": "tester", "units": 20}],
            "events": [{"id": "hold", "kind": "authorize", "account": "tester", "units": 12},
                       capture, dict(capture), {**capture, "units": 2},
                       {"id": "back", "kind": "refund", "authorization": "hold", "units": 1},
                       {"id": "close", "kind": "void", "authorization": "hold"},
                       {"id": "after", "kind": "capture", "authorization": "hold", "units": 1}],
            "expected_receipts": [allow, allow, {"status": "duplicate", "reason": None},
                                  {"status": "rejected", "reason": "conflicting_event_id"}, allow, allow,
                                  {"status": "rejected", "reason": "capture_exceeds_hold"}]}


class SandboxTests(unittest.TestCase):
    def test_partial_capture_refund_and_void_conserve_fixture_units(self):
        raw = plan()
        report = payment_sandbox_builder.simulate(raw, identity(raw))
        self.assertEqual(report["status"], "verified_fixture")
        self.assertEqual(report["reconciliation"]["tester"], {"initial_units": 20, "available_units": 13,
                                                               "held_units": 0, "net_captured_units": 7, "conserved": True})
        self.assertEqual(report["receipts"][2]["original_line"], 2)
        self.assertEqual(report["receipts_sha256"], identity(report["receipts"]))

    def test_refuses_missing_assertions_and_reports_mismatch(self):
        raw = plan()
        raw["expected_receipts"].pop()
        with self.assertRaisesRegex(ContractError, "Setiap event"):
            payment_sandbox_builder.simulate(raw, identity(raw))
        raw["expected_receipts"].append({"status": "accepted", "reason": None})
        report = payment_sandbox_builder.simulate(raw, identity(raw))
        self.assertEqual(report["status"], "failed_fixture")
        self.assertEqual(report["differences"][0]["line"], 7)
