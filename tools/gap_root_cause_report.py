#!/usr/bin/env python3
"""Laporan kandidat akar masalah gap dari OperationalStore SQLite secara baca-saja (AG30).

Kenapa: ratusan/ribuan occurrence berulang seperti DYNAMIC_TECH_PRACTICE_FAILED
atau gap LANGUAGE dengan occurrence ribuan tidak boleh ditangani per gejala;
pengelompokan per error_type beserta tren occurrence dan status tugas belajar
tertaut langsung memunculkan kandidat akar masalah sistemik tanpa menyentuh DB.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any
from urllib.parse import quote


SCHEMA = "ace.gap-root-cause-report.v1"


def _root_cause_candidate(error_type: str, gap_rows: list[dict[str, Any]], task_outcomes: Counter[str]) -> str:
    max_occ = max((g["occurrence_count"] for g in gap_rows), default=0)
    open_cnt = sum(1 for g in gap_rows if g["status"] == "OPEN")
    completed = task_outcomes.get("COMPLETED", 0)
    failed = task_outcomes.get("FAILED_WITH_RECOVERY_STATE", 0)
    unlinked = task_outcomes.get("UNLINKED", 0)

    if max_occ >= 100 and (completed == 0 or failed > 0):
        return f"stalled_learning_loop_outlier:{error_type.lower()}"
    if open_cnt >= 5 and failed >= open_cnt // 2:
        return f"systemic_practice_evaluator_or_skill_gap:{error_type.lower()}"
    if unlinked == len(gap_rows) and open_cnt > 0:
        return f"unlinked_gaps_missing_curriculum:{error_type.lower()}"
    if open_cnt == 0 and completed > 0:
        return f"resolving_under_learning:{error_type.lower()}"
    return f"active_investigation:{error_type.lower()}"


def analyze_gap_root_causes(db_path: Path) -> dict[str, Any]:
    """Baca tabel gaps & tasks dari OperationalStore via URI read-only dan bangun tabel akar masalah."""
    resolved = Path(db_path).resolve()
    if not resolved.is_file():
        raise ValueError(f"Berkas SQLite store tidak ditemukan: {db_path}")

    uri = f"file:{quote(str(resolved))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"Gagal membuka SQLite read-only: {exc}") from None

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
                "SELECT gap_id, fingerprint, source_task_id, error_type, missing_skill_or_tool, "
                "status, linked_learning_task_id, occurrence_count, created_at, updated_at "
                "FROM gaps ORDER BY gap_id"
            ).fetchall()
        ]
        tasks_by_id: dict[str, dict[str, Any]] = {}
        if "tasks" in tables:
            for row in conn.execute(
                "SELECT task_id, status, attempt_count, stagnation_score, error_summary, updated_at "
                "FROM tasks ORDER BY task_id"
            ).fetchall():
                tasks_by_id[str(row["task_id"])] = dict(row)
    except sqlite3.Error as exc:
        raise ValueError(f"Gagal membaca tabel store SQLite: {exc}") from None
    finally:
        conn.close()

    by_error: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in gaps:
        etype = str(g.get("error_type") or "UNKNOWN")
        by_error[etype].append(g)

    groups: list[dict[str, Any]] = []
    for etype, group_rows in sorted(
        by_error.items(),
        key=lambda item: (-sum(int(r.get("occurrence_count") or 0) for r in item[1]), item[0]),
    ):
        occurrences = [int(r.get("occurrence_count") or 0) for r in group_rows]
        daily_trend: dict[str, int] = defaultdict(int)
        outcome_counts: Counter[str] = Counter()

        for r in group_rows:
            occ = int(r.get("occurrence_count") or 0)
            day = str(r.get("updated_at") or r.get("created_at") or "")[:10] or "unknown"
            daily_trend[day] += occ
            ltid = str(r.get("linked_learning_task_id") or "").strip()
            if not ltid:
                outcome_counts["UNLINKED"] += 1
            elif ltid not in tasks_by_id:
                outcome_counts["MISSING_TASK"] += 1
            else:
                outcome_counts[str(tasks_by_id[ltid]["status"])] += 1

        open_count = sum(1 for r in group_rows if r.get("status") == "OPEN")
        candidate = _root_cause_candidate(etype, group_rows, outcome_counts)
        groups.append(
            {
                "error_type": etype,
                "gap_count": len(group_rows),
                "open_gap_count": open_count,
                "total_occurrences": sum(occurrences),
                "max_occurrence": max(occurrences, default=0),
                "min_occurrence": min(occurrences, default=0),
                "avg_occurrence": round(sum(occurrences) / len(occurrences), 2) if occurrences else 0.0,
                "occurrence_trend_by_day": [
                    {"day": day, "occurrences": cnt}
                    for day, cnt in sorted(daily_trend.items())
                ],
                "learning_task_outcomes": dict(sorted(outcome_counts.items())),
                "root_cause_candidate": candidate,
                "sample_gap_ids": [r["gap_id"] for r in sorted(group_rows, key=lambda x: (-int(x.get("occurrence_count") or 0), x["gap_id"]))[:5]],
            }
        )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "summary": {
            "total_gaps": len(gaps),
            "open_gaps": sum(1 for g in gaps if g.get("status") == "OPEN"),
            "error_type_count": len(groups),
            "total_occurrences": sum(int(g.get("occurrence_count") or 0) for g in gaps),
        },
        "groups": groups,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Laporan Kandidat Akar Masalah Gap",
        "",
        f"- Schema: `{report['schema']}` (`read_only={report['read_only']}`)",
        f"- Total gap: **{s['total_gaps']}** (open: **{s['open_gaps']}**), jenis error: **{s['error_type_count']}**, total occurrence: **{s['total_occurrences']}**",
        "",
        "| Error Type | Gap (Open/Total) | Total Occ | Max Occ | Hasil Tugas Belajar Tertaut | Kandidat Akar Masalah |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for grp in report["groups"]:
        outcomes = ", ".join(f"{k}={v}" for k, v in sorted(grp["learning_task_outcomes"].items()))
        lines.append(
            f"| `{grp['error_type']}` | {grp['open_gap_count']}/{grp['gap_count']} "
            f"| {grp['total_occurrences']} | {grp['max_occurrence']} | {outcomes} | `{grp['root_cause_candidate']}` |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, type=Path, help="Path SQLite OperationalStore.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        report = analyze_gap_root_causes(args.sqlite)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, ensure_ascii=False), end="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
