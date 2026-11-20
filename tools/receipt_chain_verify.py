"""Verifikator rantai receipt director JSONL selaras semantik AG11 (AG53).

Memeriksa kelengkapan pasangan ``started`` -> ``completed``/``failed`` pada
berkas receipt ``director_executor`` secara read-only:
- Baris terakhir yang robek (tanpa ``\\n`` penutup atau JSON terpotong di ekor)
  ditoleransi sebagai status eksplisit ``"torn_tail_pending"`` dengan
  ``"<torn_receipt>"`` pada daftar ``pending`` (selaras ``_read_receipts`` AG11).
- Baris tengah rusak JSON, field cacat, ``started`` ganda, atau
  ``completed``/``failed`` tanpa ``started`` sebelumnya menghasilkan temuan
  bernama eksplisit pada ``findings``.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Sequence


SCHEMA = "ace.receipt-chain-verify.v1"
TORN_SENTINEL = "<torn_receipt>"


def verify_receipts_file(receipts_path: Path) -> dict[str, Any]:
    """Verifikasi berkas receipt JSONL dan laporkan pasangan, tail robek, serta temuan."""
    path = Path(receipts_path)
    with path.open("r", encoding="utf-8") as stream:
        lines = stream.readlines()

    started: dict[str, dict[str, Any]] = {}
    pending: set[str] = set()
    completed_pairs: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    torn_tail = False
    torn_tail_reason: str | None = None

    for idx, line in enumerate(lines):
        line_no = idx + 1
        is_last = idx == len(lines) - 1

        if is_last and not line.endswith("\n"):
            torn_tail = True
            torn_tail_reason = "missing_trailing_newline"
            pending.add(TORN_SENTINEL)
            break

        if not line.strip():
            findings.append(
                {
                    "line": line_no,
                    "code": "blank_line",
                    "detail": "baris kosong tidak diharapkan pada log receipt",
                }
            )
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            if is_last:
                torn_tail = True
                torn_tail_reason = "truncated_last_line_json"
                pending.add(TORN_SENTINEL)
                break
            findings.append(
                {
                    "line": line_no,
                    "code": "corrupt_middle_line",
                    "detail": str(exc),
                }
            )
            continue

        if not isinstance(record, dict):
            findings.append(
                {
                    "line": line_no,
                    "code": "invalid_record_not_object",
                    "detail": type(record).__name__,
                }
            )
            continue

        task_id = record.get("task_id")
        timestamp = record.get("at")
        status = record.get("status")

        if not isinstance(task_id, str) or not task_id.strip():
            findings.append(
                {
                    "line": line_no,
                    "code": "invalid_task_id",
                    "detail": f"task_id tidak sah: {task_id!r}",
                }
            )
            continue

        if not isinstance(timestamp, str) or not timestamp.strip():
            findings.append(
                {
                    "line": line_no,
                    "code": "invalid_timestamp",
                    "task_id": task_id,
                    "detail": "field 'at' hilang atau kosong",
                }
            )
            continue

        try:
            instant = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            findings.append(
                {
                    "line": line_no,
                    "code": "invalid_timestamp",
                    "task_id": task_id,
                    "detail": str(exc),
                }
            )
            continue

        if instant.tzinfo is None:
            findings.append(
                {
                    "line": line_no,
                    "code": "naive_timestamp",
                    "task_id": task_id,
                    "detail": f"timestamp wajib memiliki offset/zona waktu: {timestamp!r}",
                }
            )
            continue

        if status == "started":
            if task_id in started:
                findings.append(
                    {
                        "line": line_no,
                        "code": "duplicate_started",
                        "task_id": task_id,
                        "detail": "event started ganda untuk task_id yang sama",
                    }
                )
            else:
                started[task_id] = {"started_at": timestamp, "line": line_no}
                pending.add(task_id)
        elif status in {"completed", "failed"}:
            if task_id not in started:
                findings.append(
                    {
                        "line": line_no,
                        "code": "terminal_without_started",
                        "task_id": task_id,
                        "status": status,
                        "detail": f"event '{status}' muncul tanpa event 'started' sebelumnya",
                    }
                )
            elif task_id not in pending:
                findings.append(
                    {
                        "line": line_no,
                        "code": "duplicate_terminal",
                        "task_id": task_id,
                        "status": status,
                        "detail": "event terminal ganda untuk task_id yang sudah selesai",
                    }
                )
            else:
                pending.remove(task_id)
                completed_pairs.append(
                    {
                        "task_id": task_id,
                        "started_at": started[task_id]["started_at"],
                        "terminal_at": timestamp,
                        "terminal_status": status,
                    }
                )
        else:
            findings.append(
                {
                    "line": line_no,
                    "code": "unknown_status",
                    "task_id": task_id,
                    "status": status,
                    "detail": f"status receipt tidak dikenal: {status!r}",
                }
            )

    if findings:
        chain_status = "corrupt"
    elif torn_tail:
        chain_status = "torn_tail_pending"
    elif pending:
        chain_status = "in_flight_pending"
    else:
        chain_status = "clean"

    return {
        "schema": SCHEMA,
        "receipts_path": str(path),
        "status": chain_status,
        "valid_sequence": len(findings) == 0,
        "torn_tail": torn_tail,
        "torn_tail_reason": torn_tail_reason,
        "summary": {
            "total_lines": len(lines),
            "started_count": len(started),
            "complete_pair_count": len(completed_pairs),
            "pending_count": len(pending),
            "finding_count": len(findings),
            "finding_codes": [f["code"] for f in findings],
        },
        "pending_tasks": sorted(pending),
        "completed_pairs": completed_pairs,
        "findings": findings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifikasi rantai receipt JSONL (started/terminal, torn tail AG11, dan korupsi)."
    )
    parser.add_argument("--receipts", required=True, help="Path berkas receipts JSONL.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        report = verify_receipts_file(Path(args.receipts))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["valid_sequence"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
