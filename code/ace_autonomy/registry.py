"""Authenticated CapabilityRegistry recording only IndependentVerifier-approved capabilities."""
from __future__ import annotations

import hmac
import json
import sqlite3
from typing import Any, Callable

from .errors import IntegrityError
from .policy import canonical, digest

CAPABILITY_STATUSES = frozenset({"VERIFIED_OPERATIONAL", "STAGED_CANDIDATE_UNEXECUTED"})


class CapabilityRegistry:
    """Stores operational capabilities bound to signed step verification receipts."""

    def __init__(self, db: sqlite3.Connection, sign_fn: Callable[[Any], str]):
        self.db = db
        self._sign = sign_fn

    def _row_payload(self, row: dict[str, Any] | sqlite3.Row) -> dict[str, Any]:
        return {
            "cap_id": row["cap_id"],
            "goal_id": row["goal_id"],
            "step_index": row["step_index"],
            "kind": row["kind"],
            "artifact_digest": row["artifact_digest"],
            "domain_scope": row["domain_scope"],
            "status": row["status"],
            "event_signature": row["event_signature"],
            "metadata_json": row["metadata_json"],
        }

    def verify_all(self, valid_event_sigs: set[str]) -> None:
        for row in self.db.execute("SELECT * FROM capability_registry ORDER BY cap_id"):
            if row["status"] not in CAPABILITY_STATUSES:
                raise IntegrityError("invalid capability_registry status")
            if row["event_signature"] not in valid_event_sigs:
                raise IntegrityError("capability_registry references unknown or unverified event signature")
            expected = self._sign(self._row_payload(row))
            if not hmac.compare_digest(expected, row["signature"]):
                raise IntegrityError("capability_registry signature tampered")

    def register_verified(
        self,
        *,
        goal_id: str,
        step_index: int,
        kind: str,
        artifact_digest: str,
        domain_scope: str,
        status: str,
        event_signature: str,
        metadata: dict[str, Any],
    ) -> str:
        if status not in CAPABILITY_STATUSES:
            raise IntegrityError("unsupported capability status")
        cap_id = digest({
            "goal_id": goal_id,
            "step_index": step_index,
            "kind": kind,
            "artifact_digest": artifact_digest,
        })
        meta_json = canonical(metadata)
        row = {
            "cap_id": cap_id,
            "goal_id": goal_id,
            "step_index": step_index,
            "kind": kind,
            "artifact_digest": artifact_digest,
            "domain_scope": domain_scope,
            "status": status,
            "event_signature": event_signature,
            "metadata_json": meta_json,
        }
        sig = self._sign(row)
        self.db.execute(
            "INSERT OR REPLACE INTO capability_registry VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                row["cap_id"],
                row["goal_id"],
                row["step_index"],
                row["kind"],
                row["artifact_digest"],
                row["domain_scope"],
                row["status"],
                row["event_signature"],
                row["metadata_json"],
                sig,
            ),
        )
        return cap_id

    def list_capabilities(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in self.db.execute("SELECT * FROM capability_registry ORDER BY step_index, cap_id"):
            out.append({
                "cap_id": r["cap_id"],
                "goal_id": r["goal_id"],
                "step_index": r["step_index"],
                "kind": r["kind"],
                "artifact_digest": r["artifact_digest"],
                "domain_scope": r["domain_scope"],
                "status": r["status"],
                "metadata": json.loads(r["metadata_json"]),
            })
        return out
