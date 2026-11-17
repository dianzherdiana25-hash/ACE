#!/usr/bin/env python3
"""Pelacak laporan royalti dan penjualan CSV KBM menggunakan aritmetika Decimal (WS-C #9).

Mengimpor satu atau lebih berkas CSV laporan royalti/penjualan melalui pemetaan
kolom yang dapat dikonfigurasi (`--map` JSON atau flag CLI), menormalkan tanggal
menjadi bulan `YYYY-MM`, menghitung total per serial per bulan memakai
`decimal.Decimal` (tanpa galat floating-point), dan menghasilkan ringkasan JSON
`ace.royalty-summary.v1` untuk konsumsi dashboard status.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import io
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

ROYALTY_SCHEMA = "ace.royalty-summary.v1"

DEFAULT_COLUMN_MAP: dict[str, Any] = {
    "serial": "serial",
    "date": "date",
    "amount": "amount",
    "currency": "currency",
    "units": "units",
    "default_currency": "IDR",
    "delimiter": ",",
    "decimal_separator": ".",
}


class RoyaltyTrackError(ValueError):
    """Kesalahan berkas masukan CSV, pemetaan kolom, atau argumen CLI."""


def parse_month(raw_date: str) -> str:
    """Ubah string tanggal menjadi kunci bulan kanonik `YYYY-MM`."""
    cleaned = raw_date.strip()
    if not cleaned:
        raise ValueError("Tanggal kosong.")
    if re.fullmatch(r"\d{4}-\d{2}", cleaned):
        datetime.strptime(cleaned, "%Y-%m")
        return cleaned
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(cleaned[:19] if "T" in cleaned or " " in cleaned else cleaned, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue
    raise ValueError(f"Format tanggal tidak dikenali: {raw_date!r}")


def parse_decimal_amount(raw_amount: str, *, decimal_separator: str = ".") -> Decimal:
    """Parse nominal uang string menjadi Decimal secara aman."""
    if not isinstance(raw_amount, str):
        raise ValueError("Nominal wajib berupa string.")
    s = raw_amount.strip()
    if not s:
        raise ValueError("Nominal kosong.")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        negative = True
        s = s[1:].strip()

    # Buang simbol mata uang / huruf / spasi.
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        raise ValueError(f"Nominal tidak mengandung digit: {raw_amount!r}")

    if decimal_separator == ",":
        # Format lokal Indonesia/Eropa: titik = pemisah ribuan, koma = desimal.
        s = s.replace(".", "").replace(",", ".")
    else:
        # Format standar: buang koma ribuan bila ada pola ribuan atau multiple comma.
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s:
            # Jika tepat 1 koma diikuti <= 2 digit di akhir (dan bukan 3 digit ribuan), anggap desimal.
            parts = s.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                s = parts[0] + "." + parts[1]
            else:
                s = s.replace(",", "")

    try:
        val = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"Nominal Decimal tidak sah: {raw_amount!r}") from exc
    if not val.is_finite():
        raise ValueError(f"Nominal non-finit tidak diizinkan: {raw_amount!r}")
    return -val if negative else val


def load_column_map(map_path: Path | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Muat konfigurasi pemetaan kolom CSV dari JSON ditambah override CLI."""
    cfg = dict(DEFAULT_COLUMN_MAP)
    if map_path is not None:
        if not map_path.is_file():
            raise RoyaltyTrackError(f"Berkas mapping kolom tidak ditemukan: {map_path}")
        try:
            loaded = json.loads(map_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RoyaltyTrackError(f"Gagal membaca mapping JSON '{map_path}': {exc}") from exc
        if not isinstance(loaded, dict):
            raise RoyaltyTrackError("Berkas mapping kolom wajib objek JSON.")
        cfg.update({k: v for k, v in loaded.items() if v is not None})
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v is not None})

    for req_col in ("serial", "date", "amount"):
        if not isinstance(cfg.get(req_col), str) or not cfg[req_col].strip():
            raise RoyaltyTrackError(f"Konfigurasi kolom `{req_col}` wajib string tidak kosong.")
    if cfg.get("decimal_separator") not in (".", ","):
        raise RoyaltyTrackError("`decimal_separator` wajib `.` atau `,`.")
    return cfg


def summarize_royalties(
    csv_paths: list[Path],
    *,
    column_map: dict[str, Any] | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Hitung ringkasan pendapatan Decimal per serial dan per bulan dari berkas CSV."""
    if not csv_paths:
        raise RoyaltyTrackError("Minimal satu berkas CSV royalti harus diberikan.")
    cfg = dict(DEFAULT_COLUMN_MAP)
    if column_map:
        cfg.update(column_map)

    col_serial = str(cfg["serial"])
    col_date = str(cfg["date"])
    col_amount = str(cfg["amount"])
    col_currency = cfg.get("currency")
    col_units = cfg.get("units")
    default_currency = str(cfg.get("default_currency") or "IDR").upper()
    delimiter = str(cfg.get("delimiter") or ",")
    decimal_sep = str(cfg.get("decimal_separator") or ".")

    totals_by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    serial_buckets: dict[str, dict[str, Any]] = {}
    month_buckets: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    total_rows = 0
    valid_rows = 0

    for path in csv_paths:
        if not path.is_file():
            raise RoyaltyTrackError(f"Berkas CSV tidak ditemukan: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise RoyaltyTrackError(f"Gagal membaca CSV '{path}': {exc}") from exc

        reader = csv.DictReader(io.StringIO(raw_text), delimiter=delimiter)
        if not reader.fieldnames:
            raise RoyaltyTrackError(f"Berkas CSV '{path}' tidak memiliki header.")
        missing_cols = [c for c in (col_serial, col_date, col_amount) if c not in reader.fieldnames]
        if missing_cols:
            raise RoyaltyTrackError(
                f"Berkas CSV '{path}' kekurangan kolom wajib {missing_cols}; header aktual={reader.fieldnames}"
            )

        for row_idx, row in enumerate(reader, start=2):
            total_rows += 1
            serial = (row.get(col_serial) or "").strip()
            raw_date = (row.get(col_date) or "").strip()
            raw_amt = (row.get(col_amount) or "").strip()
            raw_cur = (row.get(str(col_currency)) or "").strip().upper() if col_currency and col_currency in row else default_currency
            currency = raw_cur or default_currency

            try:
                if not serial:
                    raise ValueError("Kolom serial kosong.")
                month = parse_month(raw_date)
                amount = parse_decimal_amount(raw_amt, decimal_separator=decimal_sep)
                units = 0
                if col_units and col_units in row and (row.get(str(col_units)) or "").strip():
                    units_str = (row.get(str(col_units)) or "").strip()
                    if not re.fullmatch(r"-?\d+", units_str):
                        raise ValueError(f"Nilai unit tidak valid: {units_str!r}")
                    units = int(units_str)
            except ValueError as exc:
                err_rec = {"file": str(path), "line": row_idx, "error": str(exc)}
                errors.append(err_rec)
                if strict:
                    raise RoyaltyTrackError(f"Baris {row_idx} pada '{path}' tidak valid: {exc}") from exc
                continue

            valid_rows += 1
            totals_by_currency[currency] += amount

            s_entry = serial_buckets.setdefault(
                serial,
                {
                    "revenue_by_currency": defaultdict(lambda: Decimal("0")),
                    "total_units": 0,
                    "row_count": 0,
                    "months": {},
                },
            )
            s_entry["revenue_by_currency"][currency] += amount
            s_entry["total_units"] += units
            s_entry["row_count"] += 1
            sm_entry = s_entry["months"].setdefault(
                month,
                {"revenue_by_currency": defaultdict(lambda: Decimal("0")), "units": 0, "rows": 0},
            )
            sm_entry["revenue_by_currency"][currency] += amount
            sm_entry["units"] += units
            sm_entry["rows"] += 1

            m_entry = month_buckets.setdefault(
                month,
                {"revenue_by_currency": defaultdict(lambda: Decimal("0")), "units": 0, "rows": 0},
            )
            m_entry["revenue_by_currency"][currency] += amount
            m_entry["units"] += units
            m_entry["rows"] += 1

    serialized_serials: dict[str, Any] = {}
    for serial in sorted(serial_buckets):
        sb = serial_buckets[serial]
        months_out: dict[str, Any] = {}
        for month in sorted(sb["months"]):
            mb = sb["months"][month]
            months_out[month] = {
                "revenue_by_currency": {cur: format(val, "f") for cur, val in sorted(mb["revenue_by_currency"].items())},
                "units": mb["units"],
                "rows": mb["rows"],
            }
        serialized_serials[serial] = {
            "revenue_by_currency": {cur: format(val, "f") for cur, val in sorted(sb["revenue_by_currency"].items())},
            "total_units": sb["total_units"],
            "row_count": sb["row_count"],
            "months": months_out,
        }

    monthly_totals = [
        {
            "month": month,
            "revenue_by_currency": {
                cur: format(val, "f") for cur, val in sorted(month_buckets[month]["revenue_by_currency"].items())
            },
            "units": month_buckets[month]["units"],
            "rows": month_buckets[month]["rows"],
        }
        for month in sorted(month_buckets)
    ]

    return {
        "schema": ROYALTY_SCHEMA,
        "files": [str(p) for p in csv_paths],
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": len(errors),
        "totals_by_currency": {cur: format(val, "f") for cur, val in sorted(totals_by_currency.items())},
        "totals_by_serial": serialized_serials,
        "monthly_totals": monthly_totals,
        "errors": errors,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import laporan royalti/penjualan CSV KBM dengan aritmetika Decimal."
    )
    parser.add_argument("csv_files", nargs="+", type=Path, help="Satu atau lebih berkas CSV laporan royalti.")
    parser.add_argument("--map", type=Path, default=None, help="Path berkas JSON konfigurasi pemetaan kolom.")
    parser.add_argument("--out", type=Path, default=None, help="Path opsional berkas JSON keluaran ringkasan.")
    parser.add_argument("--col-serial", default=None, help="Nama kolom serial.")
    parser.add_argument("--col-date", default=None, help="Nama kolom tanggal.")
    parser.add_argument("--col-amount", default=None, help="Nama kolom nilai royalti.")
    parser.add_argument("--col-currency", default=None, help="Nama kolom mata uang.")
    parser.add_argument("--col-units", default=None, help="Nama kolom jumlah unit.")
    parser.add_argument("--default-currency", default=None, help="Mata uang default jika kolom kosong (mis. IDR).")
    parser.add_argument("--delimiter", default=None, help="Pemisah CSV (mis. `,` atau `;`).")
    parser.add_argument("--decimal-sep", choices=(".", ","), default=None, help="Pemisah desimal nominal.")
    parser.add_argument("--strict", action="store_true", help="Gagal dengan exit 2 bila ada baris CSV rusak.")
    args = parser.parse_args(argv)

    try:
        col_map = load_column_map(
            args.map,
            overrides={
                "serial": args.col_serial,
                "date": args.col_date,
                "amount": args.col_amount,
                "currency": args.col_currency,
                "units": args.col_units,
                "default_currency": args.default_currency,
                "delimiter": args.delimiter,
                "decimal_separator": args.decimal_sep,
            },
        )
        report = summarize_royalties(args.csv_files, column_map=col_map, strict=args.strict)
    except RoyaltyTrackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        _atomic_write_text(args.out, rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
