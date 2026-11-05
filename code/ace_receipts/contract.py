"""Evaluator-owned durable action receipts; no network calls or paid retries.

A caller MUST commit dispatch() before invoking the external provider.
After a crash, DISPATCHED without a verified receipt is HALT_UNCERTAIN.
An external provider must implement durable idempotency independently.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

class ReceiptError(RuntimeError):
    pass

class UncertainAction(ReceiptError):
    pass

class ReceiptBook:
    def __init__(self, path: str | Path):
        path = Path(path)
        if path.is_symlink():
            raise ReceiptError("database symlink forbidden")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS actions (
            key TEXT PRIMARY KEY, payload TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN
            ('RESERVED','DISPATCHED','SUCCEEDED','FAILED','HALT_UNCERTAIN')),
            receipt TEXT)""")

    def close(self):
        self.db.close()

    @staticmethod
    def _encode(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def _row(self, key):
        return self.db.execute(
            "SELECT payload,state,receipt FROM actions WHERE key=?", (key,)
        ).fetchone()

    def reserve(self, key: str, payload: dict) -> str:
        if not isinstance(key, str) or not key or len(key) > 200:
            raise ReceiptError("invalid idempotency key")
        if not isinstance(payload, dict):
            raise ReceiptError("payload must be object")
        encoded = self._encode(payload)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(key)
            if row is None:
                self.db.execute("INSERT INTO actions VALUES (?,?,?,NULL)",
                                (key, encoded, "RESERVED"))
                result = "RESERVED"
            elif row[0] != encoded:
                raise ReceiptError("idempotency key reused for different payload")
            else:
                result = row[1]
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def dispatch(self, key: str) -> None:
        """Durably claim exactly one *local* dispatch; caller invokes provider afterward."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(key)
            if row is None:
                raise ReceiptError("reserve before dispatch")
            if row[1] != "RESERVED":
                raise UncertainAction("dispatch not allowed: " + row[1])
            self.db.execute("UPDATE actions SET state='DISPATCHED' WHERE key=?", (key,))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def reconcile(self, key: str, receipt: dict,
                  verify: Callable[[str, dict, dict], bool]) -> str:
        """Accept ONLY externally authenticated evidence, not researcher assertion."""
        if not isinstance(receipt, dict):
            raise ReceiptError("receipt must be object")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(key)
            if row is None or row[1] == "RESERVED":
                raise ReceiptError("receipt for non-dispatched action")
            if row[1] in ("SUCCEEDED", "FAILED"):
                if row[2] != self._encode(receipt):
                    raise ReceiptError("conflicting terminal receipt")
                result = row[1]
            else:
                payload = json.loads(row[0])
                if not callable(verify) or verify(key, payload, receipt) is not True:
                    raise ReceiptError("unverified external receipt")
                if receipt.get("key") != key or receipt.get("outcome") not in ("SUCCEEDED", "FAILED"):
                    raise ReceiptError("invalid receipt binding or outcome")
                result = receipt["outcome"]
                self.db.execute("UPDATE actions SET state=?,receipt=? WHERE key=?",
                                (result, self._encode(receipt), key))
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def recover(self) -> list[tuple[str, str]]:
        """Fail closed on all nonterminal actions, including pre-dispatch reservations.

        RESERVED might be safe to cancel manually, but never auto-retry here.
        """
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("""UPDATE actions SET state='HALT_UNCERTAIN'
                WHERE state IN ('RESERVED','DISPATCHED')""")
            rows = self.db.execute(
                "SELECT key,state FROM actions ORDER BY key").fetchall()
            self.db.execute("COMMIT")
            return rows
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def status(self, key: str) -> str | None:
        row = self._row(key)
        return row[1] if row else None
