"""Pastikan ringkasan periode dan posisi ledger memakai bukti yang tepat."""
import json
from datetime import date
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.income_report import (
    INCOME_SCHEMA, LEDGER_SCHEMA, LedgerPosition, read_ledger, render_income_report,
)


SCRIPT = Path(__file__).with_name("income_report.py")
AS_OF = date(2026, 2, 8)


def event(event_id, rail, settled, amount, *, status="COCOK PENUH"):
    return {"id": event_id, "rail": rail, "status": status,
            "issues": [] if status == "COCOK PENUH" else ["fixture"],
            "verified_rupiah": amount, "statement_date": settled}


def results(*events):
    return {"schema": INCOME_SCHEMA, "max_lag_days": 14, "events": list(events)}


class IncomeReportTests(unittest.TestCase):
    def test_monthly_totals_and_both_goals_match_manual_calculation(self):
        result = results(
            event("one", "kbm_seabank", "2026-02-01", 15_000),
            event("two", "kbm_seabank", "2026-02-08", 16_000),
            event("three", "fastwork_bank", "2026-02-05", 22_000),
            event("before", "gopay_qris", "2026-01-31", 800_000),
            event("later", "gopay_qris", "2026-02-09", 700_000),
            event("partial", "gopay_qris", "2026-02-05", None, status="SEBAGIAN"),
            event("missing", "gopay_qris", None, None, status="HILANG"),
        )
        ledger = LedgerPosition(AS_OF, 75_000, 100_000, 400_000, 125_000)

        report = render_income_report(result, ledger, period="monthly", as_of=AS_OF)

        for expected in (
                "# Laporan pendapatan bulanan",
                "- Periode mutasi — 2026-02-01 s.d. 2026-02-08",
                "- Peristiwa cocok penuh dalam periode — 3",
                "- `fastwork_bank` — Rp22.000",
                "- `kbm_seabank` — Rp31.000",
                "- Total masuk terverifikasi periode — Rp53.000",
                "- Kas terverifikasi — Rp75.000",
                "- Biaya operasional — Rp100.000",
                "- Sisa menuju cakupan biaya — Rp25.000",
                "- Target utang awal — Rp400.000",
                "- Dibayar menurut ledger — Rp125.000",
                "- Sisa target utang awal — Rp275.000"):
            self.assertIn(expected, report)
        self.assertNotIn("gopay_qris", report)

    def test_weekly_uses_monday_and_crosses_calendar_month(self):
        as_of = date(2026, 1, 3)
        report = render_income_report(
            results(event("one", "fastwork_bank", "2025-12-29", 1_000),
                    event("two", "gopay_qris", "2026-01-03", 2_000),
                    event("earlier", "fastwork_bank", "2025-12-28", 10_000),
                    event("later", "gopay_qris", "2026-01-04", 20_000)),
            LedgerPosition(as_of), period="weekly", as_of=as_of)
        self.assertIn("- Periode mutasi — 2025-12-29 s.d. 2026-01-03", report)
        self.assertIn("- Total masuk terverifikasi periode — Rp3.000", report)

    def test_shortfall_floors_at_zero_and_null_stays_unknown(self):
        ledger = LedgerPosition(AS_OF, 40_000, 0, None, 25_000)
        report = render_income_report(results(), ledger, period="monthly", as_of=AS_OF)
        self.assertIn("- Biaya operasional — Rp0", report)
        self.assertIn("- Sisa menuju cakupan biaya — Rp0", report)
        self.assertIn("- Sisa target utang awal — TIDAK TAHU", report)
        self.assertIn("Belum ada bukti cocok penuh", report)

    def test_dating_and_flag_consistency_are_required(self):
        bad_events = [
            (event("one", "kbm_seabank", None, 300), "statement_date"),
            (event("one", "kbm_seabank", "2026-02-30", 300), "statement_date"),
            (event("one", "kbm_seabank", "2026-02-08", 300, status="HILANG"),
             "wajib null"),
            (event("one", "unregistered", "2026-02-08", 300), "tidak konsisten"),
        ]
        for invalid, message in bad_events:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, message):
                    render_income_report(results(invalid), LedgerPosition(AS_OF),
                                         period="weekly", as_of=AS_OF)

    def test_ledger_date_must_match_report_cutoff(self):
        with self.assertRaisesRegex(ValueError, "Tanggal posisi ledger"):
            render_income_report(results(), LedgerPosition(date(2026, 2, 7)),
                                 period="monthly", as_of=AS_OF)

    def test_duplicate_verification_ids_are_rejected(self):
        row = event("id-repeat", "kbm_seabank", "2026-02-08", 13_000)
        with self.assertRaisesRegex(ValueError, "ganda"):
            render_income_report(results(row, row.copy()), LedgerPosition(AS_OF),
                                 period="monthly", as_of=AS_OF)


class LedgerSourceTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def write(self, filename, contents):
        path = self.root / filename
        path.write_text(contents, encoding="utf-8")
        return path

    def test_legacy_markdown_uses_explicit_cash_and_debt_total(self):
        path = self.write(
            "ledger.md",
            "Total keseluruhan TUNAI terverifikasi: Rp 250.000\n"
            "| **Total** | **500.000** | — | **100.000** | **400.000** | **20.0%** |\n",
        )
        report = render_income_report(results(), read_ledger(path), period="monthly", as_of=AS_OF)
        self.assertIn("- Tanggal posisi ledger — TIDAK TAHU", report)
        self.assertIn("- Kas terverifikasi — Rp250.000", report)
        self.assertIn("- Biaya operasional — TIDAK TAHU", report)
        self.assertIn("- Sisa target utang awal — Rp400.000", report)

    def test_malformed_markdown_figures_fail_closed(self):
        for text, message in (
                ("Total biaya operasional ACE: Rp 1.00", "rupiah bulat"),
                ("Total biaya operasional ACE: Rp 1.000\n"
                 "Total biaya operasional ACE: Rp 2.000", "ganda"),
                ("| **Total** | **500.000** | — | **100.000** | **300.000** | **20.0%** |",
                 "tidak konsisten")):
            with self.subTest(text=text):
                path = self.write("ledger.md", text)
                with self.assertRaisesRegex(ValueError, message):
                    read_ledger(path)

    def test_json_amount_does_not_coerce_boolean(self):
        path = self.write("ledger.json", json.dumps({
            "schema": LEDGER_SCHEMA, "as_of": AS_OF.isoformat(), "operating_cost_rupiah": True,
        }))
        with self.assertRaisesRegex(ValueError, "rupiah bulat"):
            read_ledger(path)

    def test_cli_keeps_both_files_unchanged_and_outputs_markdown(self):
        verification = self.write("verification.json", json.dumps(
            results(event("id", "gopay_qris", AS_OF.isoformat(), 19_000))))
        ledger = self.write("ledger.md", "Tanggal posisi: 2026-02-08\n"
                            "- **Total keseluruhan TUNAI terverifikasi:** Rp 25.000\n"
                            "Total biaya operasional ACE: Rp 22.000\n")
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        run = subprocess.run(
            [sys.executable, str(SCRIPT), str(verification), str(ledger),
             "--period", "weekly", "--as-of", AS_OF.isoformat()],
            cwd=self.root, text=True, capture_output=True, check=True, timeout=15,
        )
        after = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(before, after)
        self.assertIn("# Laporan pendapatan mingguan", run.stdout)
        self.assertIn("- Total masuk terverifikasi periode — Rp19.000", run.stdout)
        self.assertIn("- Sisa menuju cakupan biaya — Rp0", run.stdout)

    def test_cli_invalid_ledger_prints_no_report(self):
        verification = self.write("verification.json", json.dumps(results()))
        ledger = self.write("ledger.json", "[]")
        run = subprocess.run(
            [sys.executable, str(SCRIPT), str(verification), str(ledger), "--as-of", AS_OF.isoformat()],
            cwd=self.root, text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, "")
        self.assertIn(LEDGER_SCHEMA, run.stderr)


if __name__ == "__main__":
    unittest.main()
