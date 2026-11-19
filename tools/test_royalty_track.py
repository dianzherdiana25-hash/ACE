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

    def test_pasal7_tier_omzet_boundaries_exact_and_adjacent_rupiah(self) -> None:
        """Uji batas tier omzet Pasal 7 (Rp100rb/250rb/500rb/1jt/5jt) persis & ±Rp1."""
        # Nilai persis di batas dan ±Rp1 pada kedua sisi untuk kelima batas Pasal 7 KBM.
        boundaries = [100_000, 250_000, 500_000, 1_000_000, 5_000_000]
        points: list[tuple[str, int]] = []
        for idx, b in enumerate(boundaries, start=1):
            points.append((f"T{idx}_MINUS1", b - 1))
            points.append((f"T{idx}_EXACT", b))
            points.append((f"T{idx}_PLUS1", b + 1))

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # 1) Uji tiap titik batas tunggal sebagai serial terpisah dalam format IDR lokal.
            rows = ["serial,date,amount,currency,units"]
            expected_sum = 0
            for serial, rupiah in points:
                rows.append(f"{serial},2026-11-10,{rupiah},IDR,1")
                expected_sum += rupiah
            single_csv = tmp / "pasal7_points.csv"
            single_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")

            rep = summarize_royalties([single_csv])
            self.assertEqual(rep["valid_rows"], len(points))
            self.assertEqual(rep["invalid_rows"], 0)
            self.assertEqual(rep["totals_by_currency"]["IDR"], str(expected_sum))
            for serial, rupiah in points:
                self.assertEqual(
                    rep["totals_by_serial"][serial]["revenue_by_currency"]["IDR"],
                    str(rupiah),
                )

            # 2) Uji akumulasi bertahap persis melewati setiap ambang Pasal 7 (±Rp1).
            # 99.999 -> +1 = 100.000 -> +1 = 100.001 -> ... -> +1 = 5.000.001
            step_deltas = [
                ("bab_01", 99_999),
                ("bab_02", 1),        # kumulatif = 100.000
                ("bab_03", 1),        # kumulatif = 100.001
                ("bab_04", 149_998),  # kumulatif = 249.999
                ("bab_05", 1),        # kumulatif = 250.000
                ("bab_06", 1),        # kumulatif = 250.001
                ("bab_07", 249_998),  # kumulatif = 499.999
                ("bab_08", 1),        # kumulatif = 500.000
                ("bab_09", 1),        # kumulatif = 500.001
                ("bab_10", 499_998),  # kumulatif = 999.999
                ("bab_11", 1),        # kumulatif = 1.000.000
                ("bab_12", 1),        # kumulatif = 1.000.001
                ("bab_13", 3_999_998),  # kumulatif = 4.999.999
                ("bab_14", 1),        # kumulatif = 5.000.000
                ("bab_15", 1),        # kumulatif = 5.000.001
            ]
            running = 0
            for step_idx, (bab, delta) in enumerate(step_deltas, start=1):
                running += delta
                step_csv = tmp / f"step_{step_idx:02d}.csv"
                step_rows = ["serial,date,amount,currency,units"] + [
                    f"IANILA,2026-11-{d_idx:02d},{d_amt},IDR,1"
                    for d_idx, (_, d_amt) in enumerate(step_deltas[:step_idx], start=1)
                ]
                step_csv.write_text("\n".join(step_rows) + "\n", encoding="utf-8")
                step_rep = summarize_royalties([step_csv])
                self.assertEqual(
                    step_rep["totals_by_serial"]["IANILA"]["revenue_by_currency"]["IDR"],
                    str(running),
                    f"Mismatch at {bab}",
                )
            self.assertEqual(running, 5_000_001)

    def test_decimal_precision_subcent_and_separator_edge_cases(self) -> None:
        """Pembulatan/skala Decimal eksak tanpa drift biner IEEE-754."""
        # 100 baris @ 0.01 dan jebakan float 0.1 + 0.2 + 0.149999...
        self.assertEqual(str(parse_decimal_amount("1.234,565", decimal_separator=",")), "1234.565")
        self.assertEqual(str(parse_decimal_amount("1,234,567.89", decimal_separator=".")), "1234567.89")
        self.assertEqual(str(parse_decimal_amount("100,000", decimal_separator=".")), "100000")
        self.assertEqual(str(parse_decimal_amount("12,5", decimal_separator=".")), "12.5")
        self.assertEqual(str(parse_decimal_amount("12,50", decimal_separator=".")), "12.50")

        for bad in ("", "   ", "Rp ---", "NaN", "Infinity", "1.2.3"):
            with self.assertRaises(ValueError, msg=f"Should fail for {bad!r}"):
                parse_decimal_amount(bad)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = tmp / "precision.csv"
            lines = ["serial,date,amount,currency,units"]
            for idx in range(1, 101):
                lines.append(f"MICRO,2026-11-01,0.01,USD,1")
            lines.append("MICRO,2026-11-02,1500.335,IDR,1")
            lines.append("MICRO,2026-11-03,1500.335,IDR,1")
            lines.append("MICRO,2026-11-04,0.1,USD,1")
            lines.append("MICRO,2026-11-05,0.2,USD,1")
            csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            rep = summarize_royalties([csv_path])
            self.assertEqual(rep["totals_by_currency"]["USD"], "1.30")
            self.assertEqual(rep["totals_by_currency"]["IDR"], "3000.670")

    def test_cross_chapter_and_cross_file_accumulation_with_bom_and_multicurrency(self) -> None:
        """Akumulasi lintas bab, lintas berkas CSV (termasuk UTF-8 BOM), dan lintas bulan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Bab 8-10 (koin perak = 0 + emas = 1500), Bab 11-12 di bulan berikut + berkas berbeda
            f1 = tmp / "nov_bab8_10.csv"
            f1.write_text(
                "\ufeffserial,date,amount,currency,units\n"
                "SERI_X,2026-10-28,0.00,IDR,10\n"       # bab 8 perak
                "SERI_X,2026-10-29,1500.00,IDR,1\n"     # bab 9 emas
                "SERI_X,2026-10-30,1500.00,IDR,1\n"     # bab 10 emas
                "SERI_X,2026-10-31,2.50,USD,1\n",
                encoding="utf-8",
            )
            f2 = tmp / "nov_bab11_12.csv"
            f2.write_text(
                "serial,date,amount,currency,units\n"
                "SERI_X,2026-11-01T10:15:00,4500.50,IDR,3\n"
                "SERI_X,04/11/2026,7500.50,IDR,5\n"
                "SERI_X,2026-11-05,1.25,USD,1\n"
                "SERI_Y,2026-11-05,15000.00,IDR,10\n",
                encoding="utf-8",
            )
            rep = summarize_royalties([f1, f2])
            self.assertEqual(rep["valid_rows"], 8)
            self.assertEqual(rep["totals_by_currency"]["IDR"], "30001.00")
            self.assertEqual(rep["totals_by_currency"]["USD"], "3.75")

            sx = rep["totals_by_serial"]["SERI_X"]
            self.assertEqual(sx["row_count"], 7)
            self.assertEqual(sx["total_units"], 22)
            self.assertEqual(sx["revenue_by_currency"]["IDR"], "15001.00")
            self.assertEqual(sx["revenue_by_currency"]["USD"], "3.75")
            self.assertEqual(sx["months"]["2026-10"]["revenue_by_currency"]["IDR"], "3000.00")
            self.assertEqual(sx["months"]["2026-11"]["revenue_by_currency"]["IDR"], "12001.00")
            self.assertEqual([m["month"] for m in rep["monthly_totals"]], ["2026-10", "2026-11"])

    def test_zero_and_negative_amounts_and_refund_cancellation(self) -> None:
        """Nilai nol, negatif (- dan tanda kurung), refund penuh menjadi nol, dan unit negatif."""
        self.assertEqual(str(parse_decimal_amount("0")), "0")
        self.assertEqual(str(parse_decimal_amount("-0")), "0")
        self.assertEqual(str(parse_decimal_amount("(-0.00)")), "0.00")
        self.assertEqual(str(parse_decimal_amount("Rp 0,00", decimal_separator=",")), "0.00")
        self.assertEqual(str(parse_decimal_amount("-Rp 1.500,00", decimal_separator=",")), "-1500.00")
        self.assertEqual(str(parse_decimal_amount("(Rp 2.500,25)", decimal_separator=",")), "-2500.25")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = tmp / "zero_neg.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "serial,date,amount,currency,units",
                        "ZERO_ONLY,2026-11-01,0.00,IDR,0",
                        "NET_ZERO,2026-11-01,15000.00,IDR,10",
                        "NET_ZERO,2026-11-02,(15000.00),IDR,-10",
                        "NET_NEG,2026-11-03,5000.00,IDR,3",
                        "NET_NEG,2026-11-04,-7500.50,IDR,-5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rep = summarize_royalties([csv_path])
            self.assertEqual(rep["totals_by_currency"]["IDR"], "-2500.50")
            self.assertEqual(rep["totals_by_serial"]["ZERO_ONLY"]["revenue_by_currency"]["IDR"], "0.00")
            self.assertEqual(rep["totals_by_serial"]["NET_ZERO"]["revenue_by_currency"]["IDR"], "0.00")
            self.assertEqual(rep["totals_by_serial"]["NET_ZERO"]["total_units"], 0)
            self.assertEqual(rep["totals_by_serial"]["NET_NEG"]["revenue_by_currency"]["IDR"], "-2500.50")
            self.assertEqual(rep["totals_by_serial"]["NET_NEG"]["total_units"], -2)

    def test_error_validation_for_bad_csv_and_mapping(self) -> None:
        """Validasi kegagalan CSV kosong, kolom hilang, separator salah, dan baris rusak."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with self.assertRaises(RoyaltyTrackError):
                summarize_royalties([])
            with self.assertRaises(RoyaltyTrackError):
                summarize_royalties([tmp / "tidak_ada.csv"])
            empty_csv = tmp / "empty.csv"
            empty_csv.write_text("", encoding="utf-8")
            with self.assertRaises(RoyaltyTrackError):
                summarize_royalties([empty_csv])

            bad_cols = tmp / "bad_cols.csv"
            bad_cols.write_text("serial,date\nA,2026-11-01\n", encoding="utf-8")
            with self.assertRaises(RoyaltyTrackError):
                summarize_royalties([bad_cols])

            bad_units = tmp / "bad_units.csv"
            bad_units.write_text("serial,date,amount,units\nA,2026-11-01,1000,1.5\n", encoding="utf-8")
            rep = summarize_royalties([bad_units], strict=False)
            self.assertEqual(rep["valid_rows"], 0)
            self.assertEqual(rep["invalid_rows"], 1)
            with self.assertRaises(RoyaltyTrackError):
                summarize_royalties([bad_units], strict=True)

            with self.assertRaises(RoyaltyTrackError):
                load_column_map(None, overrides={"decimal_separator": ";"})
            with self.assertRaises(RoyaltyTrackError):
                load_column_map(None, overrides={"serial": "   "})

    def test_expected_failure_currency_prefix_before_minus_sign(self) -> None:
        """Bug D1 yang sudah diperbaiki (2026-11-20): `Rp -1.500,00` dulu
        menghilangkan tanda minus karena cek `startswith('-')` berjalan
        sebelum awalan mata uang dibuang. Parser kini mengecek tanda lagi
        sesudah awalan mata uang disingkirkan.
        """
        self.assertEqual(
            str(parse_decimal_amount("Rp -1.500,00", decimal_separator=",")),
            "-1500.00",
        )

    def test_expected_failure_pasal7_tiered_author_share_not_computed(self) -> None:
        """Celah D1 yang sudah ditutup (2026-11-20): `summarize_royalties`
        kini melampirkan `tier_summary` Pasal 7 per serial
        (<=100rb: 100%, <=250rb: 90%, <=500rb: 80%, <=1jt: 70%, <=5jt: 65%, >5jt: 60%).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "tier2.csv"
            csv_path.write_text(
                "serial,date,amount,currency,units\nIANILA,2026-11-01,250000,IDR,1\n",
                encoding="utf-8",
            )
            rep = summarize_royalties([csv_path])
            tier = rep["totals_by_serial"]["IANILA"]["tier_summary"]
            self.assertEqual(tier["omzet_idr"], "250000")
            self.assertEqual(tier["rate_percent"], "90")
            self.assertEqual(tier["author_share_idr"], "225000")


if __name__ == "__main__":
    unittest.main()
