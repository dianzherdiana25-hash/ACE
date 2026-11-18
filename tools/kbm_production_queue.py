"""Prepare a checked manuscript and place its bytes in a private local review queue."""

from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
from tempfile import TemporaryDirectory

from tools.kbm_pack_check import DEFAULT_MIN_BYTES
from tools.kbm_pipeline import run_pipeline
from tools.kbm_split import DEFAULT_MIN_WORDS

SCHEMA = "ace.kbm-queue.v1"
STATUS = "WAITING_FOR_HUMAN_REVIEW"
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_PACKAGE_FILES = 250


@contextmanager
def _queue(path: Path, *, writable: bool):
    if writable:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise ValueError("queue must be a private regular file")
    uri = path.absolute().as_uri() + ("?mode=rw" if writable else "?mode=ro")
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection


def _create_tables(connection):
    connection.execute(
        "CREATE TABLE IF NOT EXISTS kbm_review_item ("
        "id TEXT PRIMARY KEY, manifest TEXT NOT NULL, "
        "status TEXT NOT NULL CHECK(status = 'WAITING_FOR_HUMAN_REVIEW'))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS kbm_review_blob ("
        "item_id TEXT NOT NULL REFERENCES kbm_review_item(id), "
        "name TEXT NOT NULL, payload BLOB NOT NULL, PRIMARY KEY(item_id, name))"
    )


def _snapshot(result, bundle):
    source = result["bundle"]["manifest"]
    cover = source["cover"]
    chapters = source["chapters"]
    entries = [(cover["file"], cover)] + [(chapter["bundle_file"], chapter) for chapter in chapters]
    if len(entries) > MAX_PACKAGE_FILES or sum(row["size_bytes"] for _, row in entries) > MAX_PACKAGE_BYTES:
        raise ValueError("checked package exceeds local queue limit")
    payloads = {}
    for name, row in entries:
        if name in payloads or Path(name).name != name or name in {".", ".."}:
            raise ValueError("invalid or duplicate bundled filename")
        payload = (bundle / name).read_bytes()
        if len(payload) != row["size_bytes"] or hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise ValueError("checked bundle bytes changed before enqueue")
        payloads[name] = payload

    manifest = {
        "schema": SCHEMA, "cover": cover,
        "chapters": [{key: value for key, value in chapter.items() if key != "source_file"}
                     for chapter in chapters],
    }
    record = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return record, payloads


def enqueue(manuscript, cover, queue_path, *, min_words=DEFAULT_MIN_WORDS, min_bytes=DEFAULT_MIN_BYTES):
    manuscript = Path(manuscript)
    cover = Path(cover)
    queue_path = Path(queue_path)
    if not all(path.is_file() and not path.is_symlink() for path in (manuscript, cover)):
        raise ValueError("manuscript and cover must be ordinary local files")
    if sum(path.stat().st_size for path in (manuscript, cover)) > MAX_PACKAGE_BYTES:
        raise ValueError("source exceeds local queue limit")
    with TemporaryDirectory(prefix="ace-kbm-production-") as tmp:
        scratch = Path(tmp)
        bundle = scratch / "bundle"
        result = run_pipeline(manuscript, scratch / "split", min_words=min_words,
                              min_bytes=min_bytes, cover_source=cover,
                              bundle_dir=bundle, strict_cover=True)
        if not result["passed"]:
            return {"schema": SCHEMA, "queued": False, "failed_stage": result["failed_stage"],
                    "errors": sorted({error["code"] for error in result["pack_check"]["errors"]}),
                    "upload_authorized": False}
        record, payloads = _snapshot(result, bundle)

    item_id = hashlib.sha256(record.encode("utf-8")).hexdigest()
    with _queue(queue_path, writable=True) as connection, connection:
        _create_tables(connection)
        found = connection.execute(
            "INSERT OR IGNORE INTO kbm_review_item(id, manifest, status) VALUES (?, ?, ?)",
            (item_id, record, STATUS),
        ).rowcount
        if found:
            connection.executemany(
                "INSERT INTO kbm_review_blob VALUES (?, ?, ?)",
                ((item_id, name, payload) for name, payload in sorted(payloads.items())),
            )
        else:
            saved = connection.execute(
                "SELECT manifest FROM kbm_review_item WHERE id = ?", (item_id,)
            ).fetchone()
            saved_blobs = dict(connection.execute(
                "SELECT name, payload FROM kbm_review_blob WHERE item_id = ?", (item_id,)
            ))
            if saved != (record,) or saved_blobs != payloads:
                raise ValueError("existing queue item failed integrity verification")
    return {"schema": SCHEMA, "queued": True, "id": item_id, "inserted": bool(found),
            "status": STATUS, "files": len(payloads), "upload_authorized": False}


def list_items(queue_path):
    path = Path(queue_path)
    if not path.exists() and not path.is_symlink():
        return []
    with _queue(path, writable=False) as connection:
        # A process can stop after exclusive allocation but before initialization.
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'kbm_review_item' AND type = 'table'"
        ).fetchone()
        if not exists:
            return []
        rows = connection.execute(
            "SELECT id, status, manifest FROM kbm_review_item ORDER BY rowid"
        )
        return [{"id": key, "status": status, "manifest": json.loads(manifest)}
                for key, status, manifest in rows]


def export_review(queue_path, item_id, destination):
    """Materialize a verified package for local review in a fresh directory."""
    with _queue(Path(queue_path), writable=False) as connection:
        connection.execute("BEGIN")
        row = connection.execute(
            "SELECT manifest, status FROM kbm_review_item WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown queue item")
        record, status = row
        if status != STATUS or hashlib.sha256(record.encode("utf-8")).hexdigest() != item_id:
            raise ValueError("queue manifest failed integrity verification")
        payloads = dict(connection.execute(
            "SELECT name, payload FROM kbm_review_blob WHERE item_id = ?", (item_id,)
        ))
    manifest = json.loads(record)
    cover = manifest["cover"]
    entries = [(cover["file"], cover)] + [
        (chapter["bundle_file"], chapter) for chapter in manifest["chapters"]
    ]
    if len(entries) != len(payloads) or {name for name, _ in entries} != set(payloads):
        raise ValueError("queue file set failed integrity verification")
    for name, expected in entries:
        payload = payloads[name]
        if (Path(name).name != name or name in {".", "..", "review_manifest.json"} or "\\" in name
                or not isinstance(payload, bytes) or len(payload) != expected["size_bytes"]
                or hashlib.sha256(payload).hexdigest() != expected["sha256"]):
            raise ValueError("queue payload failed integrity verification")

    target = Path(destination)
    target.mkdir(mode=0o700)
    try:
        for name, payload in payloads.items():
            (target / name).write_bytes(payload)
        (target / "review_manifest.json").write_text(record + "\n", encoding="utf-8")
    except OSError:
        shutil.rmtree(target)
        raise
    return {"schema": SCHEMA, "id": item_id, "files": len(payloads),
            "status": STATUS, "upload_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    add = sub.add_parser("enqueue")
    add.add_argument("manuscript", type=Path)
    add.add_argument("cover", type=Path)
    add.add_argument("--min-words", type=int, default=DEFAULT_MIN_WORDS)
    add.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    sub.add_parser("list")
    review = sub.add_parser("export-review")
    review.add_argument("item_id")
    review.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "enqueue":
            result = enqueue(args.manuscript, args.cover, args.queue,
                             min_words=args.min_words, min_bytes=args.min_bytes)
        elif args.operation == "list":
            result = {"schema": SCHEMA, "items": list_items(args.queue), "upload_authorized": False}
        else:
            result = export_review(args.queue, args.item_id, args.destination)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"KBM queue: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("queued", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
