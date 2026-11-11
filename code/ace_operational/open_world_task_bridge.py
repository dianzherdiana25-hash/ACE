"""Durable, read-only Open-World planning adapter for the existing ACE stores.

This module creates a versioned plan journal INSIDE OperationalStore's SQLite
database. It does not introduce a competing ACE task state machine. A separate
MissionBus can optionally queue a *review-only* mission, never a candidate
capability execution. Exact stored contract snapshots make retries reproducible.

Trust boundaries:
- SHA-256 detects accidental/local-record tampering; it is not independent
  evidence custody when the database owner is compromised.
- Evidence references in capability contracts are NOT authenticated here.
- READY means a type-compatible route, not completion or execution.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from ace_mission.bus import MissionBus
from .open_world_planner import CapabilityRegistry, plan_capabilities, _tokens
from .open_world_review_bus import queue_structural_review
from .store import OperationalStore, utc_now_iso

SCHEMA = "ace.open_world.plan.v1"


def _canonical(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contracts(registry: CapabilityRegistry) -> list[dict[str, Any]]:
    items = []
    for cap in registry.list_all():
        items.append({
            "capability_id": cap.capability_id,
            "consumes": sorted(cap.consumes),
            "produces": sorted(cap.produces),
            "provider": cap.provider,
            "status": cap.status,
            "evidence_ref": cap.evidence_ref,
            "effect": cap.effect,
            "cost_units": cap.cost_units,
        })
    return items


class OpenWorldTaskBridge:
    """Thin same-database integration for planning, replay and mission review."""

    def __init__(self, store: OperationalStore):
        self.store = store
        # Reuse OperationalStore's WAL connection + reentrant lock, rather than
        # creating a second task store. Any future store refactor should expose
        # this transaction as a public migration/API.
        with store._lock:
            store._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS open_world_plans (
                    plan_key TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            store._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_open_world_task "
                "ON open_world_plans(task_id, created_at)"
            )
            store._conn.commit()

    def plan_and_record(
        self,
        task_id: str,
        registry: CapabilityRegistry,
        *,
        available_types: Iterable[str],
        goal_types: Iterable[str],
        allowed_effects: Iterable[str] = ("none", "read"),
        max_steps: int = 12,
        max_expansions: int = 1000,
        max_cost_units: int = 100,
    ) -> dict[str, Any]:
        if self.store.get_task(task_id) is None:
            raise KeyError(f"Unknown ACE task: {task_id}")

        request: dict[str, Any] = {
            "schema": SCHEMA,
            "task_id": task_id,
            "capability_snapshot": _contracts(registry),
            "available_types": sorted(_tokens(available_types, "available_types")),
            "goal_types": sorted(_tokens(goal_types, "goal_types")),
            "allowed_effects": sorted(_tokens(allowed_effects, "allowed_effects")),
            "max_steps": max_steps,
            "max_expansions": max_expansions,
            "max_cost_units": max_cost_units,
        }
        # Validate and derive plan before touching the journal.
        result = plan_capabilities(
            registry,
            available_types=request["available_types"],
            goal_types=request["goal_types"],
            allowed_effects=request["allowed_effects"],
            max_steps=max_steps,
            max_expansions=max_expansions,
            max_cost_units=max_cost_units,
        )
        result_data: dict[str, Any] = {
            "status": result.status,
            "capability_ids": list(result.capability_ids),
            "acquired_types": sorted(result.acquired_types),
            "missing_types": sorted(result.missing_types),
            "expanded_states": result.expanded_states,
            "total_cost_units": result.total_cost_units,
            "execution_performed": False,
            "scientific_status": "NOT_ASSESSED",
            "release_gate": "BLOCK_RELEASE",
        }
        request_json = _canonical(request)
        result_json = _canonical(result_data)
        plan_key = "ow_" + _sha256(request_json)
        record_sha256 = _sha256(request_json + "\n" + result_json)
        with self.store._lock:
            # Keep the immutable journal row idempotent across processes.
            self.store._conn.execute(
                """
                INSERT OR IGNORE INTO open_world_plans(
                    plan_key, task_id, request_json, result_json, record_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (plan_key, task_id, request_json, result_json, record_sha256, utc_now_iso()),
            )
            self.store._conn.commit()

        persisted = self.get_plan(plan_key)
        if persisted["record_sha256"] != record_sha256:
            raise ValueError("Same plan key has a different recorded result")
        return persisted

    def get_plan(self, plan_key: str) -> dict[str, Any]:
        with self.store._lock:
            row = self.store._conn.execute(
                """
                SELECT plan_key, task_id, request_json, result_json,
                       record_sha256, created_at
                FROM open_world_plans WHERE plan_key = ?
                """,
                (plan_key,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown open-world plan: {plan_key}")
        request_json, result_json = row["request_json"], row["result_json"]
        if (
            row["plan_key"] != "ow_" + _sha256(request_json)
            or row["record_sha256"] != _sha256(request_json + "\n" + result_json)
        ):
            raise ValueError("Open-world plan journal integrity check failed")
        request = json.loads(request_json)
        result = json.loads(result_json)
        if (request.get("schema") != SCHEMA
                or request.get("task_id") != row["task_id"]
                or result.get("execution_performed") is not False):
            raise ValueError("Malformed open-world plan journal record")
        return {
            "plan_key": row["plan_key"],
            "task_id": row["task_id"],
            "request": request,
            "result": result,
            "record_sha256": row["record_sha256"],
            "created_at": row["created_at"],
        }

    def list_plan_keys(self, task_id: str) -> list[str]:
        if self.store.get_task(task_id) is None:
            raise KeyError(f"Unknown ACE task: {task_id}")
        with self.store._lock:
            rows = self.store._conn.execute(
                "SELECT plan_key FROM open_world_plans "
                "WHERE task_id = ? ORDER BY created_at ASC, plan_key ASC",
                (task_id,),
            ).fetchall()
        return [row["plan_key"] for row in rows]

    def stage_review_mission(
        self,
        plan_key: str,
        bus: MissionBus,
        *,
        authorize_local_queue: bool = False,
    ) -> dict[str, Any]:
        """Queue an idempotent review task, NEVER capability execution.

        Local queue creation requires explicit caller authorization. Review
        the immutable contract snapshot; do not access remote providers,
        write code, or trust the string evidence references as attestations.
        """
        if not authorize_local_queue:
            raise PermissionError("Local mission queue requires explicit authorization")
        snapshot = self.get_plan(plan_key)
        if snapshot["result"]["status"] != "READY":
            raise ValueError("Cannot stage an unplannable result")
        caps = {c["capability_id"]: c for c in snapshot["request"]["capability_snapshot"]}
        for cap_id in snapshot["result"]["capability_ids"]:
            cap = caps.get(cap_id)
            if (cap is None or cap["status"] != "VERIFIED"
                    or not cap["evidence_ref"].strip()
                    or cap["effect"] not in ("none", "read")):
                raise PermissionError("Review queue rejects unsafe/changed capability contract")
        if not bus.verify_hash_chain():
            raise ValueError("MissionBus chain verification failed")

        mission_id = queue_structural_review(
            bus, plan_key=plan_key, record_sha256=snapshot["record_sha256"]
        )
        return {
            "mission_id": mission_id,
            "plan_key": plan_key,
            "status": "PENDING_REVIEW",
            "execution_performed": False,
        }
