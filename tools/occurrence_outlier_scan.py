#!/usr/bin/env python3
"""Pemindai outlier occurrence gap tanpa kemajuan tugas belajar tertaut (AG31).

Kenapa: gap dengan ribuan pengulangan (seperti occurrence=1526) tanpa kemajuan
tugas belajar menandakan putaran macet atau pembelajaran buta yang menghabiskan
siklus tanpa penutupan gap. Perkakas baca-saja ini menyorot hanya gap yang
melampaui ambang sekaligus tidak menunjukkan kemajuan tugas belajar tertaut.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any
from urllib.parse import quote


SCHEMA = "ace.occurrence-outlier-scan.v1"
DEFAULT_THRESHOLD = 100
_PROGRESSIVE_STATES = frozenset(
    {"ACTIVE", "LEARNING", "VERIFYING", "READY_TO_INTEGRATE", "INTEGRATING", "COMPLETED"}
)


def _has_learning_progress(task_row: dict[str, Any] | None) -> tuple[bool, str]:
    if task_row is None:
        return False, "no_linked_learning_task"
    status = str(task_row.get("status") or "")
    stagnation = float(task_row.get("stagnation_score") or 0.0)
    attempts = int(task_row.get("attempt_count") or 0)
    if status == "COMPLETED":
        return True, "learning_completed"
    if status in _PROGRESSIVE_STATES and stagnation < 0.5 and attempts > 0:
        return True, "learning_active_with_progress"
    if status in _PROGRESSIVE_STATES and stagnation >= 0.5:
        return False, "linked_task_stagnant"
    if status in ("FAILED_WITH_RECOVERY_STATE", "CANCELLED", "PAUSED"):
        return False, f"linked_task_{status.lower()}"
    return False, f"linked_task_no_progress:{status or 'UNKNOWN'}"


def scan_occurrence_outliers(
    db_path: Path,
    *,
    threshold: int = DEFAULT_THRESHOLD,
    include_closed: bool = False,
) -> dict[str, Any]:
    """Pindai tabel gaps + tasks via URI read-only untuk mendeteksi outlier tanpa kemajuan belajar."""
    if type(threshold) is not int or threshold <= 0:
        raise ValueError("--threshold wajib bilangan bulat positif.")
    resolved = Path(db_path).resolve()
    if not resolved.is_file():
        raise ValueError(f"Berkas SQLite store tidak ditemukan: {db_path}")

    uri = f"file:{quote(str(resolved))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"Gagal membuka SQLite secara read-only: {exc}") from None

    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "gaps" not in tables:
            raise ValueError("Tabel 'gaps' tidak ditemukan pada OperationalStore SQLite.")
        gaps = [
            dict(row)
            for row in conn.execute(
                "SELECT gap_id, error_type, status, linked_learning_task_id, occurrence_count, updated_at "
                "FROM gaps ORDER BY occurrence_count DESC, gap_id ASC"
            ).fetchall()
        ]
        tasks_by_id: dict[str, dict[str, Any]] = {}
        if "tasks" in tables:
            for row in conn.execute(
                "SELECT task_id, status, attempt_count, stagnation_score, updated_at FROM tasks"
            ).fetchall():
                tasks_by_id[str(row["task_id"])] = dict(row)
    except sqlite3.Error as exc:
        raise ValueError(f"Gagal membaca SQLite store: {exc}") from None
    finally:
        conn.close()

    outliers: list[dict[str, Any]] = []
    skipped_with_progress: list[str] = []
    gaps_checked = 0

    for g in gaps:
        status = str(g.get("status") or "OPEN")
        if not include_closed and status != "OPEN":
            continue
        gaps_checked += 1
        occ = int(g.get("occurrence_count") or 0)
        if occ < threshold:
            continue
        ltid = str(g.get("linked_learning_task_id") or "").strip()
        task_row = tasks_by_id.get(ltid) if ltid else None
        progressed, progress_reason = _has_learning_progress(task_row)
        if progressed:
            skipped_with_progress.append(str(g["gap_id"]))
            continue
        outliers.append(
            {
                "gap_id": str(g["gap_id"]),
                "error_type": str(g.get("error_type") or "UNKNOWN"),
                "status": status,
                "occurrence_count": occ,
                "linked_learning_task_id": ltid or None,
                "linked_task_status": str(task_row["status"]) if task_row else None,
                "reason": progress_reason,
                "updated_at": str(g.get("updated_at") or ""),
            }
        )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "threshold": threshold,
        "summary": {
            "gaps_scanned": gaps_checked,
            "outlier_count": len(outliers),
            "skipped_with_active_progress": len(skipped_with_progress),
        },
        "outlier_gap_ids": [item["gap_id"] for item in outliers],
        "skipped_with_progress_gap_ids": skipped_with_progress,
        "outliers": outliers,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Pemindaian Outlier Occurrence Gap",
        "",
        f"- Schema: `{report['schema']}` (`threshold >= {report['threshold']}`)",
        f"- Gap dipindai: **{s['gaps_scanned']}**, outlier tanpa kemajuan: **{s['outlier_count']}**, "
        f"dilewati karena belajar aktif: **{s['skipped_with_active_progress']}**",
        "",
        "| Gap ID | Error Type | Occurrence | Tugas Tertaut | Alasan |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in report["outliers"]:
        lines.append(
            f"| `{item['gap_id']}` | `{item['error_type']}` | {item['occurrence_count']} "
            f"| `{item['linked_learning_task_id'] or '-'}` ({item['linked_task_status'] or '-'}) | `{item['reason']}` |"
        )
    if not report["outliers"]:
        lines.append("| - | - | 0 | - | Tidak ada outlier melewati ambang |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, type=Path, help="Path SQLite OperationalStore.")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="Ambang minimum occurrence_count.")
    parser.add_argument("--include-closed", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        report = scan_occurrence_outliers(
            args.sqlite,
            threshold=args.threshold,
            include_closed=args.include_closed,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, ensure_ascii=False), end="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
