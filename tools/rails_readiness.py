"""Daftar periksa kesiapan rel pembayaran fixture-only (KBM, SeaBank, GoPay, QRIS) (AG54).

Menyediakan struktur data deklaratif, deteksi kedaluwarsa verifikasi
(``stale`` bila usia melebihi ``--max-age-days``), penjaga anti nomor rekening
mentah, serta perender checklist Markdown dan JSON. Data bawaan murni fixture
luring tanpa rekening pribadi ataupun eksekusi transaksi nyata.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.rails-readiness.v1"
DEFAULT_MAX_AGE_DAYS = 90
EXPECTED_RAIL_IDS: tuple[str, ...] = ("kbm", "seabank", "gopay", "qris")

_RAW_ACCOUNT_DIGIT_RE = re.compile(r"\b\d{10,20}\b")
_FORBIDDEN_KEY_RE = re.compile(
    r"(?i)^(account|account_number|no_rekening|rekening|iban|card_number)$"
)


def _assert_no_raw_account_leak(obj: Any, *, path: str = "$") -> None:
    if isinstance(obj, Mapping):
        for key, val in obj.items():
            if isinstance(key, str) and _FORBIDDEN_KEY_RE.match(key.strip()):
                raise ValueError(f"Field nomor rekening terlarang terdeteksi pada {path}.{key}")
            _assert_no_raw_account_leak(val, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _assert_no_raw_account_leak(item, path=f"{path}[{idx}]")
    elif isinstance(obj, str):
        if _RAW_ACCOUNT_DIGIT_RE.search(obj):
            raise ValueError(f"Deret digit menyerupai nomor rekening mentah terlarang pada {path}")


def default_fixture_rails() -> list[dict[str, Any]]:
    """Kembalikan paket fixture metadata untuk KBM, SeaBank, GoPay, dan QRIS."""
    return [
        {
            "rail_id": "kbm",
            "name": "KBM App Royalty",
            "requirements": [
                "Akun penulis terverifikasi (fixture)",
                "Ambang minimum penarikan Rp15.000",
                "Tujuan transfer terhubung ke SeaBank (tanpa nomor mentah di repo)",
            ],
            "fees": "Potongan admin/platform mengikuti ketentuan KBM (fixture luring)",
            "payout_schedule": "Periode pengajuan pencairan mengikuti jadwal platform setelah >= Rp15.000",
            "source": "fixture:SPESIFIKASI_WS2_REL_DAN_BUKTI",
            "verified_date": "2026-11-01",
        },
        {
            "rail_id": "seabank",
            "name": "SeaBank Settlement",
            "requirements": [
                "Rekening tujuan atas nama penerima terverifikasi di luar repo",
                "Mutasi/statement untuk rekonsiliasi sisi penerima",
            ],
            "fees": "Biaya transfer masuk/BI-FAST Rp0 (mengikuti ketentuan umum bank, fixture)",
            "payout_schedule": "Settlement real-time/hari kerja tergantung rel sumber",
            "source": "fixture:SPESIFIKASI_WS2_REL_DAN_BUKTI",
            "verified_date": "2026-11-01",
        },
        {
            "rail_id": "gopay",
            "name": "GoPay Wallet",
            "requirements": [
                "Dompet terverifikasi KYC (fixture)",
                "Referensi transaksi dicocokkan lewat statement/bukti ekspor",
            ],
            "fees": "Biaya transfer bank sesuai tarif e-wallet berlaku (fixture)",
            "payout_schedule": "Pencairan ke rekening bank on-demand atau terjadwal (fixture)",
            "source": "fixture:SPESIFIKASI_WS2_REL_DAN_BUKTI",
            "verified_date": "2026-11-01",
        },
        {
            "rail_id": "qris",
            "name": "QRIS Merchant",
            "requirements": [
                "NMID merchant terverifikasi di luar repo",
                "Catatan MDR dan settlement harian tersimpan pada bukti rekonsiliasi",
            ],
            "fees": "MDR kategori usaha sesuai ketentuan QRIS berlaku (fixture)",
            "payout_schedule": "Settlement T+1 hari kerja ke rekening settlement (fixture)",
            "source": "fixture:SPESIFIKASI_WS2_REL_DAN_BUKTI",
            "verified_date": "2026-11-01",
        },
    ]


def _parse_iso_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def evaluate_rails_readiness(
    rails: Sequence[Mapping[str, Any]],
    *,
    as_of: date | str,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, Any]:
    """Evaluasi kelengkapan syarat & kesegaran verifikasi tiap rel pembayaran."""
    if max_age_days < 0:
        raise ValueError("max_age_days tidak boleh negatif")
    as_of_date = _parse_iso_date(as_of)
    if as_of_date is None:
        raise ValueError(f"Tanggal acuan as_of tidak sah (wajib YYYY-MM-DD): {as_of!r}")

    _assert_no_raw_account_leak(list(rails))

    results: list[dict[str, Any]] = []
    stale_rails: list[str] = []
    incomplete_rails: list[str] = []

    for idx, rail in enumerate(rails):
        if not isinstance(rail, Mapping):
            raise ValueError(f"Entri rel[{idx}] wajib berupa objek JSON")
        rail_id = str(rail.get("rail_id") or rail.get("id") or "").strip().lower()
        if not rail_id:
            raise ValueError(f"Entri rel[{idx}] wajib memiliki rail_id")
        name = str(rail.get("name") or rail_id)

        reqs = rail.get("requirements")
        req_list = [str(r).strip() for r in reqs if str(r).strip()] if isinstance(reqs, list) else []
        fees = rail.get("fees")
        payout_schedule = rail.get("payout_schedule")
        source = rail.get("source")

        missing_fields: list[str] = []
        if not req_list:
            missing_fields.append("requirements")
        if not fees or (isinstance(fees, str) and not fees.strip()):
            missing_fields.append("fees")
        if not isinstance(payout_schedule, str) or not payout_schedule.strip():
            missing_fields.append("payout_schedule")
        if not isinstance(source, str) or not source.strip():
            missing_fields.append("source")

        verified_raw = rail.get("verified_date")
        verified_dt = _parse_iso_date(verified_raw)
        if verified_dt is None:
            age_days: int | None = None
            staleness_status = "unverified"
            stale = True
        else:
            age_days = (as_of_date - verified_dt).days
            if age_days < 0:
                staleness_status = "future_date_invalid"
                stale = True
            elif age_days > max_age_days:
                staleness_status = "stale"
                stale = True
            else:
                staleness_status = "fresh"
                stale = False

        complete = len(missing_fields) == 0
        ready = complete and not stale
        if stale:
            stale_rails.append(rail_id)
        if not complete:
            incomplete_rails.append(rail_id)

        results.append(
            {
                "rail_id": rail_id,
                "name": name,
                "requirements": req_list,
                "fees": fees if fees is not None else "",
                "payout_schedule": str(payout_schedule or ""),
                "source": str(source or ""),
                "verified_date": verified_dt.isoformat() if verified_dt else None,
                "age_days": age_days,
                "staleness_status": staleness_status,
                "stale": stale,
                "complete": complete,
                "missing_fields": missing_fields,
                "ready": ready,
            }
        )

    present_ids = {row["rail_id"] for row in results}
    missing_expected = [rid for rid in EXPECTED_RAIL_IDS if rid not in present_ids]

    return {
        "schema": SCHEMA,
        "as_of": as_of_date.isoformat(),
        "max_age_days": max_age_days,
        "summary": {
            "total_rails": len(results),
            "ready_rails": sum(1 for r in results if r["ready"]),
            "stale_rails": stale_rails,
            "incomplete_rails": incomplete_rails,
            "missing_expected_rails": missing_expected,
            "all_ready": (
                len(stale_rails) == 0
                and len(incomplete_rails) == 0
                and len(missing_expected) == 0
            ),
        },
        "rails": results,
    }


def render_checklist_markdown(report: Mapping[str, Any]) -> str:
    """Render daftar periksa kesiapan rel pembayaran dalam format Markdown."""
    lines = [
        "# Checklist Kesiapan Rel Pembayaran (Fixture Luring)",
        "",
        f"- Tanggal evaluasi (`as_of`): `{report['as_of']}`",
        f"- Batas kesegaran (`max_age_days`): {report['max_age_days']} hari",
        f"- Siap penuh: `{report['summary']['all_ready']}`",
        "",
        "| Rel | Nama | Verified Date | Usia (hari) | Status Kesegaran | Lengkap | Siap |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rail in report.get("rails", []):
        vdate = rail.get("verified_date") or "belum diverifikasi"
        age = rail.get("age_days") if rail.get("age_days") is not None else "-"
        lines.append(
            f"| {rail['rail_id']} | {rail['name']} | {vdate} | {age} | "
            f"{rail['staleness_status']} | {rail['complete']} | {rail['ready']} |"
        )

    for rail in report.get("rails", []):
        lines.extend(
            [
                "",
                f"## {rail['name']} (`{rail['rail_id']}`)",
                f"- Sumber: `{rail['source']}`",
                f"- Biaya: {rail['fees']}",
                f"- Jadwal pencairan: {rail['payout_schedule']}",
                "- Syarat:",
            ]
        )
        for req in rail.get("requirements", []):
            lines.append(f"  - [ ] {req}")

    return "\n".join(lines) + "\n"


def _load_rails(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(obj, list):
        return [dict(x) for x in obj]
    if isinstance(obj, Mapping) and isinstance(obj.get("rails"), list):
        return [dict(x) for x in obj["rails"]]
    raise ValueError(f"Format JSON rails tidak sah: {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluasi dan render checklist kesiapan rel pembayaran fixture (KBM/SeaBank/GoPay/QRIS)."
    )
    parser.add_argument("--rails", help="Path JSON daftar rel opsional (default: fixture bawaan).")
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Tanggal evaluasi YYYY-MM-DD (default: hari ini).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Ambang maksimal umur verifikasi dalam hari (default: {DEFAULT_MAX_AGE_DAYS}).",
    )
    parser.add_argument("--out-json", help="Tulis output JSON ke path ini.")
    parser.add_argument("--out-md", help="Tulis checklist Markdown ke path ini.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format stdout saat --out-json/--out-md tidak diberikan.",
    )
    args = parser.parse_args(argv)

    try:
        rails = _load_rails(Path(args.rails)) if args.rails else default_fixture_rails()
        report = evaluate_rails_readiness(
            rails, as_of=args.as_of, max_age_days=args.max_age_days
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    md_text = render_checklist_markdown(report)

    if args.out_json:
        p = Path(args.out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_text, encoding="utf-8")
    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md_text, encoding="utf-8")
    if not args.out_json and not args.out_md:
        sys.stdout.write(json_text if args.format == "json" else md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
