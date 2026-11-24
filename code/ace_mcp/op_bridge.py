"""Operational tool surface for ACE MCP (tool layer v1).

Exposes the operational substrate (`ace_operational`: OperationalStore
tasks/receipts/skills/frontier/gaps/work orders and the OMEGA-07
cognitive memory) as MCP tools, per ACE_TOOL_LAYER_PLAN_v1.md
(decisions D1-D5, owner 2026-11-24):

- ONE core: this bridge is the operational core. The MCP server
  (`ace_mcp.server`) and the thin CLI (`ace_mcp.cli`) both call it;
  neither duplicates its logic.
- Agents are FREE to use and modify ACE (D3). Write tools are gated
  only by the bridge's existing operator opt-in (`allow_writes`,
  ACE's own mechanism, like the self-send marker) - never by
  per-tool permission tiers. Accountability comes from ACE's native
  traceability: every mutating call emits a store event naming the
  calling agent, file writes are preimage-hash guarded and atomic,
  and memory writes carry honest provenance (agent statements are
  `external`, never dressed up as operator or evidence).
- Vendor-neutral (D4): plain stdlib, plain JSON, no SDK.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ace_operational.memory_bridge import ConversationalMemoryManager
from ace_operational.store import OperationalStore


def _spec(name: str, description: str, properties: dict, required: tuple = (), *, write: bool = False) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": list(required),
        },
        "annotations": {"readOnlyHint": not write, "destructiveHint": False},
    }


_STR = {"type": "string"}
_AGENT_PROP = {"agent": {"type": "string", "maxLength": 80,
                         "description": "Calling agent's name, recorded for traceability."}}

OP_TOOL_SPECS = (
    _spec("ace_op_status",
          "Operational status summary: task counts by status, open gaps, active skills, frontier counts, memory summary.",
          {}),
    _spec("ace_op_task_list",
          "List operational tasks (newest first).",
          {"limit": {"type": "integer", "minimum": 1, "maximum": 200}}),
    _spec("ace_op_task_get",
          "Get one operational task with its receipts and work orders.",
          {"task_id": _STR}, ("task_id",)),
    _spec("ace_op_task_create",
          "Create an operational task in ACE's store.",
          {**_AGENT_PROP,
           "title": _STR, "goal": _STR,
           "kind": {"type": "string"},
           "priority": {"type": "number"}},
          ("title", "goal"), write=True),
    _spec("ace_op_task_update_status",
          "Move a task to a new status (the store enforces its legal state machine) and optionally set next_action / error_summary.",
          {**_AGENT_PROP, "task_id": _STR, "status": _STR,
           "next_action": _STR, "error_summary": _STR},
          ("task_id", "status"), write=True),
    _spec("ace_op_memory_remember",
          "Store a statement in ACE's long-term cognitive memory. Stored with provenance kind 'external' and the calling agent as source_ref; model/agent statements never pose as evidence.",
          {**_AGENT_PROP, "text": _STR,
           "sensitivity": {"type": "string", "enum": ["internal", "private"]}},
          ("text",), write=True),
    _spec("ace_op_memory_recall",
          "Recall from ACE's long-term cognitive memory (bounded, provenance-tagged).",
          {"query": _STR,
           "limit": {"type": "integer", "minimum": 1, "maximum": 50},
           "include_private": {"type": "boolean"},
           "include_superseded": {"type": "boolean"}}),
    _spec("ace_op_memory_forget",
          "Forget memory records by record_id or by query; content is destroyed and replaced with an auditable tombstone.",
          {**_AGENT_PROP, "record_id": _STR, "query": _STR, "reason": _STR},
          (), write=True),
    _spec("ace_op_memory_audit",
          "Audit ACE's cognitive memory hash chain and counts (chain_ok, active, superseded, tombstones).",
          {}),
    _spec("ace_op_receipt_list",
          "List execution receipts, optionally for one task. Receipts hash inputs/outputs/stdout/stderr.",
          {"task_id": _STR}),
    _spec("ace_op_skill_list",
          "List ACE skills with success/failure/negative-transfer counts.",
          {"active_only": {"type": "boolean"}}),
    _spec("ace_op_skill_get",
          "Get one skill by skill_id.",
          {"skill_id": _STR}, ("skill_id",)),
    _spec("ace_op_skill_create",
          "Create or update a skill record (procedure steps, preconditions, limits, verification template).",
          {**_AGENT_PROP, "name": _STR, "domain": _STR,
           "procedure_steps": {"type": "array", "items": _STR},
           "preconditions": {"type": "array", "items": _STR},
           "boundary_limitations": {"type": "array", "items": _STR},
           "verification_template": {"type": "object"}},
          ("name", "domain", "procedure_steps"), write=True),
    _spec("ace_op_frontier_list",
          "List the capability frontier (status per capability; KNOWN_AND_TESTED requires an evidence_ref in the store).",
          {}),
    _spec("ace_op_gap_list",
          "List capability gaps, optionally filtered by status.",
          {"status": _STR}),
    _spec("ace_op_gap_report",
          "Report a capability gap; identical fingerprints are deduplicated and only distinct reproductions count.",
          {**_AGENT_PROP, "source_task_id": _STR, "error_type": _STR,
           "missing_skill_or_tool": _STR, "description": _STR,
           "reproduction_ref": _STR},
          ("error_type", "missing_skill_or_tool", "description"), write=True),
    _spec("ace_op_work_order_create",
          "Create a delegated work order under a parent task (idempotency-keyed).",
          {**_AGENT_PROP, "parent_task_id": _STR, "objective": _STR,
           "idempotency_key": _STR, "worker_kind": _STR,
           "base_snapshot_hash": _STR, "mission_id": _STR},
          ("parent_task_id", "objective", "idempotency_key"), write=True),
    _spec("ace_op_work_order_list",
          "List work orders, optionally for one parent task.",
          {"parent_task_id": _STR}),
    _spec("ace_op_work_order_submit",
          "Submit a worker result for a work order. Submission does NOT self-verify: verification_status stays UNVERIFIED until ACE verifies it.",
          {**_AGENT_PROP, "work_order_id": _STR,
           "result": {"type": "object"}},
          ("work_order_id", "result"), write=True),
    _spec("ace_op_file_write",
          "Write a UTF-8 text file inside the ACE workspace, guarded by the current file's sha256 (expected_sha256; empty string means the file must not exist yet). Atomic replace; hashes are returned and the write is event-logged.",
          {**_AGENT_PROP, "path": _STR, "content": _STR,
           "expected_sha256": _STR, "task_id": _STR},
          ("path", "content", "expected_sha256"), write=True),
    _spec("ace_op_verify_task",
          "Verify a task from ACE's own records: its receipts (all must pass) and the memory chain state. Returns the components; the verdict never exceeds the evidence.",
          {"task_id": _STR}, ("task_id",)),
)

OP_WRITE_TOOLS = frozenset(
    s["name"] for s in OP_TOOL_SPECS if not s["annotations"]["readOnlyHint"]
)
OP_TOOL_NAMES = frozenset(s["name"] for s in OP_TOOL_SPECS)


class OperationalBridge:
    """The operational core behind the MCP server and the thin CLI."""

    def __init__(self, workspace: str | Path, allow_writes: bool = False):
        if type(allow_writes) is not bool:
            raise TypeError("allow_writes must be bool")
        self.workspace = Path(workspace)
        self.allow_writes = allow_writes
        self.store = OperationalStore(self.workspace)
        self.memory = ConversationalMemoryManager(self.store)

    # -- plumbing ---------------------------------------------------------
    def tools(self) -> list[dict]:
        return list(OP_TOOL_SPECS)

    def _agent(self, args: dict) -> str:
        agent = str(args.get("agent") or "unknown-agent")[:80]
        return agent

    def _log(self, tool: str, args: dict, detail: dict) -> None:
        self.store.emit_event(
            kind="tool_call",
            status="COMPLETED",
            summary_code=tool,
            technical_detail={"agent": self._agent(args), **detail},
        )

    def call(self, name: str, arguments: dict) -> Any:
        if name not in OP_TOOL_NAMES:
            raise ValueError(f"unknown operational tool: {name}")
        if type(arguments) is not dict:
            raise ValueError("tool arguments must be an object")
        if name in OP_WRITE_TOOLS and not self.allow_writes:
            raise PermissionError(
                "ACE write tools are disabled; the operator must enable them "
                "(server: --read-write, CLI: --read-write)")
        handler = getattr(self, f"_do_{name}")
        return handler(arguments)

    # -- status / tasks ---------------------------------------------------
    def _do_ace_op_status(self, args: dict) -> Any:
        tasks = self.store.list_tasks(limit=200)
        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        frontier = self.store.list_frontier()
        return {
            "workspace": str(self.store.workspace),
            "tasks_total": len(tasks),
            "tasks_by_status": by_status,
            "gaps_open": len(self.store.list_gaps(status="OPEN")),
            "skills_active": len(self.store.list_skills(active_only=True)),
            "frontier_total": len(frontier),
            "frontier_known_and_tested": sum(
                1 for f in frontier if f["status"] == "KNOWN_AND_TESTED"),
            "memory": self.memory.get_summary(),
        }

    def _do_ace_op_task_list(self, args: dict) -> Any:
        limit = int(args.get("limit", 50))
        return {"tasks": self.store.list_tasks(limit=limit)}

    def _do_ace_op_task_get(self, args: dict) -> Any:
        task = self.store.get_task(str(args["task_id"]))
        if task is None:
            raise KeyError(f"task not found: {args['task_id']}")
        task = dict(task)
        task["receipts"] = self.store.list_receipts(task["task_id"])
        task["work_orders"] = self.store.list_work_orders(task["task_id"])
        return task

    def _do_ace_op_task_create(self, args: dict) -> Any:
        task = self.store.create_task(
            kind=str(args.get("kind") or "user_task"),
            title_id=str(args["title"]),
            user_request=str(args["goal"]),
            normalized_goal=str(args["goal"]),
            priority=float(args.get("priority", 10.0)),
        )
        self._log("ace_op_task_create", args, {"task_id": task["task_id"]})
        return task

    def _do_ace_op_task_update_status(self, args: dict) -> Any:
        extra = {}
        if args.get("next_action"):
            extra["next_action"] = str(args["next_action"])
        if args.get("error_summary"):
            extra["error_summary"] = str(args["error_summary"])
        task = self.store.update_task(
            str(args["task_id"]), status=str(args["status"]), **extra)
        self._log("ace_op_task_update_status", args,
                  {"task_id": task["task_id"], "status": task["status"]})
        return task

    # -- memory -------------------------------------------------------------
    def _do_ace_op_memory_remember(self, args: dict) -> Any:
        res = self.memory.remember_statement(
            str(args["text"]),
            source_kind="external",
            source_ref=self._agent(args),
            sensitivity=str(args.get("sensitivity") or "internal"),
        )
        self._log("ace_op_memory_remember", args, {"stored": bool(res.get("stored"))})
        return res

    def _do_ace_op_memory_recall(self, args: dict) -> Any:
        return self.memory.recall_memories(
            str(args.get("query", "")),
            limit=int(args.get("limit", 10)),
            include_private=bool(args.get("include_private", False)),
            include_superseded=bool(args.get("include_superseded", False)),
        )

    def _do_ace_op_memory_forget(self, args: dict) -> Any:
        reason = str(args.get("reason") or f"diminta agent {self._agent(args)} lewat tool layer")
        if args.get("record_id"):
            res = self.memory.forget_by_id(str(args["record_id"]), reason=reason)
        elif args.get("query"):
            res = self.memory.forget_by_query(str(args["query"]), reason=reason)
        else:
            raise ValueError("ace_op_memory_forget requires record_id or query")
        self._log("ace_op_memory_forget", args, {"reason": reason})
        return res

    def _do_ace_op_memory_audit(self, args: dict) -> Any:
        return {"audit": self.memory.audit_report(),
                "summary": self.memory.get_summary()}

    # -- receipts / verification -------------------------------------------
    def _do_ace_op_receipt_list(self, args: dict) -> Any:
        task_id = str(args["task_id"]) if args.get("task_id") else None
        return {"receipts": self.store.list_receipts(task_id)}

    def _do_ace_op_verify_task(self, args: dict) -> Any:
        task_id = str(args["task_id"])
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(f"task not found: {task_id}")
        receipts = self.store.list_receipts(task_id)
        passed = [r for r in receipts if r.get("passed")]
        audit = self.memory.audit_report()
        return {
            "task_id": task_id,
            "task_status": task["status"],
            "receipts_total": len(receipts),
            "receipts_passed": len(passed),
            "all_receipts_passed": bool(receipts) and len(passed) == len(receipts),
            "memory_chain_ok": bool(audit["chain_ok"]),
            "verdict": (
                "VERIFIED" if receipts and len(passed) == len(receipts)
                and audit["chain_ok"] else "NOT_VERIFIED"),
            "note": "Verdict is computed only from ACE's own receipts and memory chain; no receipts means NOT_VERIFIED.",
        }

    # -- skills / frontier / gaps -------------------------------------------
    def _do_ace_op_skill_list(self, args: dict) -> Any:
        return {"skills": self.store.list_skills(
            active_only=bool(args.get("active_only", False)))}

    def _do_ace_op_skill_get(self, args: dict) -> Any:
        skill = self.store.get_skill(str(args["skill_id"]))
        if skill is None:
            raise KeyError(f"skill not found: {args['skill_id']}")
        return skill

    def _do_ace_op_skill_create(self, args: dict) -> Any:
        skill = self.store.save_skill(
            name=str(args["name"]),
            domain=str(args["domain"]),
            preconditions=[str(x) for x in args.get("preconditions", [])],
            boundary_limitations=[str(x) for x in args.get("boundary_limitations", [])],
            procedure_steps=[str(x) for x in args["procedure_steps"]],
            verification_template=dict(args.get("verification_template", {})),
            source_task_ids=[],
        )
        self._log("ace_op_skill_create", args, {"skill_id": skill["skill_id"]})
        return skill

    def _do_ace_op_frontier_list(self, args: dict) -> Any:
        return {"frontier": self.store.list_frontier()}

    def _do_ace_op_gap_list(self, args: dict) -> Any:
        status = str(args["status"]) if args.get("status") else None
        return {"gaps": self.store.list_gaps(status=status)}

    def _do_ace_op_gap_report(self, args: dict) -> Any:
        gap, created = self.store.record_gap(
            source_task_id=str(args.get("source_task_id") or ""),
            error_type=str(args["error_type"]),
            missing_skill_or_tool=str(args["missing_skill_or_tool"]),
            description_id=str(args["description"]),
            reproduction_ref=str(args.get("reproduction_ref") or ""),
        )
        self._log("ace_op_gap_report", args,
                  {"gap_id": gap.get("gap_id", ""), "created_new": created})
        return {"gap": gap, "created_new": created}

    # -- work orders ---------------------------------------------------------
    def _do_ace_op_work_order_create(self, args: dict) -> Any:
        wo, created = self.store.create_work_order(
            parent_task_id=str(args["parent_task_id"]),
            mission_id=str(args.get("mission_id") or ""),
            idempotency_key=str(args["idempotency_key"]),
            worker_kind=str(args.get("worker_kind") or "coding_worker"),
            objective=str(args["objective"]),
            base_snapshot_hash=str(args.get("base_snapshot_hash") or ""),
            payload={},
        )
        self._log("ace_op_work_order_create", args,
                  {"work_order_id": wo["work_order_id"], "created_new": created})
        return {"work_order": wo, "created_new": created}

    def _do_ace_op_work_order_list(self, args: dict) -> Any:
        parent = str(args["parent_task_id"]) if args.get("parent_task_id") else None
        return {"work_orders": self.store.list_work_orders(parent)}

    def _do_ace_op_work_order_submit(self, args: dict) -> Any:
        wo = self.store.update_work_order(
            str(args["work_order_id"]),
            status="SUBMITTED",
            claimed_by=self._agent(args),
            result=dict(args["result"]),
            verification_status="UNVERIFIED",
        )
        self._log("ace_op_work_order_submit", args,
                  {"work_order_id": wo["work_order_id"]})
        return wo

    # -- guarded file write (the "Ubah" family) -------------------------------
    def _do_ace_op_file_write(self, args: dict) -> Any:
        rel = str(args["path"])
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts or not rel:
            raise ValueError("path must be a workspace-relative path without '..'")
        dest = (self.store.workspace / rel_path).resolve()
        root = self.store.workspace.resolve()
        if dest != root and root not in dest.parents:
            raise ValueError("path escapes the ACE workspace")
        expected = str(args["expected_sha256"])
        before = ""
        if dest.is_file():
            before = hashlib.sha256(dest.read_bytes()).hexdigest()
        if before != expected:
            raise ValueError(
                f"preimage hash mismatch: expected {expected or '<absent>'}, "
                f"actual {before or '<absent>'} - re-read the file and retry")
        data = str(args["content"]).encode("utf-8")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp-tool-layer")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        after = hashlib.sha256(data).hexdigest()
        self._log("ace_op_file_write", args,
                  {"path": rel, "sha256_before": before, "sha256_after": after})
        return {"path": rel, "sha256_before": before,
                "sha256_after": after, "bytes": len(data)}
