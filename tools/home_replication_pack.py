"""Paket replikasi antar rumah ACE: manifest berhash dan deteksi konflik rekaman (AG50).

Membangun manifest hash deterministik atas berkas store dan memory milik
satu rumah fixture serta membandingkannya terhadap rumah kedua secara baca-saja
(SQLite dibuka dengan ``?mode=ro``). Secara tegas memisahkan:
- ``files.missing_on_target`` / ``files.extra_on_target`` (berkas hilang), vs
- ``records.conflicts`` (ID rekaman sama pada kedua rumah tetapi hash isi berbeda).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Mapping, Sequence
from urllib.parse import quote


SCHEMA = "ace.home-replication-pack.v1"


def _canonical_sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _extract_jsonl_records(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)
        if not isinstance(obj, Mapping):
            continue
        # Dukungan native untuk entri log CognitiveMemory (event.record) maupun objek datar.
        if isinstance(obj.get("event"), Mapping):
            ev = obj["event"]
            if ev.get("type") == "record" and isinstance(ev.get("record"), Mapping):
                rec = ev["record"]
                rid = str(rec.get("id") or f"seq:{obj.get('seq', line_no)}")
                records[rid] = _canonical_sha256(rec)
            else:
                rid = f"event:{obj.get('seq', line_no)}:{ev.get('type', 'unknown')}"
                records[rid] = _canonical_sha256(ev)
        else:
            rid = str(
                obj.get("id")
                or obj.get("record_id")
                or obj.get("gap_id")
                or obj.get("task_id")
                or f"line:{line_no}"
            )
            records[rid] = _canonical_sha256(obj)
    return records


def _extract_json_records(path: Path) -> dict[str, str]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, str] = {}
    if isinstance(obj, list):
        for idx, item in enumerate(obj):
            if isinstance(item, Mapping):
                rid = str(item.get("id") or item.get("record_id") or f"idx:{idx}")
                records[rid] = _canonical_sha256(item)
            else:
                records[f"idx:{idx}"] = _canonical_sha256(item)
    elif isinstance(obj, Mapping):
        if isinstance(obj.get("records"), list):
            for idx, item in enumerate(obj["records"]):
                if isinstance(item, Mapping):
                    rid = str(item.get("id") or item.get("record_id") or f"idx:{idx}")
                    records[rid] = _canonical_sha256(item)
        else:
            for key, val in obj.items():
                records[str(key)] = _canonical_sha256(val)
    return records


def _is_sqlite_file(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _extract_sqlite_records(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    uri = f"file:{quote(str(resolved))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        records: dict[str, str] = {}
        for table in tables:
            safe_table = table.replace('"', '""')
            col_info = conn.execute(f'PRAGMA table_info("{safe_table}")').fetchall()
            pk_cols = [c["name"] for c in sorted(col_info, key=lambda r: r["pk"]) if c["pk"] > 0]
            rows = conn.execute(f'SELECT * FROM "{safe_table}"').fetchall()
            for idx, row in enumerate(rows):
                row_dict = {k: row[k] for k in row.keys()}
                if pk_cols:
                    pk_val = "|".join(str(row_dict[col]) for col in pk_cols)
                elif "id" in row_dict:
                    pk_val = str(row_dict["id"])
                else:
                    pk_val = f"row:{idx}"
                records[f"{table}:{pk_val}"] = _canonical_sha256(row_dict)
        return records
    finally:
        conn.close()


def _extract_records_for_file(path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _extract_jsonl_records(path)
    if suffix == ".json":
        return _extract_json_records(path)
    if suffix in {".db", ".sqlite", ".sqlite3"} or _is_sqlite_file(path):
        return _extract_sqlite_records(path)
    return {}


def build_replication_manifest(home_dir: Path) -> dict[str, Any]:
    """Bangun manifest berkas + hash rekaman per-ID dari direktori rumah fixture."""
    root = Path(home_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Direktori rumah tidak ditemukan: {root}")

    files: dict[str, dict[str, Any]] = {}
    records: dict[str, dict[str, str]] = {}

    for child in sorted(root.rglob("*")):
        if not child.is_file():
            continue
        if "__pycache__" in child.parts or child.suffix == ".pyc":
            continue
        rel = child.relative_to(root).as_posix()
        raw = child.read_bytes()
        file_sha = hashlib.sha256(raw).hexdigest()
        rec_map = _extract_records_for_file(child)
        files[rel] = {
            "sha256": file_sha,
            "bytes": len(raw),
            "record_count": len(rec_map),
        }
        if rec_map:
            records[rel] = dict(sorted(rec_map.items()))

    return {
        "schema": SCHEMA,
        "home_root": str(root),
        "file_count": len(files),
        "files": files,
        "records": records,
    }


def _as_manifest(source: Path | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(source, Mapping):
        return source
    path = Path(source)
    if path.is_dir():
        return build_replication_manifest(path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, Mapping) or "files" not in obj:
        raise ValueError(f"Berkas manifest tidak sah: {path}")
    return obj


def compare_homes(
    source: Path | Mapping[str, Any],
    target: Path | Mapping[str, Any],
) -> dict[str, Any]:
    """Bandingkan dua rumah atau manifest untuk mendeteksi berkas hilang vs konflik rekaman."""
    m_src = _as_manifest(source)
    m_tgt = _as_manifest(target)

    src_files: Mapping[str, Mapping[str, Any]] = m_src.get("files", {})
    tgt_files: Mapping[str, Mapping[str, Any]] = m_tgt.get("files", {})

    src_names = set(src_files.keys())
    tgt_names = set(tgt_files.keys())

    missing_files = sorted(src_names - tgt_names)
    extra_files = sorted(tgt_names - src_names)
    shared_files = sorted(src_names & tgt_names)

    matching_files: list[str] = []
    differing_files: list[dict[str, str]] = []
    for rel in shared_files:
        s_sha = str(src_files[rel]["sha256"])
        t_sha = str(tgt_files[rel]["sha256"])
        if s_sha == t_sha:
            matching_files.append(rel)
        else:
            differing_files.append(
                {"path": rel, "source_sha256": s_sha, "target_sha256": t_sha}
            )

    src_recs_by_file: Mapping[str, Mapping[str, str]] = m_src.get("records", {})
    tgt_recs_by_file: Mapping[str, Mapping[str, str]] = m_tgt.get("records", {})

    conflicts: list[dict[str, str]] = []
    missing_records_on_target: list[dict[str, str]] = []
    extra_records_on_target: list[dict[str, str]] = []
    matching_records: list[dict[str, str]] = []

    for rel in shared_files:
        s_map = src_recs_by_file.get(rel, {})
        t_map = tgt_recs_by_file.get(rel, {})
        s_ids = set(s_map.keys())
        t_ids = set(t_map.keys())

        for rid in sorted(s_ids - t_ids):
            missing_records_on_target.append({"file": rel, "record_id": rid})
        for rid in sorted(t_ids - s_ids):
            extra_records_on_target.append({"file": rel, "record_id": rid})
        for rid in sorted(s_ids & t_ids):
            s_hash = str(s_map[rid])
            t_hash = str(t_map[rid])
            if s_hash == t_hash:
                matching_records.append({"file": rel, "record_id": rid, "sha256": s_hash})
            else:
                conflicts.append(
                    {
                        "file": rel,
                        "record_id": rid,
                        "source_sha256": s_hash,
                        "target_sha256": t_hash,
                    }
                )

    sync_clean = (
        not missing_files
        and not extra_files
        and not differing_files
        and not conflicts
        and not missing_records_on_target
        and not extra_records_on_target
    )

    return {
        "schema": SCHEMA,
        "sync_clean": sync_clean,
        "summary": {
            "source_file_count": len(src_names),
            "target_file_count": len(tgt_names),
            "matching_file_count": len(matching_files),
            "differing_file_count": len(differing_files),
            "missing_file_count": len(missing_files),
            "extra_file_count": len(extra_files),
            "matching_record_count": len(matching_records),
            "record_conflict_count": len(conflicts),
            "missing_record_count": len(missing_records_on_target),
            "extra_record_count": len(extra_records_on_target),
        },
        "files": {
            "matching": matching_files,
            "differing": differing_files,
            "missing_on_target": missing_files,
            "extra_on_target": extra_files,
        },
        "records": {
            "matching": matching_records,
            "conflicts": conflicts,
            "missing_on_target": missing_records_on_target,
            "extra_on_target": extra_records_on_target,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bangun manifest replikasi dan bandingkan dua rumah ACE secara read-only."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_man = sub.add_parser("manifest", help="Bangun manifest hash berkas dan rekaman rumah.")
    p_man.add_argument("--home", required=True, help="Direktori rumah sumber.")
    p_man.add_argument("--out", help="Path output JSON opsional (default stdout).")

    p_cmp = sub.add_parser("compare", help="Bandingkan dua rumah atau dua manifest.")
    p_cmp.add_argument("--source", required=True, help="Direktori atau JSON manifest rumah A.")
    p_cmp.add_argument("--target", required=True, help="Direktori atau JSON manifest rumah B.")
    p_cmp.add_argument("--out", help="Path output JSON opsional (default stdout).")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "manifest":
            result = build_replication_manifest(Path(args.home))
        else:
            result = compare_homes(Path(args.source), Path(args.target))
    except (OSError, json.JSONDecodeError, sqlite3.Error, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
