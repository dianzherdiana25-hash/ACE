"""Verifier kapasitas, izin fixture, dan undo dengan hash sebelumnya."""
import unittest

from ace_web_operator import booking_agent
from ace_web_operator._contracts import ContractError,identity


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.cal={"schema":"ace.web.booking-fixture.v1","source_ref":"fixture/calendar",
                  "slots":[{"id":"window","start":"2026-01-02T00:00:00Z","end":"2026-01-02T01:00:00Z",
                            "cancel_until":"2026-01-01T04:00:00Z","capacity":3,"source_ref":"fixture/schedule"}],
                  "reservations":[{"id":"existing","slot":"window","places":1}]}
        self.plan={"schema":"ace.web.booking-plan.v1","id":"new_book","source_ref":"fixture/request",
                   "snapshot_sha256":identity(self.cal),"approval_ref":"fixture/approval",
                   "now":"2026-01-01T00:00:00Z","earliest":"2026-01-01T23:00:00Z","latest":"2026-01-02T02:00:00Z",
                   "minimum_cancel_seconds":3600,"places":2}

    def apply(self):
        return booking_agent.apply_fixture(self.plan,identity(self.plan),self.cal)

    def test_reservation_simulation_and_undo_keeps_source_snapshot(self):
        data,receipt=self.apply()
        self.assertEqual(receipt["status"],"simulated_reserved")
        self.assertEqual(len(data["reservations"]),2)
        self.assertEqual(len(self.cal["reservations"]),1)
        restored,verdict=booking_agent.undo_fixture(data,receipt["undo"],"2026-01-01T03:59:59Z")
        self.assertEqual(restored,self.cal)
        self.assertEqual(verdict["status"],"simulated_cancelled")
        with self.assertRaisesRegex(ContractError,"lewat"):
            booking_agent.undo_fixture(data,receipt["undo"],"2026-01-01T04:00:01Z")

    def test_without_consent_or_enough_capacity_returns_no_data(self):
        self.plan["approval_ref"]=None
        data,result=self.apply()
        self.assertIsNone(data)
        self.assertEqual(result["reason"],"approval_missing")
        self.plan["approval_ref"]="fixture/approval"
        self.plan["places"]=3
        self.assertEqual(self.apply()[1]["reason"],"no_cancellable_capacity")
