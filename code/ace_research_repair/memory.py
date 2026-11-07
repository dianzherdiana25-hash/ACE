"""Durable SQLite WAL `RepairMemory` (`Remember`) with hash-chained integrity verification.

Persists validated `(runtime_model_id, trace_regime, fine_signature, ast_node_kind) ->
(operator_family, operator_name)` repair schemas across process restarts and verifies
event-chain custody on every read and write. Never imports `evaluator.py`.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any

from .corpus import canonical_json, sha256_digest

MEMORY_SCHEMA = "ace.repair.memory.v1"
MAX_MEMORY_RECORDS = 512


class MemoryIntegrityError(ValueError):
    """Raised when stored `RepairMemory` state or hash-linked events fail verification."""


def _encode(value: Any) -> str:
    return canonical_json(value).decode("utf-8")


class RepairMemory:
    """Transactional SQLite WAL store for validated software repair schemas."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repairs (
                    record_id TEXT PRIMARY KEY,
                    ordinal INTEGER NOT NULL UNIQUE,
                    unit_id TEXT NOT NULL,
                    runtime_model_id TEXT NOT NULL,
                    trace_regime TEXT NOT NULL,
                    fine_signature TEXT NOT NULL,
                    ast_node_kind TEXT NOT NULL,
                    operator_family TEXT NOT NULL,
                    operator_name TEXT NOT NULL,
                    patch_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    previous TEXT NOT NULL,
                    hash TEXT NOT NULL
                );
                """
            )
            with self._transaction(write=True):
                self.db.execute(
                    "INSERT OR IGNORE INTO metadata VALUES ('schema', ?)",
                    (MEMORY_SCHEMA,),
                )
                self._verify()
        except BaseException:
            self.db.close()
            raise

    def __enter__(self) -> RepairMemory:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def _transaction(self, *, write: bool = True):
        self.db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _verify(self) -> None:
        meta = dict(self.db.execute("SELECT key, value FROM metadata").fetchall())
        if meta != {"schema": MEMORY_SCHEMA}:
            raise MemoryIntegrityError("repair memory schema mismatch")

        repairs = {
            row["record_id"]: row
            for row in self.db.execute("SELECT * FROM repairs ORDER BY ordinal")
        }
        if len(repairs) > MAX_MEMORY_RECORDS:
            raise MemoryIntegrityError("repair memory capacity exceeded")

        previous = "0" * 64
        seen_records: set[str] = set()
        for expected_seq, ev in enumerate(self.db.execute("SELECT * FROM events ORDER BY seq"), 1):
            payload_obj = json.loads(ev["payload"])
            expected_event = {
                "seq": expected_seq,
                "kind": ev["kind"],
                "record_id": ev["record_id"],
                "payload": payload_obj,
                "previous": previous,
            }
            if (
                ev["seq"] != expected_seq
                or ev["previous"] != previous
                or sha256_digest(expected_event) != ev["hash"]
            ):
                raise MemoryIntegrityError("repair memory event hash chain corrupted")
            if ev["kind"] != "remembered" or ev["record_id"] in seen_records:
                raise MemoryIntegrityError("unexpected or duplicate repair memory event")
            row = repairs.get(ev["record_id"])
            if row is None:
                raise MemoryIntegrityError("orphaned repair memory event")
            stored_payload = json.loads(row["payload"])
            if _encode(payload_obj) != _encode(stored_payload) or sha256_digest(stored_payload) != row["record_id"]:
                raise MemoryIntegrityError("repair record disagrees with event receipt")
            if (
                stored_payload.get("unit_id") != row["unit_id"]
                or stored_payload.get("runtime_model_id") != row["runtime_model_id"]
                or stored_payload.get("operator_family") != row["operator_family"]
                or stored_payload.get("operator_name") != row["operator_name"]
                or stored_payload.get("patch_id") != row["patch_id"]
            ):
                raise MemoryIntegrityError("repair column metadata tampered")
            seen_records.add(ev["record_id"])
            previous = ev["hash"]

        if set(repairs.keys()) != seen_records:
            raise MemoryIntegrityError("repair record missing event receipt")

    def remember_validated_repair(
        self,
        *,
        unit_id: str,
        runtime_model_id: str,
        trace_regime: str,
        fine_signature: str,
        ast_node_kind: str,
        operator_family: str,
        operator_name: str,
        patch_id: str,
    ) -> dict[str, Any]:
        """Stage 8 (`Remember`): Persist a verified repair schema atomically (idempotent)."""
        if not runtime_model_id:
            raise ValueError("validated repair requires a non-empty runtime_model_id")
        record_payload = {
            "ast_node_kind": ast_node_kind,
            "fine_signature": fine_signature,
            "operator_family": operator_family,
            "operator_name": operator_name,
            "patch_id": patch_id,
            "runtime_model_id": runtime_model_id,
            "trace_regime": trace_regime,
            "unit_id": unit_id,
        }
        record_id = sha256_digest(record_payload)
        with self._transaction(write=True):
            self._verify()
            existing = self.db.execute(
                "SELECT ordinal FROM repairs WHERE record_id = ?",
                (record_id,),
            ).fetchone()
            if existing is not None:
                return {
                    "record_id": record_id,
                    "inserted": False,
                    "ordinal": int(existing["ordinal"]),
                }
            count = int(self.db.execute("SELECT COUNT(*) FROM repairs").fetchone()[0])
            if count >= MAX_MEMORY_RECORDS:
                raise ValueError("repair memory capacity exhausted")
            ordinal = count + 1
            self.db.execute(
                """
                INSERT INTO repairs (
                    record_id, ordinal, unit_id, runtime_model_id, trace_regime,
                    fine_signature, ast_node_kind, operator_family, operator_name,
                    patch_id, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    ordinal,
                    unit_id,
                    runtime_model_id,
                    trace_regime,
                    fine_signature,
                    ast_node_kind,
                    operator_family,
                    operator_name,
                    patch_id,
                    _encode(record_payload),
                ),
            )
            last_ev = self.db.execute(
                "SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = int(last_ev["seq"]) + 1 if last_ev is not None else 1
            prev_hash = str(last_ev["hash"]) if last_ev is not None else "0" * 64
            event_obj = {
                "seq": seq,
                "kind": "remembered",
                "record_id": record_id,
                "payload": record_payload,
                "previous": prev_hash,
            }
            self.db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    seq,
                    "remembered",
                    record_id,
                    _encode(record_payload),
                    prev_hash,
                    sha256_digest(event_obj),
                ),
            )
        return {
            "record_id": record_id,
            "inserted": True,
            "ordinal": ordinal,
        }

    def query_priors(
        self,
        runtime_model_id: str | None,
        fine_signature: str,
    ) -> dict[str, Any]:
        """Retrieve empirical `(runtime_model_id -> operator_family)` and fine priors."""
        with self._transaction(write=False):
            self._verify()
            if not runtime_model_id:
                return {
                    "matched_capability_records": 0,
                    "family_counts": {},
                    "operator_counts": {},
                }
            rows = self.db.execute(
                "SELECT fine_signature, operator_family, operator_name FROM repairs WHERE runtime_model_id = ? ORDER BY ordinal",
                (runtime_model_id,),
            ).fetchall()
            family_counts: dict[str, int] = {}
            operator_counts: dict[str, int] = {}
            for row in rows:
                fam = str(row["operator_family"])
                op = str(row["operator_name"])
                family_counts[fam] = family_counts.get(fam, 0) + 1
                if str(row["fine_signature"]) == fine_signature:
                    operator_counts[op] = operator_counts.get(op, 0) + 1
            return {
                "matched_capability_records": len(rows),
                "family_counts": dict(sorted(family_counts.items())),
                "operator_counts": dict(sorted(operator_counts.items())),
            }

    def status(self) -> dict[str, Any]:
        with self._transaction(write=False):
            self._verify()
            rows = self.db.execute(
                "SELECT record_id, ordinal, unit_id, runtime_model_id, operator_family, operator_name, patch_id FROM repairs ORDER BY ordinal"
            ).fetchall()
            last_ev = self.db.execute(
                "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            return {
                "schema": MEMORY_SCHEMA,
                "total_records": len(rows),
                "head_event_hash": str(last_ev["hash"]) if last_ev is not None else "0" * 64,
                "records": [
                    {
                        "record_id": str(r["record_id"]),
                        "ordinal": int(r["ordinal"]),
                        "unit_id": str(r["unit_id"]),
                        "runtime_model_id": str(r["runtime_model_id"]),
                        "operator_family": str(r["operator_family"]),
                        "operator_name": str(r["operator_name"]),
                        "patch_id": str(r["patch_id"]),
                    }
                    for r in rows
                ],
            }
