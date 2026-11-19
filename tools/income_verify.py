#!/usr/bin/env python3
"""Gabungkan tiga berkas bukti lokal agar nominal tak dinilai dari satu sumber.

Setiap berkas UTF-8 memuat array JSON. Tiap objek mewakili satu bukti dan
memerlukan id (ID samaran peristiwa), rail, ref (ID samaran bukti), provider,
date (YYYY-MM-DD), dan amount_rupiah (bilangan bulat positif). recipient
adalah nama opsional. Penarikan Fastwork memerlukan fee_rupiah, termasuk nol
jika gratis. Angka platform/penarikan Fastwork bruto dan angka mutasi neto.
Tidak ada field nomor rekening. ID peristiwa harus sama di ketiga sumber
dan muncul paling banyak sekali dalam tiap berkas. Untuk bukti yang absen,
hilangkan barisnya atau gunakan [] bila seluruh berkas peran kosong.

Rel dan provider mengikuti revenue_verify.py. Kebijakan WS-2 memeriksa
kecocokan nominal, penerima, jenis sumber, urutan tanggal, dan jendela lag.
Keluaran ace.income-verification.v1 mempertahankan verdict WS-2 dan menambah
nominal per bukti serta statement_date untuk periode laporan. Kaki yang absen
bernilai null. Untuk rel tak terdaftar, detail nominal dan tanggal disisihkan.
Acuan penerima dibaca dari berkas privat satu baris. Nama dan ref tidak
disertakan di laporan.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .revenue_verify import INPUT_SCHEMA, RAILS, ROLES, TOKEN, _unique_fields, verify_revenue
else:
    from revenue_verify import INPUT_SCHEMA, RAILS, ROLES, TOKEN, _unique_fields, verify_revenue


RESULT_SCHEMA = "ace.income-verification.v1"
_FIELDS = {"id", "rail", "ref", "provider", "date", "amount_rupiah", "recipient"}


def _group_evidence(platform: list, withdrawal: list, statement: list) -> dict[str, dict]:
    events = {}
    for role, rows in zip(ROLES, (platform, withdrawal, statement), strict=True):
        if not isinstance(rows, list):
            raise ValueError(f"Bukti {role} wajib berupa array JSON.")
        fields = _FIELDS | {"fee_rupiah"} if role == "withdrawal" else _FIELDS
        for index, row in enumerate(rows, 1):
            where = f"Bukti {role} baris {index}"
            if not isinstance(row, dict) or row.keys() - fields:
                raise ValueError(f"{where} memiliki field yang tidak sah.")
            event_id, rail = row.get("id"), row.get("rail")
            if (not isinstance(event_id, str) or not TOKEN.fullmatch(event_id)
                    or not isinstance(rail, str) or not TOKEN.fullmatch(rail)):
                raise ValueError(f"{where} memerlukan id samaran dan rail.")
            event = events.setdefault(event_id, {"id": event_id, "rail": rail})
            if event["rail"] != rail or role in event:
                raise ValueError(f"{where} memiliki id ganda atau rail yang bertentangan.")
            event[role] = {field: value for field, value in row.items() if field not in {"id", "rail"}}
    return events


def verify_income(
    *, platform: list, withdrawal: list, statement: list, recipient: str, max_lag_days: int = 14,
) -> dict:
    """Gunakan verifikator WS-2 setelah menyatukan ID lintas sumber."""
    events = _group_evidence(platform, withdrawal, statement)
    result = verify_revenue(
        {"schema": INPUT_SCHEMA, "events": list(events.values())},
        recipient=recipient, max_lag_days=max_lag_days,
    )
    for row in result["events"]:
        event = events[row["id"]] if row["rail"] in RAILS else {}
        row["statement_date"] = event.get("statement", {}).get("date")
        row["amounts_rupiah"] = {
            role: event.get(role, {}).get("amount_rupiah") for role in ROLES
        }
    return {**result, "schema": RESULT_SCHEMA}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for role in ROLES:
        parser.add_argument(f"--{role}", required=True, type=Path, help=f"Array JSON bukti {role}.")
    parser.add_argument("--recipient-file", required=True, type=Path,
                        help="Berkas privat berisi nama penerima acuan.")
    parser.add_argument("--max-lag-days", type=int, default=14)
    args = parser.parse_args(argv)
    try:
        sources = {
            role: json.loads(getattr(args, role).read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
            for role in ROLES
        }
        recipient = args.recipient_file.read_text(encoding="utf-8").strip()
        if len(recipient.splitlines()) != 1:
            raise ValueError("Berkas penerima wajib memuat satu baris nama.")
        report = verify_income(**sources, recipient=recipient, max_lag_days=args.max_lag_days)
    except (OSError, UnicodeError, json.JSONDecodeError):
        parser.exit(2, "Error membaca bukti JSON atau acuan penerima.\n")
    except ValueError as exc:
        parser.exit(2, f"Error: {exc}\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
