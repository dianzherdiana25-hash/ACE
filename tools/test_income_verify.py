"""Pastikan tiga berkas bukti menghasilkan verdict sesuai kebijakan WS-2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.income_verify import RESULT_SCHEMA, verify_income


ROLES = ("platform", "withdrawal", "statement")
RECIPIENT = "Penerima Fixture"


def _row(role: str, event_id: str = "payout-sample", **fields) -> dict:
    return {
        "id": event_id, "rail": "kbm_seabank", "provider": "seabank" if role == "statement" else "kbm",
        "ref": f"bukti-{event_id}-{role}", "date": "2026-01-10", "amount_rupiah": 25_000,
        "recipient": RECIPIENT, **fields,
    }


def _verify(**overrides) -> dict:
    records = {role: [_row(role)] for role in ROLES}
    return verify_income(recipient=RECIPIENT, **(records | overrides))


class IncomeVerifyTests(unittest.TestCase):
    def test_full_match_and_report_contract(self):
        result = _verify()
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        self.assertEqual(result["max_lag_days"], 14)
        self.assertEqual(result["events"], [{
            "id": "payout-sample", "rail": "kbm_seabank", "status": "COCOK PENUH",
            "issues": [], "verified_rupiah": 25_000,
            "statement_date": "2026-01-10",
            "amounts_rupiah": dict.fromkeys(ROLES, 25_000),
        }])

    def test_one_nominal_mismatch_partially_matches_and_reports_each_amount(self):
        result = _verify(statement=[_row("statement", amount_rupiah=26_000)])["events"][0]
        self.assertEqual(result["status"], "SEBAGIAN")
        self.assertIn("amount_mismatch:withdrawal:statement", result["issues"])
        self.assertIsNone(result["verified_rupiah"])
        self.assertEqual(result["amounts_rupiah"]["statement"], 26_000)

    def test_three_nominals_differ(self):
        result = _verify(
            withdrawal=[_row("withdrawal", amount_rupiah=24_000)],
            statement=[_row("statement", amount_rupiah=26_000)],
        )["events"][0]
        self.assertEqual(result["status"], "TIDAK COCOK")
        self.assertIsNone(result["verified_rupiah"])

    def test_missing_statement_is_not_zero(self):
        result = _verify(statement=[])["events"][0]
        self.assertEqual(result["status"], "HILANG")
        self.assertEqual(result["issues"], ["missing:statement"])
        self.assertIsNone(result["amounts_rupiah"]["statement"])
        self.assertIsNone(result["verified_rupiah"])
        self.assertIsNone(result["statement_date"])

    def test_statement_only_id_is_reported_and_never_joined_by_amount(self):
        result = _verify(statement=[_row("statement", event_id="payout-other")])["events"]
        self.assertEqual([event["id"] for event in result], ["payout-other", "payout-sample"])
        self.assertEqual(result[0]["issues"], ["missing:platform", "missing:withdrawal"])
        self.assertEqual(result[1]["issues"], ["missing:statement"])

    def test_fastwork_compares_gross_to_net_via_stated_fee(self):
        result = _verify(
            platform=[_row("platform", rail="fastwork_bank", provider="fastwork")],
            withdrawal=[_row("withdrawal", rail="fastwork_bank", provider="fastwork", fee_rupiah=1_250)],
            statement=[_row("statement", rail="fastwork_bank", amount_rupiah=23_750)],
        )["events"][0]
        self.assertEqual((result["status"], result["verified_rupiah"]), ("COCOK PENUH", 23_750))

    def test_rejects_duplicate_role_and_conflicting_rail(self):
        with self.assertRaisesRegex(ValueError, "id ganda atau rail"):
            _verify(platform=[_row("platform"), _row("platform")])
        with self.assertRaisesRegex(ValueError, "id ganda atau rail"):
            _verify(withdrawal=[_row("withdrawal", rail="fastwork_bank")])

    def test_fields_that_could_leak_bank_account_are_rejected(self):
        private = "9876543210123456"
        with self.assertRaisesRegex(ValueError, "field yang tidak sah") as error:
            _verify(statement=[_row("statement", account_number=private)])
        self.assertNotIn(private, str(error.exception))

    def test_cli_reads_three_files_and_does_not_emit_private_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [sys.executable, str(Path(__file__).with_name("income_verify.py"))]
            for role in ROLES:
                path = root / f"{role}.json"
                path.write_text(json.dumps([_row(role)]), encoding="utf-8")
                command.extend([f"--{role}", str(path)])
            recipient_file = root / "recipient.txt"
            recipient_file.write_text(RECIPIENT + "\n", encoding="utf-8")
            command.extend(["--recipient-file", str(recipient_file)])

            def hashes():
                return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()}

            before = hashes()
            proc = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(hashes(), before)
            self.assertEqual(json.loads(proc.stdout)["events"][0]["status"], "COCOK PENUH")
            self.assertNotIn(RECIPIENT, proc.stdout)
            self.assertNotIn("bukti-payout-sample-statement", proc.stdout)


if __name__ == "__main__":
    unittest.main()
