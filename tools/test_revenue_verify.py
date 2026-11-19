"""Fixture sintetis verifikasi pendapatan WS-2."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.revenue_verify import INPUT_SCHEMA, verify_revenue


RECIPIENT = "Penerima Fixture"


def event(rail="kbm_seabank", *, event_id="fixture-one", amount=15_000, fee=0):
    record = {"id": event_id, "rail": rail}
    provider, bank = {
        "kbm_seabank": ("kbm", "seabank"),
        "fastwork_bank": ("fastwork", "bank"),
        "gopay_qris": ("qris", "gopay"),
    }[rail]
    for role, day in [("platform", "2026-01-31"), ("withdrawal", "2026-02-02"),
                      ("statement", "2026-02-16")]:
        record[role] = {"ref": f"{event_id}-{role}", "amount_rupiah": amount, "date": day,
                        "provider": bank if role == "statement" else provider}
    record["statement"]["recipient"] = RECIPIENT
    if rail == "fastwork_bank":
        record["withdrawal"]["fee_rupiah"] = fee
        record["statement"]["amount_rupiah"] -= fee
    return record


def verify(*events, lag=14):
    return verify_revenue({"schema": INPUT_SCHEMA, "events": list(events)},
                          recipient=RECIPIENT, max_lag_days=lag)


class RevenueVerifyTests(unittest.TestCase):
    def test_full_match_per_rail_including_kbm_threshold_and_explicit_fastwork_zero(self):
        for rail in ("kbm_seabank", "fastwork_bank", "gopay_qris"):
            with self.subTest(rail=rail):
                row, = verify(event(rail))["events"]
                self.assertEqual((row["status"], row["verified_rupiah"], row["issues"]),
                                 ("COCOK PENUH", 15_000, []))

    def test_fastwork_uses_recorded_fee_and_verifies_net_only(self):
        record = event("fastwork_bank", fee=3271)
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "COCOK PENUH")
        self.assertEqual(row["verified_rupiah"], 11_729)
        record["withdrawal"]["fee_rupiah"] = 0
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "SEBAGIAN")
        self.assertIn("unmatched:statement", row["issues"])
        self.assertIsNone(row["verified_rupiah"])

    def test_missing_leg_or_fee(self):
        for role in ("platform", "withdrawal", "statement"):
            with self.subTest(role=role):
                record = event()
                del record[role]
                row, = verify(record)["events"]
                self.assertEqual(row["status"], "HILANG")
                self.assertEqual(row["issues"], [f"missing:{role}"])
                self.assertIsNone(row["verified_rupiah"])
        record = event("fastwork_bank", fee=3271)
        del record["withdrawal"]["fee_rupiah"]
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "HILANG")
        self.assertIn("missing:withdrawal.fee_rupiah", row["issues"])

    def test_unknown_rail_even_without_legs(self):
        row, = verify({"id": "unknown-fixture", "rail": "Facebook"})["events"]
        self.assertEqual(row["status"], "REL TAK TERDAFTAR")
        self.assertIsNone(row["verified_rupiah"])

    def test_lag_inclusive_and_configurable(self):
        record = event()
        self.assertEqual(verify(record)["events"][0]["status"], "COCOK PENUH")
        record["statement"]["date"] = "2026-02-17"
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "SEBAGIAN")
        self.assertIn("date_lag:withdrawal:statement", row["issues"])
        self.assertIsNone(row["verified_rupiah"])
        self.assertEqual(verify(record, lag=15)["events"][0]["status"], "COCOK PENUH")

    def test_order_and_recipient_mismatches(self):
        record = event()
        record["platform"]["date"] = "2026-02-19"
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "SEBAGIAN")
        self.assertIn("unmatched:platform", row["issues"])
        record["statement"]["recipient"] = "Nama Lain Fixture"
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "TIDAK COCOK")
        self.assertIn("recipient_mismatch:statement", row["issues"])
        self.assertIsNone(row["verified_rupiah"])

    def test_kbm_below_minimum(self):
        row, = verify(event(amount=14_999))["events"]
        self.assertEqual(row["status"], "TIDAK COCOK")
        self.assertIn("below_kbm_minimum:withdrawal", row["issues"])
        self.assertIsNone(row["verified_rupiah"])

    def test_wrong_statement_provider_is_unverified(self):
        record = event()
        record["statement"]["provider"] = "gopay"
        row, = verify(record)["events"]
        self.assertEqual(row["status"], "SEBAGIAN")
        self.assertIn("provider_mismatch:statement", row["issues"])
        self.assertIsNone(row["verified_rupiah"])

    def test_reject_duplicate_events_and_reused_proof_across_rails(self):
        original = event()
        with self.assertRaisesRegex(ValueError, "ID peristiwa tidak sah atau ganda"):
            verify(original, original)
        second = event("gopay_qris", event_id="fixture-two")
        second["statement"]["ref"] = original["statement"]["ref"]
        with self.assertRaisesRegex(ValueError, "Ref bukti statement dipakai"):
            verify(original, second)

    def test_reject_invalid_evidence_fields_without_echoing_input(self):
        for fields in ({"date": "2026-02-30"}, {"date": "20260216"}, {"amount_rupiah": True},
                       {"amount_rupiah": 15_000.0}, {"account": "private-fixture"}):
            with self.subTest(fields=fields):
                record = event()
                record["statement"].update(fields)
                with self.assertRaisesRegex(ValueError, r"Peristiwa #1") as result:
                    verify(record)
                self.assertNotIn("private-fixture", str(result.exception))

    def test_cli_reads_locally_and_does_not_echo_name_or_refs(self):
        script = Path(__file__).with_name("revenue_verify.py")
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence, name = root / "events.json", root / "name.txt"
            source = json.dumps({"schema": INPUT_SCHEMA, "events": [event()]})
            evidence.write_text(source, encoding="utf-8")
            name.write_text(RECIPIENT + "\n", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(script), str(evidence),
                                   "--recipient-file", str(name), "--max-lag-days", "13"],
                                  check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(proc.stdout)["events"][0]["status"], "SEBAGIAN")
            self.assertNotIn(RECIPIENT, proc.stdout)
            self.assertNotIn("fixture-one-statement", proc.stdout)
            self.assertEqual(evidence.read_text(encoding="utf-8"), source)
            self.assertEqual(list(sorted(root.iterdir())), [evidence, name])


if __name__ == "__main__":
    unittest.main()
