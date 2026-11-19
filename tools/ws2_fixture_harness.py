#!/usr/bin/env python3
"""Harness fixture multi-rel & adaptor jembatan WS-2 luring (`ace.ws2-fixture-harness.v1`).

Menyediakan:
1. Pembangkit suite fixture terstruktur berformat `ace.revenue-evidence.v1` untuk
   menguji seluruh aturan `SPESIFIKASI_WS2_REL_DAN_BUKTI.md` (rel `kbm_seabank`,
   `fastwork_bank` berbiaya eksplisit, `gopay_qris`, penolakan `facebook`/rel tak terdaftar,
   kaki hilang `HILANG`, ambang KBM Rp15.000, batas jeda `--max-lag-days`, dan larangan nomor rekening).
2. Pemvalidasi & evaluator luring atas payload bukti maupun laporan `ace.revenue-verification.v1`
   (kompatibel dengan `tools/revenue_verify.py` bila tersedia tanpa memodifikasinya).
3. Adaptor jembatan aman dari CSV royalti (`tools/royalty_track.py`) ke kandidat kaki `platform` KBM.

Zero jaringan live & zero eksekusi pembayaran nyata.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import royalty_track as _royalty_track

HARNESS_SCHEMA = "ace.ws2-fixture-harness.v1"
EVIDENCE_SCHEMA = "ace.revenue-evidence.v1"
VERIFICATION_SCHEMA = "ace.revenue-verification.v1"

ALLOWED_RAILS = frozenset({"kbm_seabank", "fastwork_bank", "gopay_qris"})
ALLOWED_STATUSES = frozenset({"COCOK PENUH", "SEBAGIAN", "HILANG", "REL TAK TERDAFTAR", "TIDAK COCOK"})
ROLES = ("platform", "withdrawal", "statement")
KBM_MIN_PAYOUT_RUPIAH = 15_000
DEFAULT_MAX_LAG_DAYS = 14

PROVIDER_MATRIX = {
    "kbm_seabank": {"platform": {"kbm"}, "withdrawal": {"kbm"}, "statement": {"seabank"}},
    "fastwork_bank": {"platform": {"fastwork"}, "withdrawal": {"fastwork"}, "statement": {"bank", "seabank"}},
    "gopay_qris": {"platform": {"gopay", "qris"}, "withdrawal": {"gopay", "qris"}, "statement": {"gopay", "seabank"}},
}

# Tolak penyisipan nomor rekening mentah (>= 10 digit berturut-turut) di kolom teks manapun
_RAW_ACCOUNT_DIGIT_RE = re.compile(r"\b\d{10,20}\b")
_FORBIDDEN_KEY_RE = re.compile(r"(?i)^(account|account_number|no_rekening|rekening|iban|card_number)$")


class Ws2HarnessError(ValueError):
    """Kesalahan skema fixture, keamanan nomor rekening, atau masukan harness WS-2."""


def _assert_no_raw_account_leak(obj: Any, *, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(key, str) and _FORBIDDEN_KEY_RE.match(key.strip()):
                raise Ws2HarnessError(f"Field nomor rekening dilarang pada {path}.{key}")
            _assert_no_raw_account_leak(val, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _assert_no_raw_account_leak(item, path=f"{path}[{idx}]")
    elif isinstance(obj, str):
        if _RAW_ACCOUNT_DIGIT_RE.search(obj):
            raise Ws2HarnessError(f"Terdeteksi deret angka panjang menyerupai nomor rekening pada {path}.")


def build_reference_fixtures(*, recipient: str = "Dian Herdiana") -> dict[str, Any]:
    """Bangun kumpulan fixture standar mencakup seluruh kasus wajib spesifikasi WS-2."""
    if not isinstance(recipient, str) or not recipient.strip():
        raise Ws2HarnessError("Nama penerima acuan tidak boleh kosong.")
    rec = recipient.strip()

    events: list[tuple[dict[str, Any], str, int | None, str]] = [
        (
            {
                "id": "kbm-full-ok",
                "rail": "kbm_seabank",
                "platform": {"ref": "kbm-plat-01", "amount_rupiah": 150000, "date": "2026-10-31", "provider": "kbm"},
                "withdrawal": {"ref": "kbm-wd-01", "amount_rupiah": 150000, "date": "2026-11-02", "provider": "kbm"},
                "statement": {
                    "ref": "sb-st-01",
                    "amount_rupiah": 150000,
                    "date": "2026-11-05",
                    "provider": "seabank",
                    "recipient": rec,
                },
            },
            "COCOK PENUH",
            150000,
            "Rel 1 KBM -> SeaBank 3 kaki cocok & di atas minimum Rp15.000",
        ),
        (
            {
                "id": "fastwork-net-fee-ok",
                "rail": "fastwork_bank",
                "platform": {"ref": "fw-plat-01", "amount_rupiah": 500000, "date": "2026-11-01", "provider": "fastwork"},
                "withdrawal": {
                    "ref": "fw-wd-01",
                    "amount_rupiah": 500000,
                    "fee_rupiah": 3000,
                    "date": "2026-11-02",
                    "provider": "fastwork",
                },
                "statement": {
                    "ref": "bank-st-01",
                    "amount_rupiah": 497000,
                    "date": "2026-11-04",
                    "provider": "seabank",
                    "recipient": rec,
                },
            },
            "COCOK PENUH",
            497000,
            "Rel 2 Fastwork biaya eksplisit Rp3.000 -> neto Rp497.000",
        ),
        (
            {
                "id": "gopay-qris-full-ok",
                "rail": "gopay_qris",
                "platform": {"ref": "gp-plat-01", "amount_rupiah": 85000, "date": "2026-11-03", "provider": "qris"},
                "withdrawal": {"ref": "gp-wd-01", "amount_rupiah": 85000, "date": "2026-11-03", "provider": "qris"},
                "statement": {
                    "ref": "gp-st-01",
                    "amount_rupiah": 85000,
                    "date": "2026-11-04",
                    "provider": "gopay",
                    "recipient": rec,
                },
            },
            "COCOK PENUH",
            85000,
            "Rel 3 GoPay/QRIS 3 kaki cocok persis",
        ),
        (
            {
                "id": "fastwork-missing-fee",
                "rail": "fastwork_bank",
                "platform": {"ref": "fw-plat-02", "amount_rupiah": 200000, "date": "2026-11-01", "provider": "fastwork"},
                "withdrawal": {"ref": "fw-wd-02", "amount_rupiah": 200000, "date": "2026-11-02", "provider": "fastwork"},
                "statement": {
                    "ref": "bank-st-02",
                    "amount_rupiah": 197000,
                    "date": "2026-11-04",
                    "provider": "bank",
                    "recipient": rec,
                },
            },
            "HILANG",
            None,
            "Fastwork tanpa field eksplisit fee_rupiah wajib status HILANG",
        ),
        (
            {
                "id": "kbm-missing-statement",
                "rail": "kbm_seabank",
                "platform": {"ref": "kbm-plat-02", "amount_rupiah": 45000, "date": "2026-11-01", "provider": "kbm"},
                "withdrawal": {"ref": "kbm-wd-02", "amount_rupiah": 45000, "date": "2026-11-02", "provider": "kbm"},
            },
            "HILANG",
            None,
            "2 dari 3 bukti dengan kaki statement absen -> HILANG",
        ),
        (
            {
                "id": "facebook-unregistered-rail",
                "rail": "facebook",
                "platform": {"ref": "fb-plat-01", "amount_rupiah": 300000, "date": "2026-11-01", "provider": "facebook"},
            },
            "REL TAK TERDAFTAR",
            None,
            "Rel di luar WS-2 (facebook) wajib ditolak sebagai REL TAK TERDAFTAR",
        ),
        (
            {
                "id": "kbm-lag-exceeded",
                "rail": "kbm_seabank",
                "platform": {"ref": "kbm-plat-03", "amount_rupiah": 90000, "date": "2026-10-01", "provider": "kbm"},
                "withdrawal": {"ref": "kbm-wd-03", "amount_rupiah": 90000, "date": "2026-10-02", "provider": "kbm"},
                "statement": {
                    "ref": "sb-st-03",
                    "amount_rupiah": 90000,
                    "date": "2026-10-20",
                    "provider": "seabank",
                    "recipient": rec,
                },
            },
            "SEBAGIAN",
            None,
            "Selisih withdrawal -> statement 18 hari (> default 14 hari) gagal COCOK PENUH",
        ),
        (
            {
                "id": "kbm-below-minimum",
                "rail": "kbm_seabank",
                "platform": {"ref": "kbm-plat-04", "amount_rupiah": 14999, "date": "2026-11-01", "provider": "kbm"},
                "withdrawal": {"ref": "kbm-wd-04", "amount_rupiah": 14999, "date": "2026-11-02", "provider": "kbm"},
                "statement": {
                    "ref": "sb-st-04",
                    "amount_rupiah": 14999,
                    "date": "2026-11-05",
                    "provider": "seabank",
                    "recipient": rec,
                },
            },
            "TIDAK COCOK",
            None,
            "Nominal KBM Rp14.999 di bawah batas minimum Rp15.000",
        ),
    ]

    return {
        "schema": HARNESS_SCHEMA,
        "recipient": rec,
        "max_lag_days": DEFAULT_MAX_LAG_DAYS,
        "evidence_payload": {
            "schema": EVIDENCE_SCHEMA,
            "events": [ev for ev, _, _, _ in events],
        },
        "expectations": [
            {
                "id": ev["id"],
                "rail": ev["rail"],
                "expected_status": exp_status,
                "expected_verified_rupiah": exp_amount,
                "note": note,
            }
            for ev, exp_status, exp_amount, note in events
        ],
    }


def _name_key(val: str) -> str:
    return " ".join(val.split()).casefold()


def evaluate_evidence_offline(
    payload: dict[str, Any],
    *,
    recipient: str,
    max_lag_days: int = DEFAULT_MAX_LAG_DAYS,
) -> dict[str, Any]:
    """Evaluator aturan WS-2 mandiri (selaras skema `ace.revenue-verification.v1`)."""
    if not isinstance(max_lag_days, int) or isinstance(max_lag_days, bool) or max_lag_days < 0:
        raise Ws2HarnessError("max_lag_days wajib bilangan bulat nonnegatif.")
    if not isinstance(recipient, str) or not _name_key(recipient):
        raise Ws2HarnessError("Nama penerima acuan wajib diisi.")
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != EVIDENCE_SCHEMA
        or not isinstance(payload.get("events"), list)
    ):
        raise Ws2HarnessError(f"Payload wajib objek ber-schema `{EVIDENCE_SCHEMA}` dengan daftar `events`.")

    _assert_no_raw_account_leak(payload)
    rec_key = _name_key(recipient)
    seen_ids: set[str] = set()
    seen_refs: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []

    for idx, ev in enumerate(payload["events"], start=1):
        if not isinstance(ev, dict):
            raise Ws2HarnessError(f"Peristiwa #{idx} bukan objek.")
        eid = ev.get("id")
        rail = ev.get("rail")
        if not isinstance(eid, str) or not eid or eid in seen_ids:
            raise Ws2HarnessError(f"Peristiwa #{idx} id tidak sah atau ganda.")
        if not isinstance(rail, str) or not rail:
            raise Ws2HarnessError(f"Peristiwa #{idx} rail tidak sah.")
        seen_ids.add(eid)

        if rail not in ALLOWED_RAILS:
            results.append(
                {
                    "id": eid,
                    "rail": rail,
                    "status": "REL TAK TERDAFTAR",
                    "issues": ["unregistered_rail"],
                    "verified_rupiah": None,
                }
            )
            continue

        legs: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for role in ROLES:
            leg = ev.get(role)
            if leg is None:
                missing.append(f"missing:{role}")
                continue
            if not isinstance(leg, dict):
                raise Ws2HarnessError(f"Peristiwa #{idx} bukti {role} bukan objek.")
            ref = leg.get("ref")
            amt = leg.get("amount_rupiah")
            prov = leg.get("provider")
            raw_day = leg.get("date")
            if not isinstance(ref, str) or not ref:
                raise Ws2HarnessError(f"Peristiwa #{idx} bukti {role} ref tidak sah.")
            if (role, ref) in seen_refs:
                raise Ws2HarnessError(f"Ref bukti {role} dipakai ganda: {ref}")
            seen_refs.add((role, ref))
            if type(amt) is not int or amt <= 0:
                raise Ws2HarnessError(f"Peristiwa #{idx} amount_rupiah {role} wajib int positif.")
            if not isinstance(prov, str) or not prov:
                raise Ws2HarnessError(f"Peristiwa #{idx} provider {role} wajib diisi.")
            if not isinstance(raw_day, str):
                raise Ws2HarnessError(f"Peristiwa #{idx} tanggal {role} wajib YYYY-MM-DD.")
            try:
                parsed_day = date.fromisoformat(raw_day)
            except ValueError as exc:
                raise Ws2HarnessError(f"Peristiwa #{idx} tanggal {role} tidak sah: {raw_day!r}") from exc

            fee_val = leg.get("fee_rupiah")
            if rail == "fastwork_bank" and role == "withdrawal":
                if "fee_rupiah" not in leg or leg.get("fee_rupiah") is None:
                    missing.append("missing:withdrawal.fee_rupiah")
                elif type(fee_val) is not int or not (0 <= fee_val < amt):
                    raise Ws2HarnessError(f"Peristiwa #{idx} fee_rupiah Fastwork tidak sah.")

            rec_leg = leg.get("recipient", recipient)
            if not isinstance(rec_leg, str) or not _name_key(rec_leg):
                raise Ws2HarnessError(f"Peristiwa #{idx} recipient {role} tidak sah.")

            legs[role] = {
                "ref": ref,
                "amount": amt,
                "day": parsed_day,
                "provider": prov,
                "name_matches": _name_key(rec_leg) == rec_key,
                "provider_matches": prov in PROVIDER_MATRIX[rail][role],
                "fee": fee_val if (rail == "fastwork_bank" and role == "withdrawal" and "fee_rupiah" in leg and leg.get("fee_rupiah") is not None) else None,
            }

        if missing:
            results.append(
                {
                    "id": eid,
                    "rail": rail,
                    "status": "HILANG",
                    "issues": missing,
                    "verified_rupiah": None,
                }
            )
            continue

        gross = {role: legs[role]["amount"] for role in ROLES}
        if rail == "fastwork_bank":
            gross["statement"] += int(legs["withdrawal"]["fee"])

        indiv_issues: dict[str, list[str]] = {r: [] for r in ROLES}
        for role in ROLES:
            if not legs[role]["name_matches"]:
                indiv_issues[role].append(f"recipient_mismatch:{role}")
            if not legs[role]["provider_matches"]:
                indiv_issues[role].append(f"provider_mismatch:{role}")
            if rail == "kbm_seabank" and legs[role]["amount"] < KBM_MIN_PAYOUT_RUPIAH:
                indiv_issues[role].append(f"below_kbm_minimum:{role}")

        issues = [i for role in ROLES for i in indiv_issues[role]]
        matched_pairs: list[tuple[str, str]] = []
        for left, right in (("platform", "withdrawal"), ("platform", "statement"), ("withdrawal", "statement")):
            pair_issues: list[str] = []
            if gross[left] != gross[right]:
                pair_issues.append(f"amount_mismatch:{left}:{right}")
            delta = (legs[right]["day"] - legs[left]["day"]).days
            if delta < 0:
                pair_issues.append(f"date_order:{left}:{right}")
            if (left, right) == ("withdrawal", "statement") and delta > max_lag_days:
                pair_issues.append("date_lag:withdrawal:statement")
            if not (pair_issues or indiv_issues[left] or indiv_issues[right]):
                matched_pairs.append((left, right))
            issues.extend(pair_issues)

        if not issues:
            status = "COCOK PENUH"
            verified_rupiah: int | None = legs["statement"]["amount"]
        elif matched_pairs:
            status = "SEBAGIAN"
            if len(matched_pairs) == 1:
                outside = next(r for r in ROLES if r not in matched_pairs[0])
                issues.append(f"unmatched:{outside}")
            verified_rupiah = None
        else:
            status = "TIDAK COCOK"
            verified_rupiah = None

        results.append(
            {
                "id": eid,
                "rail": rail,
                "status": status,
                "issues": issues,
                "verified_rupiah": verified_rupiah,
            }
        )

    results.sort(key=lambda r: r["id"])
    return {
        "schema": VERIFICATION_SCHEMA,
        "max_lag_days": max_lag_days,
        "events": results,
    }


def run_fixture_suite(*, recipient: str = "Dian Herdiana", prefer_revenue_verify: bool = True) -> dict[str, Any]:
    """Jalankan suite fixture terhadap `tools.revenue_verify` (bila ada) & evaluator mandiri."""
    fixture_bundle = build_reference_fixtures(recipient=recipient)
    payload = fixture_bundle["evidence_payload"]
    standalone_res = evaluate_evidence_offline(payload, recipient=recipient, max_lag_days=DEFAULT_MAX_LAG_DAYS)

    upstream_res: dict[str, Any] | None = None
    backend = "standalone"
    if prefer_revenue_verify and importlib.util.find_spec("tools.revenue_verify") is not None:
        rv = importlib.import_module("tools.revenue_verify")
        upstream_res = rv.verify_revenue(payload, recipient=recipient, max_lag_days=DEFAULT_MAX_LAG_DAYS)
        backend = "tools.revenue_verify+standalone"

    actual_by_id = {e["id"]: e for e in standalone_res["events"]}
    upstream_by_id = {e["id"]: e for e in upstream_res["events"]} if upstream_res is not None else None

    checks: list[dict[str, Any]] = []
    passed_count = 0
    for exp in fixture_bundle["expectations"]:
        eid = exp["id"]
        got = actual_by_id[eid]
        ok = got["status"] == exp["expected_status"] and got["verified_rupiah"] == exp["expected_verified_rupiah"]
        upstream_match = True
        if upstream_by_id is not None:
            up = upstream_by_id[eid]
            upstream_match = up["status"] == got["status"] and up["verified_rupiah"] == got["verified_rupiah"]
        if ok and upstream_match:
            passed_count += 1
        checks.append(
            {
                "id": eid,
                "rail": exp["rail"],
                "expected_status": exp["expected_status"],
                "actual_status": got["status"],
                "expected_verified_rupiah": exp["expected_verified_rupiah"],
                "actual_verified_rupiah": got["verified_rupiah"],
                "issues": got["issues"],
                "upstream_agree": upstream_match,
                "passed": bool(ok and upstream_match),
            }
        )

    status_counts = Counter(c["actual_status"] for c in checks)
    return {
        "schema": HARNESS_SCHEMA,
        "backend": backend,
        "all_passed": passed_count == len(checks),
        "total_fixtures": len(checks),
        "passed_fixtures": passed_count,
        "status_counts": dict(sorted(status_counts.items())),
        "checks": checks,
        "verification_output": upstream_res or standalone_res,
    }


def royalty_csv_to_kbm_platform_legs(
    csv_paths: list[Path],
    *,
    payout_date_day: str = "28",
) -> list[dict[str, Any]]:
    """Adaptor aman mengubah ringkasan bulanan `royalty_track.py` menjadi kandidat kaki platform KBM."""
    summary = _royalty_track.summarize_royalties(csv_paths)
    legs: list[dict[str, Any]] = []
    for item in summary["monthly_totals"]:
        month = item["month"]
        idr_str = item["revenue_by_currency"].get("IDR")
        if idr_str is None:
            continue
        amt = int(float(idr_str))
        if amt <= 0:
            continue
        legs.append(
            {
                "month": month,
                "leg": {
                    "ref": f"kbm-royalty-{month}",
                    "amount_rupiah": amt,
                    "date": f"{month}-{payout_date_day}",
                    "provider": "kbm",
                },
                "meets_kbm_minimum": amt >= KBM_MIN_PAYOUT_RUPIAH,
            }
        )
    return legs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Harness fixture multi-rel & validator spesifikasi WS-2 (luring, 0 pembayaran nyata)."
    )
    parser.add_argument("--recipient", default="Dian Herdiana", help="Nama penerima acuan.")
    parser.add_argument("--max-lag-days", type=int, default=DEFAULT_MAX_LAG_DAYS, help="Batas jeda mutasi (default 14).")
    parser.add_argument("--validate-evidence", type=Path, default=None, help="Validasi berkas JSON ace.revenue-evidence.v1.")
    parser.add_argument("--export-fixtures", type=Path, default=None, help="Tulis payload fixture standar ke JSON.")
    parser.add_argument("--royalty-csv", nargs="+", type=Path, default=None, help="Konversi CSV royalti ke kandidat kaki KBM.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.royalty_csv:
            legs = royalty_csv_to_kbm_platform_legs(args.royalty_csv)
            print(json.dumps({"schema": HARNESS_SCHEMA, "kbm_platform_candidates": legs}, ensure_ascii=False, indent=2))
            return 0
        if args.export_fixtures is not None:
            bundle = build_reference_fixtures(recipient=args.recipient)
            args.export_fixtures.parent.mkdir(parents=True, exist_ok=True)
            args.export_fixtures.write_text(json.dumps(bundle["evidence_payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"exported": str(args.export_fixtures), "event_count": len(bundle["evidence_payload"]["events"])}, ensure_ascii=False))
            return 0
        if args.validate_evidence is not None:
            payload = json.loads(args.validate_evidence.read_text(encoding="utf-8"))
            res = evaluate_evidence_offline(payload, recipient=args.recipient, max_lag_days=args.max_lag_days)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0

        report = run_fixture_suite(recipient=args.recipient)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["all_passed"] else 1
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, Ws2HarnessError, _royalty_track.RoyaltyTrackError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
