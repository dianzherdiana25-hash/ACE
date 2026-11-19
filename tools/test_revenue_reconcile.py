"""Unit & adversarial tests untuk tools/revenue_reconcile.py (H2)."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import revenue_reconcile as rr

REPO_ROOT = Path(__file__).resolve().parents[1]


def _verif_report(*events: dict) -> dict:
    return {
        "schema": rr.VERIFICATION_SCHEMA,
        "max_lag_days": 14,
        "events": list(events),
    }


class TestRevenueReconcile(unittest.TestCase):
    def test_01_clean_full_reconciliation_across_all_three_rails(self) -> None:
        ledger = [
            {"id": 1, "tipe": "PEMASUKAN", "kategori": "Royalti", "deskripsi": "KBM Okt", "nominal": 150000, "event_id": "ev-kbm", "rail": "kbm_seabank"},
            {"id": 2, "tipe": "PEMASUKAN", "kategori": "Jasa", "deskripsi": "Fastwork neto", "nominal": 497000, "event_id": "ev-fw", "rail": "fastwork_bank"},
            {"id": 3, "tipe": "PEMASUKAN", "kategori": "QRIS", "deskripsi": "GoPay harian", "nominal": 85000, "event_id": "ev-gp", "rail": "gopay_qris"},
            {"id": 4, "tipe": "PENGELUARAN", "kategori": "Kebutuhan (50%)", "deskripsi": "Sewa", "nominal": 500000},
        ]
        verif = _verif_report(
            {"id": "ev-kbm", "rail": "kbm_seabank", "status": "COCOK PENUH", "issues": [], "verified_rupiah": 150000},
            {"id": "ev-fw", "rail": "fastwork_bank", "status": "COCOK PENUH", "issues": [], "verified_rupiah": 497000},
            {"id": "ev-gp", "rail": "gopay_qris", "status": "COCOK PENUH", "issues": [], "verified_rupiah": 85000},
        )
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
            rep = rr.reconcile_ledger(ledger, verif)
        self.assertTrue(rep["clean"])
        self.assertEqual(rep["summary"]["discrepancy_count"], 0)
        self.assertEqual(rep["summary"]["reconciled_rupiah"], 732000)
        self.assertEqual(rep["summary"]["ledger_expense_rupiah"], 500000)
        md = rr.render_markdown(rep)
        self.assertIn("BERSIH (RECONCILED)", md)

    def test_02_catches_duplicate_partial_unlinked_amount_mismatch_and_unbooked(self) -> None:
        ledger = {
            "entries": [
                {"id": 1, "tipe": "PEMASUKAN", "deskripsi": "Duplikat 1", "nominal": 150000, "event_id": "ev-kbm"},
                {"id": 2, "tipe": "PEMASUKAN", "deskripsi": "Duplikat 2", "nominal": 150000, "event_id": "ev-kbm"},
                {"id": 3, "tipe": "PEMASUKAN", "deskripsi": "Kaki kurang", "nominal": 90000, "event_id": "ev-hilang"},
                {"id": 4, "tipe": "PEMASUKAN", "deskripsi": "Selisih angka", "nominal": 500000, "event_id": "ev-fw"},
                {"id": 5, "tipe": "PEMASUKAN", "deskripsi": "Tanpa tautan", "nominal": 75000},
            ]
        }
        verif = _verif_report(
            {"id": "ev-kbm", "rail": "kbm_seabank", "status": "COCOK PENUH", "issues": [], "verified_rupiah": 150000},
            {"id": "ev-hilang", "rail": "kbm_seabank", "status": "HILANG", "issues": ["missing:statement"], "verified_rupiah": None},
            {"id": "ev-fw", "rail": "fastwork_bank", "status": "COCOK PENUH", "issues": [], "verified_rupiah": 497000},
            {"id": "ev-unbooked", "rail": "gopay_qris", "status": "COCOK PENUH", "issues": [], "verified_rupiah": 85000},
        )
        rep = rr.reconcile_ledger(ledger, verif)
        self.assertFalse(rep["clean"])
        statuses = [r["reconcile_status"] for r in rep["income_records"]]
        self.assertEqual(
            statuses,
            [
                "DUPLICATE_CLAIM",
                "DUPLICATE_CLAIM",
                "UNVERIFIED_PARTIAL_OR_MISSING",
                "AMOUNT_MISMATCH",
                "UNLINKED_LEDGER_INCOME",
            ],
        )
        self.assertEqual(len(rep["unbooked_verified_events"]), 1)
        self.assertEqual(rep["unbooked_verified_events"][0]["event_id"], "ev-unbooked")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lf = base / "ledger.json"
            vf = base / "verif.json"
            lf.write_text(json.dumps(ledger), encoding="utf-8")
            vf.write_text(json.dumps(verif), encoding="utf-8")
            # Strict mode default harus exit 1, --report-only harus exit 0
            self.assertEqual(rr.main(["--ledger", str(lf), "--verification", str(vf)]), 1)
            self.assertEqual(rr.main(["--ledger", str(lf), "--verification", str(vf), "--report-only", "--format", "markdown"]), 0)

    def test_03_projects_ledger_read_only_compatibility_and_account_leak_blocked(self) -> None:
        sample_ledger = REPO_ROOT / "projects" / "pengelola_keuangan" / "data_keuangan.json"
        self.assertTrue(sample_ledger.is_file())
        data = json.loads(sample_ledger.read_text(encoding="utf-8"))
        rep = rr.reconcile_ledger(data, _verif_report())
        # Semua pemasukan di data_keuangan.json belum punya event_id -> ditandai jujur UNLINKED_LEDGER_INCOME
        self.assertFalse(rep["clean"])
        self.assertGreater(rep["summary"]["ledger_income_count"], 0)
        self.assertGreater(rep["summary"]["ledger_expense_count"], 0)
        self.assertEqual(rep["summary"]["reconciled_rupiah"], 0)

        # Blokir nomor rekening terbuka
        bad = [{"id": 1, "tipe": "PEMASUKAN", "deskripsi": "Rek 901234567890", "nominal": 10000}]
        with self.assertRaises(rr.ReconcileError):
            rr.reconcile_ledger(bad, _verif_report())
        self.assertEqual(rr.main(["--ledger", "/tmp/no_ledger.json", "--verification", "/tmp/no_verif.json"]), 2)


if __name__ == "__main__":
    unittest.main()
