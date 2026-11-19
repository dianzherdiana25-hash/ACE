#!/usr/bin/env python3
"""Pisahkan arus kas terverifikasi per periode dari posisi kumulatif program.

Masukan verifikasi memakai objek `ace.income-verification.v1` dari B4.
Hanya peristiwa COCOK PENUH dengan tanggal mutasi dalam periode yang
menyumbang `verified_rupiah`. Minggu dimulai Senin, bulan dimulai pada
tanggal satu, dan keduanya dihitung sampai tanggal --as-of inklusif.

Ledger JSON memakai schema `ace.income-ledger.v1`, `as_of` (YYYY-MM-DD),
serta field opsional rupiah bulat nonnegatif `income_total_rupiah`,
`operating_cost_rupiah`, `initial_debt_target_rupiah`, dan
`initial_debt_paid_rupiah`. Nilai yang belum diketahui boleh null.
Tanggal snapshot harus sama dengan --as-of.

Ekstrak ledger Markdown dapat menggunakan baris "Tanggal posisi:
YYYY-MM-DD", "Total keseluruhan TUNAI terverifikasi: Rp …",
"Total biaya operasional ACE: Rp …", serta baris total utang dengan
bentuk "| Total | target | — | terbayar | sisa | persen% |".
Format rupiah mendukung tanda titik ribuan dan label tebal Markdown.
Tanggal dan angka yang tidak tersedia dilaporkan TIDAK TAHU.

Posisi biaya memakai total kas ledger dikurangi biaya operasional.
Posisi utang memakai pembayaran aktual yang dicatat ledger. Kas yang
sama bisa muncul di ledger dan verifikasi, jadi total periode tidak
ditambahkan lagi ke posisi ledger. Laporan dicetak ke stdout.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
import re

if __package__:
    from .revenue_report import _rupiah, _validated_events
    from .revenue_verify import RESULT_SCHEMA, _unique_fields
else:
    from revenue_report import _rupiah, _validated_events
    from revenue_verify import RESULT_SCHEMA, _unique_fields


INCOME_SCHEMA = "ace.income-verification.v1"
LEDGER_SCHEMA = "ace.income-ledger.v1"
LEDGER_AMOUNTS = (
    "income_total_rupiah",
    "operating_cost_rupiah",
    "initial_debt_target_rupiah",
    "initial_debt_paid_rupiah",
)
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
RUPIAH_PATTERN = re.compile(r"[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+")


@dataclass(frozen=True)
class LedgerPosition:
    as_of: date | None = None
    income_total_rupiah: int | None = None
    operating_cost_rupiah: int | None = None
    initial_debt_target_rupiah: int | None = None
    initial_debt_paid_rupiah: int | None = None


def _date(value: object, label: str) -> date:
    if isinstance(value, str) and DATE_PATTERN.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(f"{label} wajib tanggal sah dengan format YYYY-MM-DD.")


def _parse_ledger_json(text: str) -> LedgerPosition:
    obj = json.loads(text, object_pairs_hook=_unique_fields)
    if (not isinstance(obj, dict) or obj.get("schema") != LEDGER_SCHEMA
            or obj.keys() - {"schema", "as_of", *LEDGER_AMOUNTS}):
        raise ValueError(f"Diperlukan objek ledger {LEDGER_SCHEMA}.")
    as_of = _date(obj.get("as_of"), "as_of ledger")
    amounts = {name: obj.get(name) for name in LEDGER_AMOUNTS}
    for name, amount in amounts.items():
        if amount is not None and (type(amount) is not int or amount < 0):
            raise ValueError(f"{name} wajib rupiah bulat nonnegatif atau null.")
    return LedgerPosition(as_of, **amounts)


def _markdown_rupiah(text: str, label: str) -> int:
    if not RUPIAH_PATTERN.fullmatch(text):
        raise ValueError(f"{label} wajib rupiah bulat dengan pemisah ribuan opsional.")
    return int(text.replace(".", ""))


def _parse_ledger_markdown(text: str) -> LedgerPosition:
    labels = {
        "Tanggal posisi": "as_of",
        "Total keseluruhan TUNAI terverifikasi": "income_total_rupiah",
        "Total biaya operasional ACE": "operating_cost_rupiah",
    }
    values = {}

    def register(name, value):
        if name in values:
            raise ValueError(f"Field ledger Markdown {name} ganda.")
        values[name] = value

    for raw in text.splitlines():
        line = raw.replace("**", "").strip().removeprefix("- ").strip()
        label, sep, value = line.partition(":")
        if sep and label in labels:
            key = labels[label]
            value = value.strip()
            if key == "as_of":
                register(key, _date(value, "tanggal posisi ledger"))
            else:
                if not value.startswith("Rp"):
                    raise ValueError(f"{label} wajib memakai satuan Rp.")
                register(key, _markdown_rupiah(value[2:].strip(), label))
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line[1:-1].split("|")]
            if len(cells) == 6 and cells[0] == "Total" and cells[2] == "—" and cells[5].endswith("%"):
                target = _markdown_rupiah(cells[1], "target utang awal")
                paid = _markdown_rupiah(cells[3], "utang awal dibayar")
                remaining = _markdown_rupiah(cells[4], "sisa utang awal")
                if remaining != max(0, target - paid):
                    raise ValueError("Sisa utang pada ledger tidak konsisten dengan target dan pembayaran.")
                register("initial_debt_target_rupiah", target)
                register("initial_debt_paid_rupiah", paid)
    if not values:
        raise ValueError("Ledger Markdown tidak memuat field yang dikenali.")
    return LedgerPosition(**values)


def read_ledger(path: Path) -> LedgerPosition:
    """Muat snapshot posisi tanpa membuat berkas keluaran di sekitar ledger."""
    if path.suffix.lower() == ".json":
        return _parse_ledger_json(path.read_text(encoding="utf-8"))
    if path.suffix.lower() == ".md":
        return _parse_ledger_markdown(path.read_text(encoding="utf-8"))
    raise ValueError("Gunakan ledger .json atau .md.")


def _position_amount(value: int | None) -> str:
    return "TIDAK TAHU" if value is None else _rupiah(value)


def _shortfall(target: int | None, amount: int | None) -> int | None:
    return max(0, target - amount) if target is not None and amount is not None else None


def render_income_report(result: dict, ledger: LedgerPosition, *, period: str, as_of: date) -> str:
    """Ringkas nominal B4 pada tanggal mutasi dan ukur posisi ledger pada tanggal laporan."""
    if period == "weekly":
        start = as_of - timedelta(days=as_of.weekday())
        label = "mingguan"
    elif period == "monthly":
        start = as_of.replace(day=1)
        label = "bulanan"
    else:
        raise ValueError("Gunakan periode weekly atau monthly.")
    if ledger.as_of is not None and ledger.as_of != as_of:
        raise ValueError("Tanggal posisi ledger harus sama dengan --as-of.")
    if not isinstance(result, dict) or result.get("schema") != INCOME_SCHEMA:
        raise ValueError(f"Laporan verifikasi harus ber-skema {INCOME_SCHEMA}.")
    events = _validated_events({**result, "schema": RESULT_SCHEMA})
    totals = Counter()
    matching = 0
    for index, event in enumerate(events, 1):
        if event["status"] != "COCOK PENUH":
            continue
        settled = _date(event.get("statement_date"), f"statement_date peristiwa #{index}")
        if start <= settled <= as_of:
            totals[event["rail"]] += event["verified_rupiah"]
            matching += 1

    operating_shortfall = _shortfall(ledger.operating_cost_rupiah, ledger.income_total_rupiah)
    debt_shortfall = _shortfall(ledger.initial_debt_target_rupiah, ledger.initial_debt_paid_rupiah)
    lines = [
        f"# Laporan pendapatan {label}",
        "",
        f"- Periode mutasi — {start.isoformat()} s.d. {as_of.isoformat()}",
        f"- Peristiwa cocok penuh dalam periode — {matching}",
        f"- Total masuk terverifikasi periode — {_rupiah(sum(totals.values()))}",
        "",
        "## Masuk terverifikasi per rel",
        "",
    ]
    if totals:
        lines.extend(f"- `{rail}` — {_rupiah(totals[rail])}" for rail in sorted(totals))
    else:
        lines.append("Belum ada bukti cocok penuh dalam periode dari berkas verifikasi ini.")
    lines.extend([
        "",
        "## Posisi kumulatif dari ledger",
        "",
        f"- Tanggal posisi ledger — {ledger.as_of.isoformat() if ledger.as_of else 'TIDAK TAHU'}",
        "",
        "### 1. Cakupan biaya operasional ACE",
        "",
        f"- Kas terverifikasi — {_position_amount(ledger.income_total_rupiah)}",
        f"- Biaya operasional — {_position_amount(ledger.operating_cost_rupiah)}",
        f"- Sisa menuju cakupan biaya — {_position_amount(operating_shortfall)}",
        "",
        "### 2. Penebusan utang awal",
        "",
        f"- Target utang awal — {_position_amount(ledger.initial_debt_target_rupiah)}",
        f"- Dibayar menurut ledger — {_position_amount(ledger.initial_debt_paid_rupiah)}",
        f"- Sisa target utang awal — {_position_amount(debt_shortfall)}",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verification", type=Path, help="JSON keluaran income_verify.py")
    parser.add_argument("ledger", type=Path, help="Snapshot ledger .json atau .md")
    parser.add_argument("--period", choices=("weekly", "monthly"), default="monthly")
    parser.add_argument("--as-of", required=True, help="Tanggal akhir laporan (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    try:
        as_of = _date(args.as_of, "--as-of")
        result = json.loads(args.verification.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
        report = render_income_report(result, read_ledger(args.ledger), period=args.period, as_of=as_of)
    except (OSError, UnicodeError, json.JSONDecodeError):
        parser.exit(2, "Error membaca verifikasi atau ledger.\n")
    except ValueError as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
