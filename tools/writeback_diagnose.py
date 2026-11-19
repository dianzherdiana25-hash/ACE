#!/usr/bin/env python3
"""Periksa kesehatan write-back agar kegagalan terlihat tanpa menyentuh state.

CLI mencetak JSON. Salinan sementara SQLite dan WAL dibuka dalam mode read-only
agar SQLite tidak membuat file SHM di workspace. Sumber harus stabil selama
penyalinan. Gunakan snapshot yang stabil jika workspace sedang sering berubah.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
from tempfile import TemporaryDirectory
from typing import Any

if __name__ == "__main__":
    sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ace_operational.cognitive_memory import CognitiveMemory


_DB = Path("ace_operational.sqlite3")
_WAL = Path("ace_operational.sqlite3-wal")
_JOURNAL = Path("ace_operational.sqlite3-journal")
_MEMORY = Path("cognitive_memory/memory.jsonl")
_SOURCES = (_DB, _WAL, _JOURNAL, _MEMORY)


def _source_identity(path: Path) -> tuple[int, ...] | None:
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Sumber harus berupa berkas reguler: {path.name}")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _snapshot(workspace: Path, target: Path) -> None:
    sources = {name: _source_identity(workspace / name) for name in _SOURCES}
    if sources[_DB] is None:
        raise ValueError("Database ace_operational.sqlite3 tidak ditemukan.")
    if sources[_JOURNAL] is not None:
        raise ValueError("Rollback journal ditemukan. Gunakan snapshot SQLite yang stabil.")
    for name in (_DB, _WAL, _MEMORY):
        if sources[name] is not None:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(workspace / name, destination)
    if any(identity != _source_identity(workspace / name) for name, identity in sources.items()):
        raise ValueError("Berkas sumber berubah saat disalin. Coba ulang dengan snapshot yang stabil.")


def _memory_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "available": False,
            "chain_ok": None,
            "events": None,
            "anchored_evidence": None,
            "records_by_class": {},
            "records_by_source_kind": {},
        }

    try:
        memory = CognitiveMemory(path.parent)
        audit = memory.audit()
        # Counts describe all surviving records, including private or superseded records.
        by_class = Counter(r["content"].get("class", "unclassified")
                           for r in memory._records.values())
        by_source = Counter(r["source"]["kind"] for r in memory._records.values())
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("Log cognitive memory rusak atau formatnya tidak sah.") from None

    return {
        "available": True,
        "chain_ok": audit["chain_ok"],
        "events": audit["events"],
        "anchored_evidence": audit["anchored_evidence"],
        "records_by_class": dict(by_class),
        "records_by_source_kind": dict(by_source),
    }


def _store_report(db_path: Path, gap_limit: int) -> dict[str, Any]:
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as conn:
        receipts = {}
        for kind, passed, failed, total in conn.execute("""
            SELECT action_kind, SUM(passed = 1), SUM(passed = 0), COUNT(*)
            FROM receipts GROUP BY action_kind
        """):
            if (passed or 0) + (failed or 0) != total:
                raise ValueError("Receipt memiliki nilai passed selain 0 atau 1.")
            receipts[kind] = {"passed": passed, "failed": failed}
        gaps = [
            {"missing_skill_or_tool": name, "occurrence_count": count}
            for name, count in conn.execute("""
                SELECT missing_skill_or_tool, SUM(occurrence_count) AS occurrences
                FROM gaps WHERE status = 'OPEN' GROUP BY missing_skill_or_tool
                ORDER BY occurrences DESC, missing_skill_or_tool LIMIT ?
            """, (gap_limit,))
        ]
        skills = dict(conn.execute("SELECT status, COUNT(*) FROM skills GROUP BY status"))
        frontier = dict(conn.execute("SELECT status, COUNT(*) FROM frontier GROUP BY status"))

    return {
        "receipts_by_action_kind": receipts,
        "top_open_gaps": gaps,
        "skills": {"total": sum(skills.values()), "by_status": skills},
        "frontier": {"total": sum(frontier.values()), "by_status": frontier},
    }


def diagnose(workspace: Path, *, gap_limit: int = 10) -> dict[str, Any]:
    """Baca laporan workspace melalui salinan sementara di luar workspace."""
    if gap_limit <= 0:
        raise ValueError("Batas gap harus positif.")
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError("Workspace harus berupa direktori yang sudah ada.")
    # Ignore TMPDIR, which can itself point into the target workspace.
    scratch = Path("/tmp").resolve()
    if scratch.is_relative_to(workspace):
        raise ValueError("Direktori salinan sementara harus berada di luar workspace.")

    with TemporaryDirectory(prefix="ace-writeback-", dir=scratch) as directory:
        snapshot = Path(directory)
        _snapshot(workspace, snapshot)
        return {
            "cognitive_memory": _memory_report(snapshot / _MEMORY),
            **_store_report(snapshot / _DB, gap_limit),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--gap-limit", type=int, default=10,
                        help="Jumlah entri gap terbuka teratas (default 10).")
    args = parser.parse_args(argv)
    try:
        result = diagnose(args.workspace, gap_limit=args.gap_limit)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f"Diagnosis gagal: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if result["cognitive_memory"]["chain_ok"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
