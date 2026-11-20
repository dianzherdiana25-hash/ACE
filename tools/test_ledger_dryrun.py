"""Tes regresi fixture-only untuk tools.ledger_dryrun (AG55)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import ledger_dryrun


class LedgerDryrunTest(unittest.TestCase):
    def test_full_match_and_both_sided_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_path = root / "reconcile.json"

            # 1. Full match fixture -> exit code 0, zero orphan dari kedua sisi.
            ledger_full = root / "ledger_full.csv"
            report_full = root / "report_full.json"
            ledger_full.write_text(
                "name,platform,amount,proof_id,date\n"
                "Karya Alpha,KBM,75000,proof-sim-001,2026-11-18\n"
                "Karya Beta,GoPay,50000,proof-sim-002,2026-11-19\n",
                encoding="utf-8",
            )
            report_full.write_text(
                json.dumps(
                    [
                        {"name": "  karya  alpha ", "platform": "kbm", "amount": 75000, "proof_id": "proof-sim-001"},
                        {"name": "Karya Beta", "platform": "gopay", "amount": "50000.00", "proof_id": "proof-sim-002"},
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                ledger_dryrun.main(
                    ["--ledger", str(ledger_full), "--report", str(report_full), "--out", str(out_path)]
                ),
                0,
            )
            rep_full = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(rep_full["schema"], ledger_dryrun.SCHEMA)
            self.assertTrue(rep_full["reconciled_clean"])
            self.assertEqual(rep_full["summary"]["matched_count"], 2)
            self.assertEqual(rep_full["summary"]["ledger_orphan_count"], 0)
            self.assertEqual(rep_full["summary"]["report_orphan_count"], 0)
            self.assertEqual(rep_full["summary"]["matched_total_amount"], "125000")

            # 2. Fixture orphan kedua sisi: 1 cocok penuh, 1 orphan ledger, 1 orphan report -> exit code 1.
            ledger_mix = root / "ledger_mix.csv"
            report_mix = root / "report_mix.json"
            ledger_mix.write_text(
                "name,platform,amount,proof_id\n"
                "Karya Alpha,KBM,75000,proof-sim-001\n"
                "Karya Yatim Ledger,SeaBank,30000,proof-ledger-only\n",
                encoding="utf-8",
            )
            report_mix.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"name": "Karya Alpha", "platform": "KBM", "amount": 75000, "proof_id": "proof-sim-001"},
                            {"name": "Karya Yatim Report", "platform": "QRIS", "amount": 45000, "proof_id": "proof-report-only"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                ledger_dryrun.main(
                    ["--ledger", str(ledger_mix), "--report", str(report_mix), "--out", str(out_path)]
                ),
                1,
            )
            rep_mix = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertFalse(rep_mix["reconciled_clean"])
        self.assertEqual(rep_mix["summary"]["matched_count"], 1)
        self.assertEqual(rep_mix["summary"]["ledger_orphan_count"], 1)
        self.assertEqual(rep_mix["summary"]["report_orphan_count"], 1)
        self.assertEqual(
            rep_mix["ledger_orphans"][0]["match_key"]["proof_id"],
            "proof-ledger-only",
        )
        self.assertEqual(
            rep_mix["report_orphans"][0]["match_key"]["proof_id"],
            "proof-report-only",
        )


if __name__ == "__main__":
    unittest.main()
