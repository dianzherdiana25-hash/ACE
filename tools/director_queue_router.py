#!/usr/bin/env python3
"""Perute antrean proposal director (praktik / riset / payung) dari error_type gap based_on (AG35).

Kenapa: memisahkan proposal yang butuh pengulangan praktik (`DYNAMIC_TECH_PRACTICE_FAILED`
& `LANGUAGE_CURRICULUM_*`), proposal payung lintas banyak gap (`multi_gap`), dan
proposal riset error baru sebelum masuk eksekusi agar setiap jalur memperoleh perlakuan tepat.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any
from urllib.parse import quote


SCHEMA = "ace.director-queue-router.v1"


def is_practice_error_type(error_type: str) -> bool:
    norm = str(error_type or "").strip()
    return norm == "DYNAMIC_TECH_PRACTICE_FAILED" or norm.startswith("LANGUAGE_CURRICULUM_")


def _extract_based_on(proposal: dict[str, Any]) -> list[str]:
    raw = proposal.get("based_on")
    if raw is None and isinstance(proposal.get("checkpoint"), dict):
        cp = proposal["checkpoint"]
        raw = cp.get("based_on")
        if raw is None and isinstance(cp.get("proposal"), dict):
            raw = cp["proposal"].get("based_on")
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(str(r).strip() for r in raw if isinstance(r, str) and r.strip()))


def load_gap_errors_from_sqlite(db_path: Path) -> dict[str, str]:
    resolved = Path(db_path).resolve()
    if not resolved.is_file():
        raise ValueError(f"Berkas SQLite store tidak ditemukan: {db_path}")
    uri = f"file:{quote(str(resolved))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "gaps" not in tables:
            raise ValueError("Tabel 'gaps' tidak ditemukan pada OperationalStore SQLite.")
        return {
            str(r["gap_id"]): str(r["error_type"])
            for r in conn.execute("SELECT gap_id, error_type FROM gaps").fetchall()
        }
    finally:
        conn.close()


def route_proposals(
    proposals: list[dict[str, Any]],
    gap_error_types: dict[str, str],
) -> dict[str, Any]:
    """Klasifikasikan setiap proposal ke antrean `praktik`, `payung`, atau `riset`."""
    if not isinstance(proposals, list) or not isinstance(gap_error_types, dict):
        raise ValueError("Proposal wajib berupa daftar dan gap_error_types wajib berupa objek.")

    counts = {"praktik": 0, "riset": 0, "payung": 0}
    queues: dict[str, list[str]] = {"praktik": [], "riset": [], "payung": []}
    routed: list[dict[str, Any]] = []

    for idx, prop in enumerate(proposals, 1):
        if not isinstance(prop, dict):
            raise ValueError(f"Proposal ke-{idx} wajib berupa objek JSON.")
        pid = str(prop.get("id") or prop.get("task_id") or f"proposal_{idx}")
        refs = _extract_based_on(prop)
        error_types = [gap_error_types.get(ref) for ref in refs if ref in gap_error_types]

        if len(refs) > 1:
            queue = "payung"
            reason = "multi_gap_based_on"
        elif len(refs) == 1 and error_types and is_practice_error_type(error_types[0]):
            queue = "praktik"
            reason = f"practice_error_type:{error_types[0]}"
        else:
            queue = "riset"
            reason = (
                f"other_error_type:{error_types[0]}"
                if error_types
                else ("missing_based_on" if not refs else "unmapped_gap_error_type")
            )

        counts[queue] += 1
        queues[queue].append(pid)
        routed.append(
            {
                "id": pid,
                "based_on": refs,
                "error_types": error_types,
                "queue": queue,
                "reason": reason,
            }
        )

    return {
        "schema": SCHEMA,
        "summary": {
            "total_proposals": len(routed),
            **counts,
        },
        "queues": queues,
        "proposals": routed,
    }


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", required=True, type=Path)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--gaps", type=Path, help="Berkas JSON peta gap_id -> error_type.")
    src.add_argument("--sqlite", type=Path, help="OperationalStore SQLite (read-only).")
    args = parser.parse_args(argv)
    try:
        proposals = _load_proposals(args.proposals)
        gap_map = (
            load_gap_errors_from_sqlite(args.sqlite)
            if args.sqlite is not None
            else json.loads(args.gaps.read_text(encoding="utf-8"))
        )
        report = route_proposals(proposals, gap_map)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
