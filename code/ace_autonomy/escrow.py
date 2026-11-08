"""Durable two-phase external action escrow with HALT_UNCERTAIN enforcement.

Before any external side effect executes, ``DISPATCHED`` intent is durably committed
to SQLite and HMAC-signed. If the process crashes, loses its lease, or receives an
ambiguous transport error before ``finalize_receipt`` commits, automatic retry is
strictly forbidden and the goal enters ``HALT_UNCERTAIN`` until explicit operator
reconciliation.
"""
from __future__ import annotations

import hmac
from typing import Any, Callable
import sqlite3

from .errors import IntegrityError, PolicyError
from .policy import canonical, digest

ESCROW_STATES = frozenset({"DISPATCHED", "COMPLETED", "FAILED", "HALT_UNCERTAIN", "RECONCILED_ABORT"})


class ExternalActionEscrow:
    """Manages HMAC-authenticated external side-effect reservations."""

    def __init__(self, db: sqlite3.Connection, sign_fn: Callable[[Any], str]):
        self.db = db
        self._sign = sign_fn

    def _row_payload(self, row: dict[str, Any] | sqlite3.Row) -> dict[str, Any]:
        return {
            "intent_id": row["intent_id"],
            "goal_id": row["goal_id"],
            "step_index": row["step_index"],
            "action_digest": row["action_digest"],
            "state": row["state"],
            "lease_epoch": row["lease_epoch"],
            "receipt_json": row["receipt_json"],
        }

    def verify_all(self) -> None:
        for row in self.db.execute("SELECT * FROM external_escrow ORDER BY intent_id"):
            if row["state"] not in ESCROW_STATES:
                raise IntegrityError("invalid external_escrow state")
            expected = self._sign(self._row_payload(row))
            if not hmac.compare_digest(expected, row["signature"]):
                raise IntegrityError("external_escrow signature tampered")

    def intent_id_for(self, goal_id: str, step_index: int) -> str:
        return digest({"goal_id": goal_id, "step_index": step_index})

    def get_intent(self, goal_id: str, step_index: int) -> sqlite3.Row | None:
        iid = self.intent_id_for(goal_id, step_index)
        return self.db.execute("SELECT * FROM external_escrow WHERE intent_id=?", (iid,)).fetchone()

    def record_dispatched(
        self,
        goal_id: str,
        step_index: int,
        action: dict[str, Any],
        lease_epoch: int,
    ) -> str:
        existing = self.get_intent(goal_id, step_index)
        if existing is not None:
            raise PolicyError("external action intent already exists; automatic retry is forbidden")
        iid = self.intent_id_for(goal_id, step_index)
        row = {
            "intent_id": iid,
            "goal_id": goal_id,
            "step_index": step_index,
            "action_digest": digest(action),
            "state": "DISPATCHED",
            "lease_epoch": lease_epoch,
            "receipt_json": "null",
        }
        sig = self._sign(row)
        self.db.execute(
            "INSERT INTO external_escrow VALUES (?,?,?,?,?,?,?,?)",
            (
                row["intent_id"],
                row["goal_id"],
                row["step_index"],
                row["action_digest"],
                row["state"],
                row["lease_epoch"],
                row["receipt_json"],
                sig,
            ),
        )
        return iid

    def update_state(
        self,
        goal_id: str,
        step_index: int,
        new_state: str,
        receipt: dict[str, Any] | None,
    ) -> None:
        if new_state not in ESCROW_STATES:
            raise IntegrityError("invalid target escrow state")
        cur = self.get_intent(goal_id, step_index)
        if cur is None:
            raise IntegrityError("missing external_escrow row")
        receipt_json = canonical(receipt) if receipt is not None else cur["receipt_json"]
        updated = {
            "intent_id": cur["intent_id"],
            "goal_id": cur["goal_id"],
            "step_index": cur["step_index"],
            "action_digest": cur["action_digest"],
            "state": new_state,
            "lease_epoch": cur["lease_epoch"],
            "receipt_json": receipt_json,
        }
        sig = self._sign(updated)
        self.db.execute(
            "UPDATE external_escrow SET state=?, receipt_json=?, signature=? WHERE intent_id=?",
            (new_state, receipt_json, sig, cur["intent_id"]),
        )
