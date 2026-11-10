"""Experimental SQLite admission store for ACE self-development (M1 research slice).

This is not wired to the legacy JSON StateManager. An epoch fences ONLY writes
that pass through this database; external Git operations require their own gate.
The database MUST live on local app-private storage, never a network filesystem.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any


class LeaseRejected(RuntimeError):
    """A lease is active, expired, or this caller no longer owns it."""


class EventConflict(RuntimeError):
    """An event ID was replayed with different content."""


@dataclass(frozen=True)
class Lease:
    job_id: str
    owner: str
    token: str
    epoch: int
    expires_at: float


class FencedStore:
    """SQLite-backed fenced, durable receipts and outbox; no external effects."""

    def __init__(self, db_path: str | Path, *, timeout: float = 5.0):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        if self.path.is_symlink():
            raise ValueError("SQLite database path must not be a symlink")
        with self._connect() as con:
            # WAL requires a local filesystem and may leave .db-wal/.db-shm files.
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS counter (
                    id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL CHECK(epoch>=0));
                INSERT OR IGNORE INTO counter(id, epoch) VALUES (1, 0);
                CREATE TABLE IF NOT EXISTS leases (
                    job_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    token TEXT NOT NULL, epoch INTEGER NOT NULL,
                    expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, event_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL, content_hash TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    UNIQUE(job_id, event_id));
                CREATE TABLE IF NOT EXISTS checkpoint (
                    job_id TEXT PRIMARY KEY, event_seq INTEGER NOT NULL,
                    epoch INTEGER NOT NULL, content_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS outbox (
                    job_id TEXT NOT NULL, event_id TEXT NOT NULL,
                    delivery_state TEXT NOT NULL DEFAULT 'PENDING',
                    PRIMARY KEY(job_id, event_id));
            """)

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(str(self.path), timeout=self.timeout, isolation_level=None)
        try:
            con.execute(f"PRAGMA busy_timeout={max(1, int(self.timeout*1000))}")
            con.execute("PRAGMA synchronous=FULL")
            yield con
        finally:
            con.close()  # sqlite3.Connection's own context manager does NOT close it

    @staticmethod
    def _validate(value: str, label: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError(f"Invalid {label}")

    @staticmethod
    def _begin(con: sqlite3.Connection) -> None:
        con.execute("BEGIN IMMEDIATE")

    @staticmethod
    def _active(con: sqlite3.Connection, lease: Lease, now: float) -> None:
        row = con.execute(
            "SELECT owner,token,epoch,expires_at FROM leases WHERE job_id=?",
            (lease.job_id,)).fetchone()
        if (row is None or row[0] != lease.owner or row[1] != lease.token
                or row[2] != lease.epoch or row[3] <= now):
            raise LeaseRejected("stale, expired, or unauthorized lease")

    def acquire(self, job_id: str, owner: str, *, ttl: float = 30.0,
                now: float | None = None) -> Lease:
        self._validate(job_id, "job_id")
        self._validate(owner, "owner")
        if not 0 < ttl <= 86400:
            raise ValueError("ttl outside allowed range")
        t = time.time() if now is None else now
        with self._connect() as con:
            self._begin(con)
            row = con.execute("SELECT expires_at FROM leases WHERE job_id=?", (job_id,)).fetchone()
            if row is not None and row[0] > t:
                raise LeaseRejected("job already leased")
            con.execute("UPDATE counter SET epoch=epoch+1 WHERE id=1")
            epoch = con.execute("SELECT epoch FROM counter WHERE id=1").fetchone()[0]
            lease = Lease(job_id, owner, secrets.token_hex(16), epoch, t + ttl)
            con.execute("""INSERT INTO leases(job_id,owner,token,epoch,expires_at)
                           VALUES (?,?,?,?,?)
                           ON CONFLICT(job_id) DO UPDATE SET owner=excluded.owner,
                               token=excluded.token, epoch=excluded.epoch,
                               expires_at=excluded.expires_at""",
                        (lease.job_id, lease.owner, lease.token, lease.epoch, lease.expires_at))
            con.commit()
            return lease

    def renew(self, lease: Lease, *, ttl: float = 30.0,
              now: float | None = None) -> Lease:
        if not 0 < ttl <= 86400:
            raise ValueError("ttl outside allowed range")
        t = time.time() if now is None else now
        with self._connect() as con:
            self._begin(con)
            self._active(con, lease, t)
            new = Lease(lease.job_id, lease.owner, lease.token, lease.epoch, t + ttl)
            con.execute("UPDATE leases SET expires_at=? WHERE job_id=?",
                        (new.expires_at, new.job_id))
            con.commit()
            return new

    def release(self, lease: Lease, *, now: float | None = None) -> None:
        t = time.time() if now is None else now
        with self._connect() as con:
            self._begin(con)
            self._active(con, lease, t)
            con.execute("DELETE FROM leases WHERE job_id=?", (lease.job_id,))
            con.commit()

    def append_receipt(self, lease: Lease, event_id: str, content: dict[str, Any],
                       *, now: float | None = None) -> int:
        """Atomically commit receipt, checkpoint and pending outbox item.

        The caller must use the returned sequence to correlate external receipts;
        resending a previously committed event with identical content is idempotent.
        """
        self._validate(event_id, "event_id")
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        t = time.time() if now is None else now
        with self._connect() as con:
            self._begin(con)
            self._active(con, lease, t)
            previous = con.execute("""SELECT seq,epoch,content_hash,content_json
                                    FROM events WHERE job_id=? AND event_id=?""",
                                   (lease.job_id, event_id)).fetchone()
            if previous is not None:
                if previous[1] != lease.epoch or previous[2] != digest or previous[3] != canonical:
                    raise EventConflict("event replay differs from original")
                con.commit()
                return previous[0]
            cur = con.execute("""INSERT INTO events(job_id,event_id,epoch,content_hash,content_json)
                                 VALUES(?,?,?,?,?)""",
                              (lease.job_id, event_id, lease.epoch, digest, canonical))
            seq = cur.lastrowid
            con.execute("""INSERT INTO checkpoint(job_id,event_seq,epoch,content_hash)
                           VALUES(?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET
                           event_seq=excluded.event_seq, epoch=excluded.epoch,
                           content_hash=excluded.content_hash""",
                        (lease.job_id, seq, lease.epoch, digest))
            con.execute("INSERT INTO outbox(job_id,event_id) VALUES(?,?)", (lease.job_id, event_id))
            con.commit()
            return seq

    def pending_outbox(self, job_id: str) -> list[tuple[str, str]]:
        """Read-only replay queue; side-effect delivery requires idempotent receiver."""
        with self._connect() as con:
            return con.execute("""SELECT o.event_id, e.content_json FROM outbox o
                                  JOIN events e ON e.job_id=o.job_id AND e.event_id=o.event_id
                                  WHERE o.job_id=? AND o.delivery_state='PENDING'
                                  ORDER BY e.seq""", (job_id,)).fetchall()

    def ack_outbox(self, lease: Lease, event_id: str, *, now: float | None = None) -> None:
        t = time.time() if now is None else now
        with self._connect() as con:
            self._begin(con)
            self._active(con, lease, t)
            cur = con.execute("""UPDATE outbox SET delivery_state='DELIVERED'
                                 WHERE job_id=? AND event_id=?""", (lease.job_id, event_id))
            if cur.rowcount != 1:
                raise KeyError(event_id)
            con.commit()

    def snapshot(self, job_id: str) -> tuple[int, int, str] | None:
        with self._connect() as con:
            return con.execute("SELECT event_seq,epoch,content_hash FROM checkpoint WHERE job_id=?",
                               (job_id,)).fetchone()
