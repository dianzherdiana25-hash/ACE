#!/usr/bin/env python3
"""Rekonsiler buku kas lokal terhadap laporan verifikasi WS-2 (`ace.revenue-reconcile.v1`).

Membandingkan entri pemasukan dari buku kas JSON (kompatibel dengan skema
`projects/pengelola_keuangan/data_keuangan.json` serta field opsional `event_id`/`rail`)
terhadap laporan `ace.revenue-verification.v1`. Menandai klaim ganda, peristiwa
belum `COCOK PENUH`, selisih nominal, pemasukan buku tanpa tautan bukti, serta
peristiwa terverifikasi yang belum dicatat ke buku kas.

Zero panggilan jaringan & zero eksekusi pembayaran.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
from typing import Any

RECONCILE_SCHEMA = "ace.revenue-reconcile.v1"
VERIFICATION_SCHEMA = "ace.revenue-verification.v1"
VALID_RAILS = frozenset({"kbm_seabank", "fastwork_bank", "gopay_qris"})

_RAW_ACCOUNT_DIGIT_RE = re.compile(r"\b\d{10,20}\b")
_FORBIDDEN_KEY_RE = re.compile(r"(?i)^(account|account_number|no_rekening|rekening|iban|card_number)$")


class ReconcileError(ValueError):
    """Kesalahan skema masukan, pelanggaran kerahasiaan rekening, atau argumen CLI."""


def _assert_no_raw_account(obj: Any, *, path: str = "$") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _FORBIDDEN_KEY_RE.match(k.strip()):
                raise ReconcileError(f"Field nomor rekening dilarang pada {path}.{k}")
            _assert_no_raw_account(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _assert_no_raw_account(item, path=f"{path}[{idx}]")
    elif isinstance(obj, str) and _RAW_ACCOUNT_DIGIT_RE.search(obj):
        raise ReconcileError(f"Terdeteksi angka panjang menyerupai nomor rekening pada {path}.")


def _to_rupiah_int(raw: Any, *, label: str) -> int:
    if isinstance(raw, bool):
        raise ReconcileError(f"{label} tidak boleh boolean.")
    try:
        dec = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ReconcileError(f"{label} bukan nominal angka sah: {raw!r}") from exc
    if not dec.is_finite() or dec <= 0:
        raise ReconcileError(f"{label} wajib lebih besar dari 0: {raw!r}")
    if dec != int(dec):
        raise ReconcileError(f"{label} wajib rupiah bulat (tanpa pecahan desimal): {raw!r}")
    return int(dec)


def _normalize_ledger_entries(raw_ledger: Any) -> tuple[list[dict[str, Any]], int, int]:
    """Muat daftar entri JSON (`list` atau `{\"entries\": [...]}`), pisahkan PEMASUKAN & PENGELUARAN."""
    if isinstance(raw_ledger, dict):
        items = raw_ledger.get("entries")
        if not isinstance(items, list):
            raise ReconcileError("Objek buku kas JSON wajib memiliki daftar `entries`.")
    elif isinstance(raw_ledger, list):
        items = raw_ledger
    else:
        raise ReconcileError("Buku kas wajib berupa daftar JSON atau objek ber-field `entries`.")

    _assert_no_raw_account(items, path="ledger")
    incomes: list[dict[str, Any]] = []
    expense_count = 0
    expense_total = 0

    for idx, entry in enumerate(items, start=1):
        if not isinstance(entry, dict):
            raise ReconcileError(f"Entri buku kas #{idx} bukan objek.")
        tipe = str(entry.get("tipe") or entry.get("type") or "").strip().upper()
        if tipe == "PENGELUARAN":
            amt = _to_rupiah_int(entry.get("nominal", entry.get("amount_rupiah")), label=f"nominal#{idx}")
            expense_count += 1
            expense_total += amt
            continue
        if tipe != "PEMASUKAN":
            raise ReconcileError(f"Entri #{idx} memiliki tipe tidak dikenal: {tipe!r} (harus PEMASUKAN/PENGELUARAN).")

        entry_id = entry.get("id", idx)
        amt = _to_rupiah_int(entry.get("nominal", entry.get("amount_rupiah")), label=f"nominal#{idx}")
        ev_id = entry.get("event_id")
        if ev_id is not None and (not isinstance(ev_id, str) or not ev_id.strip()):
            raise ReconcileError(f"Entri #{idx} event_id tidak sah.")
        rail = entry.get("rail")
        if rail is not None and (not isinstance(rail, str) or not rail.strip()):
            raise ReconcileError(f"Entri #{idx} rail tidak sah.")

        incomes.append(
            {
                "ledger_id": str(entry_id),
                "deskripsi": str(entry.get("deskripsi") or ""),
                "kategori": str(entry.get("kategori") or ""),
                "nominal_rupiah": amt,
                "event_id": ev_id.strip() if isinstance(ev_id, str) else None,
                "rail": rail.strip() if isinstance(rail, str) else None,
            }
        )

    return incomes, expense_count, expense_total


def reconcile_ledger(ledger_payload: Any, verification_payload: Any) -> dict[str, Any]:
    """Rekonsiliasi entri pemasukan buku kas terhadap laporan `ace.revenue-verification.v1`."""
    _assert_no_raw_account(verification_payload, path="verification")
    if (
        not isinstance(verification_payload, dict)
        or verification_payload.get("schema") != VERIFICATION_SCHEMA
        or not isinstance(verification_payload.get("events"), list)
    ):
        raise ReconcileError(f"Laporan verifikasi wajib ber-schema `{VERIFICATION_SCHEMA}` dengan daftar `events`.")

    events_by_id: dict[str, dict[str, Any]] = {}
    for idx, ev in enumerate(verification_payload["events"], start=1):
        if not isinstance(ev, dict):
            raise ReconcileError(f"Peristiwa verifikasi #{idx} bukan objek.")
        eid = ev.get("id")
        if not isinstance(eid, str) or not eid or eid in events_by_id:
            raise ReconcileError(f"ID peristiwa verifikasi #{idx} tidak sah atau ganda.")
        events_by_id[eid] = ev

    incomes, expense_count, expense_total = _normalize_ledger_entries(ledger_payload)

    claims_per_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for inc in incomes:
        if inc["event_id"]:
            claims_per_event[inc["event_id"]].append(inc)

    records: list[dict[str, Any]] = []
    verified_claimed_events: set[str] = set()
    discrepancy_count = 0
    reconciled_rupiah = 0
    claimed_rupiah = sum(i["nominal_rupiah"] for i in incomes)

    for inc in incomes:
        eid = inc["event_id"]
        if not eid:
            discrepancy_count += 1
            records.append(
                {
                    **inc,
                    "reconcile_status": "UNLINKED_LEDGER_INCOME",
                    "reason": "Entri pemasukan tidak mencantumkan tautan `event_id` verifikasi.",
                    "verified_rupiah": None,
                }
            )
            continue

        ev = events_by_id.get(eid)
        if ev is None:
            discrepancy_count += 1
            records.append(
                {
                    **inc,
                    "reconcile_status": "UNKNOWN_EVENT_REF",
                    "reason": f"Peristiwa `{eid}` tidak ditemukan pada laporan verifikasi.",
                    "verified_rupiah": None,
                }
            )
            continue

        if len(claims_per_event[eid]) > 1:
            discrepancy_count += 1
            records.append(
                {
                    **inc,
                    "reconcile_status": "DUPLICATE_CLAIM",
                    "reason": f"Peristiwa `{eid}` diklaim oleh {len(claims_per_event[eid])} entri buku kas sekaligus.",
                    "verified_rupiah": ev.get("verified_rupiah"),
                }
            )
            continue

        ev_status = ev.get("status")
        if ev_status != "COCOK PENUH":
            discrepancy_count += 1
            records.append(
                {
                    **inc,
                    "reconcile_status": "UNVERIFIED_PARTIAL_OR_MISSING",
                    "event_status": ev_status,
                    "reason": f"Status peristiwa `{eid}` adalah `{ev_status}`, bukan `COCOK PENUH`.",
                    "verified_rupiah": None,
                }
            )
            continue

        ev_amt = ev.get("verified_rupiah")
        if type(ev_amt) is not int or ev_amt <= 0:
            raise ReconcileError(f"Nominal terverifikasi peristiwa `{eid}` tidak valid untuk status COCOK PENUH.")

        if inc["rail"] is not None and inc["rail"] != ev.get("rail"):
            discrepancy_count += 1
            records.append(
                {
                    **inc,
                    "reconcile_status": "RAIL_MISMATCH",
                    "event_status": ev_status,
                    "reason": f"Rel buku kas `{inc['rail']}` berbeda dari rel terverifikasi `{ev.get('rail')}`.",
                    "verified_rupiah": ev_amt,
                }
            )
            continue

        if inc["nominal_rupiah"] != ev_amt:
            discrepancy_count += 1
            records.append(
                {
                    **inc,
                    "reconcile_status": "AMOUNT_MISMATCH",
                    "event_status": ev_status,
                    "reason": f"Nominal buku Rp{inc['nominal_rupiah']:,} != terverifikasi Rp{ev_amt:,}.",
                    "verified_rupiah": ev_amt,
                }
            )
            continue

        verified_claimed_events.add(eid)
        reconciled_rupiah += ev_amt
        records.append(
            {
                **inc,
                "reconcile_status": "RECONCILED",
                "event_status": ev_status,
                "verified_rail": ev.get("rail"),
                "verified_rupiah": ev_amt,
                "reason": None,
            }
        )

    unbooked_verified: list[dict[str, Any]] = []
    for eid in sorted(events_by_id):
        ev = events_by_id[eid]
        if ev.get("status") == "COCOK PENUH" and eid not in claims_per_event:
            discrepancy_count += 1
            unbooked_verified.append(
                {
                    "event_id": eid,
                    "rail": ev.get("rail"),
                    "verified_rupiah": ev.get("verified_rupiah"),
                }
            )

    status_counts = Counter(r["reconcile_status"] for r in records)
    total_verified_in_report = sum(
        int(ev["verified_rupiah"])
        for ev in events_by_id.values()
        if ev.get("status") == "COCOK PENUH" and isinstance(ev.get("verified_rupiah"), int)
    )

    clean = discrepancy_count == 0
    return {
        "schema": RECONCILE_SCHEMA,
        "clean": clean,
        "summary": {
            "ledger_income_count": len(incomes),
            "ledger_expense_count": expense_count,
            "ledger_expense_rupiah": expense_total,
            "ledger_claimed_income_rupiah": claimed_rupiah,
            "report_verified_rupiah": total_verified_in_report,
            "reconciled_rupiah": reconciled_rupiah,
            "unbooked_verified_count": len(unbooked_verified),
            "discrepancy_count": discrepancy_count,
            "status_counts": dict(sorted(status_counts.items())),
        },
        "income_records": records,
        "unbooked_verified_events": unbooked_verified,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Laporan Rekonsiliasi Buku Kas vs Verifikasi WS-2",
        "",
        f"- Status Keseluruhan: **{'BERSIH (RECONCILED)' if report['clean'] else 'TERDAPAT SELISIH/KLAIM'}**",
        f"- Total Pemasukan Buku: **Rp{s['ledger_claimed_income_rupiah']:,}** ({s['ledger_income_count']} entri)".replace(",", "."),
        f"- Total Terverifikasi Laporan WS-2: **Rp{s['report_verified_rupiah']:,}**".replace(",", "."),
        f"- Total Terekonsiliasi Penuh: **Rp{s['reconciled_rupiah']:,}**".replace(",", "."),
        f"- Peristiwa Terverifikasi Belum Dibukukan: **{s['unbooked_verified_count']}**",
        f"- Jumlah Temuan / Selisih: **{s['discrepancy_count']}**",
        "",
        "## Rincian Pemasukan Buku Kas",
        "",
        "| ID | Deskripsi | Event ID | Nominal Buku | Status Rekonsiliasi | Catatan |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for r in report["income_records"]:
        amt = f"Rp{r['nominal_rupiah']:,}".replace(",", ".")
        note = (r.get("reason") or "—").replace("|", "\\|")
        ev = r.get("event_id") or "—"
        desc = r["deskripsi"].replace("|", "\\|")
        lines.append(f"| `{r['ledger_id']}` | {desc} | `{ev}` | {amt} | `{r['reconcile_status']}` | {note} |")

    if report["unbooked_verified_events"]:
        lines.extend(["", "## Peristiwa COCOK PENUH Belum Dicatat di Buku Kas", ""])
        for u in report["unbooked_verified_events"]:
            lines.append(f"- `{u['event_id']}` (`{u['rail']}`): Rp{int(u['verified_rupiah']):,}".replace(",", "."))

    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rekonsiliasi buku kas lokal terhadap laporan ace.revenue-verification.v1 (WS-2)."
    )
    parser.add_argument("--ledger", required=True, type=Path, help="Path berkas JSON buku kas.")
    parser.add_argument("--verification", required=True, type=Path, help="Path berkas JSON hasil verifikasi WS-2.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis hasil ke berkas.")
    parser.add_argument("--report-only", action="store_true", help="Selalu keluar 0 walau ditemukan selisih (mode inspeksi).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        verif = json.loads(args.verification.read_text(encoding="utf-8"))
        report = reconcile_ledger(ledger, verif)
        rendered = render_markdown(report) if args.format == "markdown" else (json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        if args.report_only:
            return 0
        return 0 if report["clean"] else 1
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ReconcileError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
