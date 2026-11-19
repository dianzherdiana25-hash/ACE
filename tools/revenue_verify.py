#!/usr/bin/env python3
"""Verifikasi tiga bukti pendapatan lokal sesuai spesifikasi WS-2."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from itertools import combinations
import json
from pathlib import Path
import re

INPUT_SCHEMA = "ace.revenue-evidence.v1"
RESULT_SCHEMA = "ace.revenue-verification.v1"
RAILS = frozenset({"kbm_seabank", "fastwork_bank", "gopay_qris"})
STATUSES = frozenset({"COCOK PENUH", "SEBAGIAN", "HILANG", "REL TAK TERDAFTAR", "TIDAK COCOK"})
ROLES = ("platform", "withdrawal", "statement")
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")
PROVIDERS = {
    "kbm_seabank": {"platform": {"kbm"}, "withdrawal": {"kbm"}, "statement": {"seabank"}},
    "fastwork_bank": {"platform": {"fastwork"}, "withdrawal": {"fastwork"},
                      "statement": {"bank", "seabank"}},
    "gopay_qris": {"platform": {"gopay", "qris"}, "withdrawal": {"gopay", "qris"},
                   "statement": {"gopay", "seabank"}},
}


@dataclass(frozen=True)
class Evidence:
    ref: str
    amount: int
    day: date
    name_matches: bool
    provider_matches: bool
    fee: int | None


def _name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def _evidence(raw: dict, role: str, rail: str, recipient: str) -> Evidence:
    fee_required = role == "withdrawal" and rail == "fastwork_bank"
    fields = {"ref", "amount_rupiah", "date", "recipient", "provider"}
    if fee_required:
        fields.add("fee_rupiah")
    if not isinstance(raw, dict) or raw.keys() - fields:
        raise ValueError(f"Field bukti {role} tidak sah.")
    ref = raw.get("ref")
    if not isinstance(ref, str) or not TOKEN.fullmatch(ref):
        raise ValueError(f"ref pada bukti {role} wajib berupa ID lokal.")
    provider = raw.get("provider")
    if not isinstance(provider, str) or not TOKEN.fullmatch(provider):
        raise ValueError(f"provider pada bukti {role} wajib diisi.")
    amount = raw.get("amount_rupiah")
    if type(amount) is not int or amount <= 0:
        raise ValueError(f"amount_rupiah pada bukti {role} wajib bilangan bulat positif.")
    raw_date = raw.get("date")
    if not isinstance(raw_date, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
        raise ValueError(f"Tanggal pada bukti {role} wajib berbentuk YYYY-MM-DD.")
    try:
        day = date.fromisoformat(raw_date)
    except ValueError:
        raise ValueError(f"Tanggal pada bukti {role} tidak sah.") from None
    name = raw.get("recipient", recipient)
    if not isinstance(name, str) or not _name_key(name):
        raise ValueError(f"Nama penerima pada bukti {role} kosong atau tidak sah.")
    fee = None
    if fee_required and "fee_rupiah" in raw:
        fee = raw["fee_rupiah"]
        if type(fee) is not int or not 0 <= fee < amount:
            raise ValueError("fee_rupiah wajib bilangan bulat dengan 0 ≤ biaya < bruto.")
    return Evidence(ref, amount, day, _name_key(name) == recipient,
                    provider in PROVIDERS[rail][role], fee)


def _classify(legs: dict[str, Evidence], rail: str, max_lag_days: int) -> tuple[str, list[str], int | None]:
    missing = [f"missing:{role}" for role in ROLES if role not in legs]
    withdrawal = legs.get("withdrawal")
    if rail == "fastwork_bank" and withdrawal is not None and withdrawal.fee is None:
        missing.append("missing:withdrawal.fee_rupiah")
    if missing:
        return "HILANG", missing, None

    gross = {role: leg.amount for role, leg in legs.items()}
    if rail == "fastwork_bank":
        gross["statement"] += legs["withdrawal"].fee
    individual_issues = {}
    for role, leg in legs.items():
        issues = []
        if not leg.name_matches:
            issues.append(f"recipient_mismatch:{role}")
        if not leg.provider_matches:
            issues.append(f"provider_mismatch:{role}")
        if rail == "kbm_seabank" and leg.amount < 15_000:
            issues.append(f"below_kbm_minimum:{role}")
        individual_issues[role] = issues

    matched_pairs = []
    issues = [issue for role in ROLES for issue in individual_issues[role]]
    for left, right in combinations(ROLES, 2):
        pair_issues = []
        if gross[left] != gross[right]:
            pair_issues.append(f"amount_mismatch:{left}:{right}")
        delta = (legs[right].day - legs[left].day).days
        if delta < 0:
            pair_issues.append(f"date_order:{left}:{right}")
        if (left, right) == ("withdrawal", "statement") and delta > max_lag_days:
            pair_issues.append("date_lag:withdrawal:statement")
        if not (pair_issues or individual_issues[left] or individual_issues[right]):
            matched_pairs.append((left, right))
        issues.extend(pair_issues)

    if not issues:
        return "COCOK PENUH", [], legs["statement"].amount
    if matched_pairs:
        # Dua pasangan cocok bisa menyisakan konflik pada satu hubungan.
        # Catat kaki yang di luar pasangan hanya bila pasangan cocoknya tunggal.
        if len(matched_pairs) == 1:
            outside = next(role for role in ROLES if role not in matched_pairs[0])
            issues.append(f"unmatched:{outside}")
        return "SEBAGIAN", issues, None
    return "TIDAK COCOK", issues, None


def verify_revenue(payload: dict, *, recipient: str, max_lag_days: int = 14) -> dict:
    """Cocokkan bukti yang ditautkan dengan ID peristiwa pencairan."""
    if type(max_lag_days) is not int or max_lag_days < 0:
        raise ValueError("max_lag_days wajib bilangan bulat nonnegatif.")
    if not isinstance(recipient, str) or not _name_key(recipient):
        raise ValueError("Referensi nama penerima wajib diisi.")
    recipient_key = _name_key(recipient)
    if (not isinstance(payload, dict) or set(payload) != {"schema", "events"}
            or payload["schema"] != INPUT_SCHEMA or not isinstance(payload["events"], list)):
        raise ValueError("Diperlukan objek ace.revenue-evidence.v1 dengan daftar events.")

    results = []
    seen_ids = set()
    seen_refs = set()
    for index, event in enumerate(payload["events"], 1):
        try:
            if not isinstance(event, dict) or event.keys() - {"id", "rail", *ROLES}:
                raise ValueError("Field peristiwa tidak sah.")
            event_id, rail = event.get("id"), event.get("rail")
            if not isinstance(event_id, str) or not TOKEN.fullmatch(event_id) or event_id in seen_ids:
                raise ValueError("ID peristiwa tidak sah atau ganda.")
            if not isinstance(rail, str) or not TOKEN.fullmatch(rail):
                raise ValueError("ID rel tidak sah.")
            seen_ids.add(event_id)
            if rail not in RAILS:
                status, issues, total = "REL TAK TERDAFTAR", ["unregistered_rail"], None
            else:
                legs = {
                    role: _evidence(event[role], role, rail, recipient_key)
                    for role in ROLES if event.get(role) is not None
                }
                for role, leg in legs.items():
                    key = (role, leg.ref)
                    if key in seen_refs:
                        raise ValueError(f"Ref bukti {role} dipakai pada lebih dari satu peristiwa.")
                    seen_refs.add(key)
                status, issues, total = _classify(legs, rail, max_lag_days)
            results.append({"id": event_id, "rail": rail, "status": status,
                            "issues": issues, "verified_rupiah": total})
        except ValueError as exc:
            raise ValueError(f"Peristiwa #{index}. {exc}") from None
    return {"schema": RESULT_SCHEMA, "max_lag_days": max_lag_days,
            "events": sorted(results, key=lambda item: item["id"])}


def _unique_fields(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError("Field JSON ganda.")
    return obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="JSON lokal berisi bukti yang dinormalisasi.")
    parser.add_argument("--recipient-file", type=Path, required=True,
                        help="Berkas teks privat dengan satu nama penerima acuan.")
    parser.add_argument("--max-lag-days", type=int, default=14)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
        recipient = args.recipient_file.read_text(encoding="utf-8").strip()
        if len(recipient.splitlines()) != 1:
            raise ValueError("Berkas penerima wajib memuat satu baris nama.")
        result = verify_revenue(payload, recipient=recipient, max_lag_days=args.max_lag_days)
    except (OSError, UnicodeError, json.JSONDecodeError):
        parser.exit(2, "Error membaca bukti JSON atau acuan penerima.\n")
    except ValueError as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
