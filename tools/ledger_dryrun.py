"""Rekonsiliasi dry-run CSV transaksi simulasi vs laporan platform simulasi (AG55).

Membandingkan berkas CSV buku catatan simulasi (``name,platform,amount,proof_id``)
terhadap laporan platform simulasi (JSON/JSONL/CSV) berdasar tuple kunci
``(name, platform, amount, proof_id)``. Melaporkan baris cocok serta entri
yatim (orphan) dari kedua sisi tanpa pernah menyentuh ``LEDGER_PENGHASILAN.md``
ataupun data live.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.ledger-dryrun.v1"
REQUIRED_FIELDS: tuple[str, ...] = ("name", "platform", "amount", "proof_id")
_RAW_ACCOUNT_DIGIT_RE = re.compile(r"\b\d{10,20}\b")


def _normalize_text(value: Any, field: str, idx: int) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"Baris ke-{idx} memiliki field '{field}' kosong")
    text = " ".join(str(value).strip().split())
    if _RAW_ACCOUNT_DIGIT_RE.search(text):
        raise ValueError(f"Baris ke-{idx} field '{field}' menyerupai nomor rekening terlarang")
    return text


def _parse_amount(value: Any, idx: int) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Baris ke-{idx} memiliki 'amount' tidak sah: {value!r}")
    raw = str(value).strip()
    if not raw:
        raise ValueError(f"Baris ke-{idx} memiliki 'amount' kosong")
    try:
        dec = Decimal(raw).normalize()
    except InvalidOperation as exc:
        raise ValueError(f"Baris ke-{idx} gagal parse 'amount' ({raw!r}): {exc}") from exc
    if dec <= 0:
        raise ValueError(f"Baris ke-{idx} wajib memiliki 'amount' positif: {raw!r}")
    # Kanonisasi angka agar 150000 dan 150000.00 cocok konsisten.
    return format(dec, "f").rstrip("0").rstrip(".") if "." in format(dec, "f") else format(dec, "f")


def _row_key(row: Mapping[str, Any], idx: int) -> tuple[str, str, str, str]:
    name = _normalize_text(row.get("name"), "name", idx).lower()
    platform = _normalize_text(row.get("platform"), "platform", idx).lower()
    amount = _parse_amount(row.get("amount"), idx)
    proof_id = _normalize_text(row.get("proof_id"), "proof_id", idx)
    return (name, platform, amount, proof_id)


def load_ledger_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Muat transaksi simulasi dari berkas CSV."""
    with Path(csv_path).open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"CSV ledger tanpa header: {csv_path}")
        missing = [col for col in REQUIRED_FIELDS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"Header CSV ledger kurang kolom wajib {missing}: {csv_path}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError(f"CSV ledger kosong tanpa baris transaksi: {csv_path}")
    return rows


def load_platform_report(report_path: Path) -> list[dict[str, Any]]:
    """Muat laporan platform simulasi dari JSON, JSONL, atau CSV."""
    path = Path(report_path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise ValueError(f"CSV report tanpa header: {path}")
            missing = [col for col in REQUIRED_FIELDS if col not in reader.fieldnames]
            if missing:
                raise ValueError(f"Header CSV report kurang kolom wajib {missing}: {path}")
            return [dict(row) for row in reader]

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"Berkas laporan platform kosong: {path}")
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Laporan JSON wajib berupa daftar objek")
        return [dict(item) for item in data]
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, Mapping):
                for key in ("entries", "records", "rows", "payouts"):
                    if isinstance(obj.get(key), list):
                        return [dict(item) for item in obj[key]]
                return [dict(obj)]
        except json.JSONDecodeError:
            pass
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def reconcile_ledger_vs_report(
    ledger_rows: Sequence[Mapping[str, Any]],
    report_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Cocokkan ledger simulasi vs laporan platform by name+platform+amount+proof_id."""
    report_queues: dict[tuple[str, str, str, str], deque[tuple[int, dict[str, Any]]]] = defaultdict(deque)
    for r_idx, raw_r in enumerate(report_rows, 1):
        r_dict = dict(raw_r)
        key = _row_key(r_dict, r_idx)
        report_queues[key].append((r_idx, r_dict))

    matched: list[dict[str, Any]] = []
    ledger_orphans: list[dict[str, Any]] = []
    matched_total = Decimal("0")

    for l_idx, raw_l in enumerate(ledger_rows, 1):
        l_dict = dict(raw_l)
        key = _row_key(l_dict, l_idx)
        queue = report_queues.get(key)
        if queue:
            r_idx, r_dict = queue.popleft()
            matched_total += Decimal(key[2])
            matched.append(
                {
                    "match_key": {
                        "name": key[0],
                        "platform": key[1],
                        "amount": key[2],
                        "proof_id": key[3],
                    },
                    "ledger_row_index": l_idx,
                    "report_row_index": r_idx,
                    "ledger_row": l_dict,
                    "report_row": r_dict,
                }
            )
        else:
            ledger_orphans.append(
                {
                    "ledger_row_index": l_idx,
                    "match_key": {
                        "name": key[0],
                        "platform": key[1],
                        "amount": key[2],
                        "proof_id": key[3],
                    },
                    "row": l_dict,
                }
            )

    report_orphans: list[dict[str, Any]] = []
    for key, queue in sorted(report_queues.items()):
        while queue:
            r_idx, r_dict = queue.popleft()
            report_orphans.append(
                {
                    "report_row_index": r_idx,
                    "match_key": {
                        "name": key[0],
                        "platform": key[1],
                        "amount": key[2],
                        "proof_id": key[3],
                    },
                    "row": r_dict,
                }
            )
    report_orphans.sort(key=lambda item: item["report_row_index"])

    matched_amount_str = (
        format(matched_total, "f").rstrip("0").rstrip(".")
        if "." in format(matched_total, "f")
        else format(matched_total, "f")
    )
    reconciled_clean = len(ledger_orphans) == 0 and len(report_orphans) == 0

    return {
        "schema": SCHEMA,
        "reconciled_clean": reconciled_clean,
        "summary": {
            "ledger_count": len(ledger_rows),
            "report_count": len(report_rows),
            "matched_count": len(matched),
            "ledger_orphan_count": len(ledger_orphans),
            "report_orphan_count": len(report_orphans),
            "matched_total_amount": matched_amount_str,
        },
        "matched": matched,
        "ledger_orphans": ledger_orphans,
        "report_orphans": report_orphans,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rekonsiliasi dry-run CSV transaksi simulasi vs laporan platform simulasi."
    )
    parser.add_argument("--ledger", required=True, help="Path CSV transaksi simulasi.")
    parser.add_argument("--report", required=True, help="Path JSON/JSONL/CSV laporan platform simulasi.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        ledger_rows = load_ledger_csv(Path(args.ledger))
        report_rows = load_platform_report(Path(args.report))
        result = reconcile_ledger_vs_report(ledger_rows, report_rows)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if result["reconciled_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
