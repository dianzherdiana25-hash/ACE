"""Unit & adversarial integration tests untuk tools/ws2_fixture_harness.py (H1)."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import ws2_fixture_harness as h1


class TestWs2MultiRailIntegration(unittest.TestCase):
    def test_01_full_reference_fixture_suite_covers_all_rails_and_statuses(self) -> None:
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
            report = h1.run_fixture_suite()
        self.assertTrue(report["all_passed"])
        self.assertEqual(report["total_fixtures"], 8)
        self.assertEqual(report["passed_fixtures"], 8)
        self.assertEqual(
            report["status_counts"],
            {
                "COCOK PENUH": 3,
                "HILANG": 2,
                "REL TAK TERDAFTAR": 1,
                "SEBAGIAN": 1,
                "TIDAK COCOK": 1,
            },
        )

    def test_02_fastwork_net_fee_vs_zero_fee_mismatch_and_lag_override(self) -> None:
        bundle = h1.build_reference_fixtures()
        events = [dict(e) for e in bundle["evidence_payload"]["events"] if e["id"] == "kbm-lag-exceeded"]
        # 18 hari lag dengan max_lag_days=14 -> SEBAGIAN; max_lag_days=18 -> COCOK PENUH
        r14 = h1.evaluate_evidence_offline({"schema": h1.EVIDENCE_SCHEMA, "events": events}, recipient=bundle["recipient"], max_lag_days=14)
        self.assertEqual(r14["events"][0]["status"], "SEBAGIAN")
        self.assertIsNone(r14["events"][0]["verified_rupiah"])

        r18 = h1.evaluate_evidence_offline({"schema": h1.EVIDENCE_SCHEMA, "events": events}, recipient=bundle["recipient"], max_lag_days=18)
        self.assertEqual(r18["events"][0]["status"], "COCOK PENUH")
        self.assertEqual(r18["events"][0]["verified_rupiah"], 90000)

    def test_03_raw_account_number_leak_blocked_and_royalty_csv_bridge(self) -> None:
        bad_payload = {
            "schema": h1.EVIDENCE_SCHEMA,
            "events": [
                {
                    "id": "bad-acct",
                    "rail": "kbm_seabank",
                    "platform": {"ref": "p1", "amount_rupiah": 20000, "date": "2026-11-01", "provider": "kbm", "account_number": "901234567890"},
                }
            ],
        }
        with self.assertRaises(h1.Ws2HarnessError):
            h1.evaluate_evidence_offline(bad_payload, recipient="Dian Herdiana")

        bad_digits_payload = {
            "schema": h1.EVIDENCE_SCHEMA,
            "events": [
                {
                    "id": "bad-digits",
                    "rail": "kbm_seabank",
                    "platform": {"ref": "rek-901234567890", "amount_rupiah": 20000, "date": "2026-11-01", "provider": "kbm"},
                }
            ],
        }
        with self.assertRaises(h1.Ws2HarnessError):
            h1.evaluate_evidence_offline(bad_digits_payload, recipient="Dian Herdiana")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_file = base / "kbm.csv"
            csv_file.write_text(
                "serial,date,amount,currency,units\nNovelA,2026-10-05,25000,IDR,5\nNovelB,2026-10-12,10000,IDR,2\n",
                encoding="utf-8",
            )
            legs = h1.royalty_csv_to_kbm_platform_legs([csv_file])
            self.assertEqual(len(legs), 1)
            self.assertEqual(legs[0]["leg"]["amount_rupiah"], 35000)
            self.assertTrue(legs[0]["meets_kbm_minimum"])

            out_json = base / "fixtures.json"
            self.assertEqual(h1.main(["--export-fixtures", str(out_json)]), 0)
            self.assertEqual(h1.main(["--validate-evidence", str(out_json)]), 0)
            self.assertEqual(h1.main(["--validate-evidence", str(base / "missing.json")]), 2)


if __name__ == "__main__":
    unittest.main()
