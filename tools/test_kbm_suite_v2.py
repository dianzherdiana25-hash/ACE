"""Unit & adversarial tests untuk tools/kbm_suite_v2.py (H3)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import unittest
from unittest import mock

from tools import kbm_suite_v2 as kbm2


def _make_png(width: int, height: int, min_bytes: int = 1200) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"
    header = b"\x89PNG\r\n\x1a\n" + ihdr_chunk
    pad = max(0, min_bytes - len(header))
    return header + (b"\x00" * pad)


class TestKbmSuiteV2(unittest.TestCase):
    def test_01_qa_passes_clean_package_and_detects_duplicates_empty_and_bad_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "kbm_pkg"
            pkg.mkdir()
            (pkg / "cover.png").write_bytes(_make_png(800, 1200, 1500))
            body1 = ("kata " * 900).strip() + "\n"
            body2 = ("kalimat " * 950).strip() + "\n"
            (pkg / "bab_01.md").write_text("# Bab 1\n\n" + body1, encoding="utf-8")
            (pkg / "bab_02.md").write_text("# Bab 2\n\n" + body2, encoding="utf-8")

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                rep = kbm2.audit_manuscript_package(pkg, min_words=800, max_words=2000, min_bytes=100)
            self.assertTrue(rep["qa_passed"])
            self.assertEqual(rep["pacing_summary"]["chapter_count"], 2)
            self.assertEqual(rep["duplicate_chapter_groups"], [])
            self.assertEqual(rep["empty_chapters"], [])
            self.assertEqual(kbm2.main(["qa", str(pkg), "--min-bytes", "100", "--strict"]), 0)

            # Duplikasi isi bab_01 ke bab_03 (hanya beda spasi) + buat bab_04 kosong
            (pkg / "bab_03.md").write_text("  # Bab 1  \n\n" + body1.replace(" ", "  "), encoding="utf-8")
            (pkg / "bab_04.md").write_text("   \n\n", encoding="utf-8")
            rep_bad = kbm2.audit_manuscript_package(pkg, min_words=800, max_words=2000, min_bytes=0)
            self.assertFalse(rep_bad["qa_passed"])
            self.assertEqual(len(rep_bad["duplicate_chapter_groups"]), 1)
            self.assertEqual(rep_bad["duplicate_chapter_groups"][0]["files"], ["bab_01.md", "bab_03.md"])
            self.assertEqual(rep_bad["empty_chapters"], ["bab_04.md"])
            self.assertEqual(kbm2.main(["qa", str(pkg), "--min-bytes", "0", "--strict"]), 1)

    def test_02_decimal_royalty_projection_and_csv_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            csv_hist = base / "hist.csv"
            csv_hist.write_text("serial,date,amount,currency,units\nS1,2026-10-01,25000,IDR,10\n", encoding="utf-8")
            proj = kbm2.project_royalties(
                unit_price_idr="10000",
                author_share_rate="0.70",
                monthly_units=1,
                months=4,
                royalty_csv_paths=[csv_hist],
            )
            # unit_royalty = 7000 IDR -> threshold 15000 tercapai pada bulan ke-3 (7k -> 14k -> 21k cair!)
            self.assertEqual(proj["parameters"]["unit_royalty_idr"], "7000.00")
            self.assertEqual(proj["historical_idr_start"], "25000.00")
            self.assertFalse(proj["schedule"][0]["payout_triggered"])
            self.assertFalse(proj["schedule"][1]["payout_triggered"])
            self.assertTrue(proj["schedule"][2]["payout_triggered"])
            self.assertEqual(proj["schedule"][2]["payout_idr"], "21000.00")
            self.assertEqual(proj["summary"]["payout_events_count"], 1)
            self.assertEqual(proj["summary"]["ending_carried_balance_idr"], "7000.00")

            out_csv = base / "proj.csv"
            rc = kbm2.main(
                [
                    "project",
                    "--unit-price-idr",
                    "10000",
                    "--author-share-rate",
                    "0.70",
                    "--monthly-units",
                    "1",
                    "--months",
                    "4",
                    "--format",
                    "csv",
                    "--output",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 0)
            csv_text = out_csv.read_text(encoding="utf-8")
            self.assertIn("21000.00", csv_text)

    def test_03_rejects_symlinks_and_invalid_decimal_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            secret = base / "sec.txt"
            secret.write_text("abc", encoding="utf-8")
            pkg = base / "pkg_sym"
            pkg.mkdir()
            os.symlink(secret, pkg / "bab_01.md")
            with self.assertRaises(kbm2.KbmSuiteV2Error):
                kbm2.audit_manuscript_package(pkg)

        self.assertEqual(
            kbm2.main(["project", "--unit-price-idr", "NaN", "--author-share-rate", "0.5", "--monthly-units", "10"]),
            2,
        )


if __name__ == "__main__":
    unittest.main()
