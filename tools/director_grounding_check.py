#!/usr/bin/env python3
"""Pemeriksa keterjangkaran klaim kuantitatif pada rationale proposal director terhadap fakta store (AG33).

Kenapa: rationale proposal sering menyebut angka ("12 gap terbuka", "1526 occurrence")
tanpa memeriksa fakta store terkini. Perkakas baca-saja ini mengekstrak klaim angka
tersebut dan memverifikasinya terhadap berkas fakta JSON atau SQLite OperationalStore
read-only, menandai setiap penyimpangan sebagai `factual_mismatch`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any
from urllib.parse import quote


SCHEMA = "ace.director-grounding-check.v1"

_METRIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "open_gaps",
        re.compile(r"\b(\d+)\s+(?:gap(?:s)?\s+(?:terbuka|open)|open\s+gap(?:s)?)\b", re.IGNORECASE),
    ),
    (
        "total_gaps",
        re.compile(r"\b(\d+)\s+(?:total\s+gap(?:s)?|gap(?:s)?\s+(?:total|tercatat))\b", re.IGNORECASE),
    ),
    (
        "closed_gaps",
        re.compile(r"\b(\d+)\s+(?:gap(?:s)?\s+(?:tertutup|selesai|resolved|closed))\b", re.IGNORECASE),
    ),
    (
        "dynamic_tech_practice_failed_gaps",
        re.compile(r"\b(\d+)\s+gap(?:s)?\s+DYNAMIC_TECH_PRACTICE_FAILED\b", re.IGNORECASE),
    ),
    (
        "max_occurrence",
        re.compile(
            r"(?:\b(\d+)\s+(?:occurrence(?:s)?|kemunculan|kejadian)|"
            r"(?:occurrence|kemunculan)\s*(?:=|:|\s)\s*(\d+))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "active_skills",
        re.compile(r"\b(\d+)\s+(?:skill(?:s)?\s+(?:aktif|active)|active\s+skill(?:s)?)\b", re.IGNORECASE),
    ),
    (
        "completed_tasks",
        re.compile(r"\b(\d+)\s+(?:tugas\s+(?:selesai|belajar\s+selesai)|completed\s+task(?:s)?)\b", re.IGNORECASE),
    ),
)


def extract_quantitative_claims(rationale: str) -> list[dict[str, Any]]:
    """Ekstrak klaim angka terklasifikasi dari teks rationale proposal secara deterministik."""
    if not isinstance(rationale, str) or not rationale.strip():
        return []
    claims: list[dict[str, Any]] = []
    for metric, pat in _METRIC_PATTERNS:
        for match in pat.finditer(rationale):
            raw_num = next((g for g in match.groups() if g is not None), None)
            if raw_num is None:
                continue
            claims.append(
                {
                    "metric": metric,
                    "claimed": int(raw_num),
                    "snippet": match.group(0),
                    "start": match.start(),
                }
            )
    claims.sort(key=lambda item: (item["start"], item["metric"]))
    return [{k: v for k, v in item.items() if k != "start"} for item in claims]


def load_facts_from_sqlite(db_path: Path) -> dict[str, int]:
    resolved = Path(db_path).resolve()
    if not resolved.is_file():
        raise ValueError(f"Berkas SQLite store tidak ditemukan: {db_path}")
    uri = f"file:{quote(str(resolved))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        facts: dict[str, int] = {}
        if "gaps" in tables:
            facts["total_gaps"] = int(conn.execute("SELECT COUNT(*) FROM gaps").fetchone()[0])
            facts["open_gaps"] = int(
                conn.execute("SELECT COUNT(*) FROM gaps WHERE status='OPEN'").fetchone()[0]
            )
            facts["closed_gaps"] = int(
                conn.execute("SELECT COUNT(*) FROM gaps WHERE status!='OPEN'").fetchone()[0]
            )
            facts["dynamic_tech_practice_failed_gaps"] = int(
                conn.execute(
                    "SELECT COUNT(*) FROM gaps WHERE status='OPEN' AND error_type='DYNAMIC_TECH_PRACTICE_FAILED'"
                ).fetchone()[0]
            )
            facts["max_occurrence"] = int(
                conn.execute("SELECT COALESCE(MAX(occurrence_count), 0) FROM gaps").fetchone()[0]
            )
        if "skills" in tables:
            facts["active_skills"] = int(
                conn.execute("SELECT COUNT(*) FROM skills WHERE status='ACTIVE'").fetchone()[0]
            )
        if "tasks" in tables:
            facts["completed_tasks"] = int(
                conn.execute("SELECT COUNT(*) FROM tasks WHERE status='COMPLETED'").fetchone()[0]
            )
        return facts
    finally:
        conn.close()


def check_proposal_grounding(proposals: list[dict[str, Any]], facts: dict[str, Any]) -> dict[str, Any]:
    """Bandingkan klaim kuantitatif setiap proposal terhadap peta fakta store."""
    if not isinstance(proposals, list) or not isinstance(facts, dict):
        raise ValueError("Proposal wajib berupa daftar dan facts wajib berupa objek.")

    results: list[dict[str, Any]] = []
    total_claims = 0
    matched_claims = 0
    mismatched_claims = 0
    unknown_claims = 0

    for idx, prop in enumerate(proposals, 1):
        if not isinstance(prop, dict):
            raise ValueError(f"Proposal ke-{idx} wajib berupa objek JSON.")
        pid = str(prop.get("id") or prop.get("task_id") or f"proposal_{idx}")
        rationale = str(prop.get("rationale") or "")
        extracted = extract_quantitative_claims(rationale)
        checked_claims: list[dict[str, Any]] = []
        prop_mismatch = False

        for item in extracted:
            metric = item["metric"]
            claimed = item["claimed"]
            total_claims += 1
            if metric not in facts or type(facts[metric]) is not int:
                unknown_claims += 1
                checked_claims.append(
                    {
                        "metric": metric,
                        "claimed": claimed,
                        "actual": None,
                        "status": "unknown_fact",
                        "snippet": item["snippet"],
                    }
                )
            elif facts[metric] == claimed:
                matched_claims += 1
                checked_claims.append(
                    {
                        "metric": metric,
                        "claimed": claimed,
                        "actual": facts[metric],
                        "status": "match",
                        "snippet": item["snippet"],
                    }
                )
            else:
                mismatched_claims += 1
                prop_mismatch = True
                checked_claims.append(
                    {
                        "metric": metric,
                        "claimed": claimed,
                        "actual": facts[metric],
                        "status": "factual_mismatch",
                        "snippet": item["snippet"],
                    }
                )

        results.append(
            {
                "id": pid,
                "claim_count": len(checked_claims),
                "factual_mismatch": prop_mismatch,
                "status": "factual_mismatch" if prop_mismatch else "grounded",
                "claims": checked_claims,
            }
        )

    return {
        "schema": SCHEMA,
        "read_only": True,
        "summary": {
            "total_proposals": len(results),
            "grounded_proposals": sum(1 for r in results if not r["factual_mismatch"]),
            "mismatched_proposals": sum(1 for r in results if r["factual_mismatch"]),
            "total_claims": total_claims,
            "matched_claims": matched_claims,
            "mismatched_claims": mismatched_claims,
            "unknown_claims": unknown_claims,
        },
        "all_grounded": mismatched_claims == 0,
        "proposals": results,
    }


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else [parsed]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", required=True, type=Path, help="Berkas JSON/JSONL proposal berisi rationale.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--facts", type=Path, help="Berkas JSON fakta store.")
    src.add_argument("--sqlite", type=Path, help="OperationalStore SQLite (read-only).")
    args = parser.parse_args(argv)
    try:
        proposals = _load_proposals(args.proposals)
        facts = (
            load_facts_from_sqlite(args.sqlite)
            if args.sqlite is not None
            else json.loads(args.facts.read_text(encoding="utf-8"))
        )
        report = check_proposal_grounding(proposals, facts)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_grounded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
