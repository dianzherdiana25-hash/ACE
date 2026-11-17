#!/usr/bin/env python3
"""Unit tests untuk tools/royalty_track.py (WS-C #9)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.royalty_track import (
    ROYALTY_SCHEMA,
    RoyaltyTrackError,
    load_column_map,
    main,
    parse_decimal_amount,
    parse_month,
    summarize_royalties,
)


class TestRoyaltyTrack(unittest.TestCase):
    def test_decimal_precision_and_month_normalization(self) -> None:
        self.assertEqual(parse_month("2026-11-17"), "2026-11")
        self.assertEqual(parse_month("17/11/2026"), "2026-11")
        self.assertEqual(parse_month("2026-11"), "2026-11")
        self.assertEqual(str(parse_decimal_amount("Rp 12.500,50", decimal_separator=",")), "12500.50")
        self.assertEqual(str(parse_decimal_amount("($15.25)", decimal_separator=".")), "-15.25")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = tmp / "royalty.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "serial,date,amount,currency,units",
                        "SERI_A,2026-10-05,0.10,USD,1",
                        "SERI_A,2026-10-18,0.20,USD,2",
                        "SERI_A,2026-11-01,15000,IDR,3",
                        "SERI_B,02/11/2026,25000.50,IDR,5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rep = summarize_royalties([csv_path])
            self.assertEqual(rep["schema"], ROYALTY_SCHEMA)
            self.assertEqual(rep["valid_rows"], 4)
            self.assertEqual(rep["invalid_rows"], 0)
            self.assertEqual(rep["totals_by_currency"]["USD"], "0.30")
            self.assertEqual(rep["totals_by_currency"]["IDR"], "40000.50")
            self.assertEqual(
                rep["totals_by_serial"]["SERI_A"]["months"]["2026-10"]["revenue_by_currency"]["USD"],
                "0.30",
            )
            self.assertEqual(rep["totals_by_serial"]["SERI_A"]["total_units"], 6)

    def test_custom_mapping_json_and_error_isolation_and_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = tmp / "vendor_id.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "Judul Seri;Tanggal Transaksi;Nilai Bersih;Jumlah",
                        "Senja Kota;15-11-2026;Rp 10.000,25;4",
                        "Senja Kota;16-11-2026;CORRUPT;1",
                        ";17-11-2026;5000,00;1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            map_path = tmp / "map.json"
            map_path.write_text(
                json.dumps(
                    {
                        "serial": "Judul Seri",
                        "date": "Tanggal Transaksi",
                        "amount": "Nilai Bersih",
                        "units": "Jumlah",
                        "default_currency": "IDR",
                        "delimiter": ";",
                        "decimal_separator": ",",
                    }
                ),
                encoding="utf-8",
            )
            out_json = tmp / "summary.json"
            rc = main([str(csv_path), "--map", str(map_path), "--out", str(out_json)])
            self.assertEqual(rc, 0)
            rep = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(rep["valid_rows"], 1)
            self.assertEqual(rep["invalid_rows"], 2)
            self.assertEqual(rep["totals_by_currency"]["IDR"], "10000.25")
            self.assertEqual(rep["totals_by_serial"]["Senja Kota"]["total_units"], 4)

            strict_rc = main([str(csv_path), "--map", str(map_path), "--strict"])
            self.assertEqual(strict_rc, 2)

            with self.assertRaises(RoyaltyTrackError):
                load_column_map(tmp / "missing_map.json")


if __name__ == "__main__":
    unittest.main()
