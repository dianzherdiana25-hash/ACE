"""Buku insiden operasional append-only berantai hash (JSONL) (AG79).

Mencatat insiden dengan struktur baku (``incident_id``, ``ts``, ``kind``,
``cause``, ``remediation``, ``recovery_evidence``), menolak penulisan ulang
entri lama maupun manipulasi baris terdahulu lewat verifikasi rantai hash, dan
merender ringkasan per periode tanggal UTC.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.incident-book.v1"
GENESIS_PREV = "GENESIS"


class IncidentBookError(ValueError):
    """Error integritas rantai atau upaya penulisan ulang entri buku insiden."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hash(seq: int, prev: str, entry: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical({"seq": seq, "prev": prev, "entry": dict(entry)}).encode("utf-8")
    ).hexdigest()


def _parse_utc(raw: Any) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Timestamp ts insiden wajib diisi")
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp insiden wajib memiliki zona waktu: {raw!r}")
    return dt.astimezone(timezone.utc)


def load_and_verify_book(book_path: Path) -> tuple[list[dict[str, Any]], set[str], str]:
    """Muat dan verifikasi integritas append-only seluruh entri buku insiden."""
    path = Path(book_path)
    if not path.exists():
        return [], set(), GENESIS_PREV
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    expected_prev = GENESIS_PREV

    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s:
            raise IncidentBookError(f"Baris kosong terlarang pada baris {idx}")
        try:
            row = json.loads(s)
        except json.JSONDecodeError as exc:
            raise IncidentBookError(f"JSON insiden rusak pada baris {idx}: {exc}") from exc
        if not isinstance(row, dict):
            raise IncidentBookError(f"Baris {idx} buku insiden wajib berupa objek")

        seq = row.get("seq")
        prev = row.get("prev")
        digest = row.get("hash")
        entry = row.get("entry")
        if type(seq) is not int or seq != idx:
            raise IncidentBookError(f"Urutan seq insiden melompat pada baris {idx}: {seq!r}")
        if prev != expected_prev:
            raise IncidentBookError(f"Rantai prev putus pada seq {seq}: baris lama telah diubah.")
        if not isinstance(entry, Mapping) or not isinstance(digest, str):
            raise IncidentBookError(f"Entri/hash hilang pada seq {seq}")
        expected_hash = _compute_hash(seq, prev, entry)
        if digest != expected_hash:
            raise IncidentBookError(
                f"Hash insiden seq {seq} tidak cocok — penulisan ulang entri lama ditolak."
            )
        iid = str(entry.get("incident_id") or "")
        if not iid or iid in seen_ids:
            raise IncidentBookError(f"incident_id kosong atau ganda pada seq {seq}: {iid!r}")
        seen_ids.add(iid)
        entries.append(row)
        expected_prev = digest

    return entries, seen_ids, expected_prev


def record_incident(
    book_path: Path,
    *,
    incident_id: str,
    kind: str,
    cause: str,
    remediation: str,
    recovery_evidence: str,
    ts: str | None = None,
) -> dict[str, Any]:
    """Tambahkan satu entri insiden baru secara append-only dan tolak ID lama/duplikat."""
    iid = str(incident_id or "").strip()
    if not iid:
        raise ValueError("incident_id wajib tak-kosong")
    for label, val in (
        ("kind", kind),
        ("cause", cause),
        ("remediation", remediation),
        ("recovery_evidence", recovery_evidence),
    ):
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Field wajib '{label}' tidak boleh kosong")

    dt = _parse_utc(ts) if ts is not None else datetime.now(timezone.utc)
    ts_iso = dt.isoformat().replace("+00:00", "Z")

    path = Path(book_path)
    entries, seen_ids, prev_hash = load_and_verify_book(path)
    if iid in seen_ids:
        raise IncidentBookError(
            f"incident_id '{iid}' sudah tercatat — buku insiden menolak penulisan ulang entri lama."
        )

    seq = len(entries) + 1
    entry_payload = {
        "incident_id": iid,
        "ts": ts_iso,
        "kind": kind.strip(),
        "cause": cause.strip(),
        "remediation": remediation.strip(),
        "recovery_evidence": recovery_evidence.strip(),
    }
    row = {
        "schema": SCHEMA,
        "seq": seq,
        "prev": prev_hash,
        "entry": entry_payload,
        "hash": _compute_hash(seq, prev_hash, entry_payload),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical(row) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return row


def summarize_period(
    book_path: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Verifikasi integritas buku insiden lalu ringkas insiden dalam periode tanggal UTC."""
    entries, _, _ = load_and_verify_book(Path(book_path))
    start_d = date.fromisoformat(start_date) if start_date else None
    end_d = date.fromisoformat(end_date) if end_date else None

    filtered: list[dict[str, Any]] = []
    by_kind: Counter[str] = Counter()
    for row in entries:
        e = row["entry"]
        day = _parse_utc(e["ts"]).date()
        if start_d and day < start_d:
            continue
        if end_d and day > end_d:
            continue
        by_kind[e["kind"]] += 1
        filtered.append({"seq": row["seq"], **e})

    return {
        "schema": SCHEMA,
        "book_path": str(book_path),
        "integrity_verified": True,
        "total_in_book": len(entries),
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "incident_count": len(filtered),
            "by_kind": dict(sorted(by_kind.items())),
        },
        "incidents": filtered,
    }


def render_summary_markdown(report: Mapping[str, Any]) -> str:
    """Render ringkasan periode buku insiden dalam Markdown."""
    s = report["summary"]
    p = report["period"]
    lines = [
        "# Ringkasan Buku Insiden Operasional",
        "",
        f"- Periode: `{p['start_date'] or 'awal'}` s.d. `{p['end_date'] or 'akhir'}`",
        f"- Jumlah insiden periode: {s['incident_count']} (total buku: {report['total_in_book']})",
        "",
        "| Seq | ID Insiden | Tanggal UTC | Jenis | Sebab | Perbaikan | Bukti Pulih |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["incidents"]:
        lines.append(
            f"| {item['seq']} | {item['incident_id']} | {item['ts']} | {item['kind']} | "
            f"{item['cause']} | {item['remediation']} | {item['recovery_evidence']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Buku insiden operasional append-only (catat, verifikasi, ringkas periode)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="Catat satu insiden baru.")
    p_rec.add_argument("--book", required=True)
    p_rec.add_argument("--id", required=True, dest="incident_id")
    p_rec.add_argument("--kind", required=True)
    p_rec.add_argument("--cause", required=True)
    p_rec.add_argument("--remediation", required=True)
    p_rec.add_argument("--recovery-evidence", required=True)
    p_rec.add_argument("--ts")

    p_sum = sub.add_parser("summary", help="Render ringkasan periode dari buku insiden.")
    p_sum.add_argument("--book", required=True)
    p_sum.add_argument("--start-date")
    p_sum.add_argument("--end-date")
    p_sum.add_argument("--format", choices=("json", "markdown"), default="json")
    p_sum.add_argument("--out")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "record":
            res = record_incident(
                Path(args.book),
                incident_id=args.incident_id,
                kind=args.kind,
                cause=args.cause,
                remediation=args.remediation,
                recovery_evidence=args.recovery_evidence,
                ts=args.ts,
            )
            sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            return 0
        rep = summarize_period(
            Path(args.book),
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_text = (
        render_summary_markdown(rep)
        if args.format == "markdown"
        else json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(out_text, encoding="utf-8")
    else:
        sys.stdout.write(out_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
