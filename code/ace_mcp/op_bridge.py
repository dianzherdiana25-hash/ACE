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
import importlib
import os
import sys
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


def _jsonable(value: Any) -> Any:
    """Coerce repo-tool results into plain JSON data (Paths, tuples, sets)."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(v) for v in value)
    return value


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

# -- Toolbox batch 1 (owner direction 2026-11-24): ACE's own repo tools --
# (the `tools/` package at the repo root, 205 modules) opened to ACE's
# agents through this same core. Batch 1 wires the read-only audit and
# report functions that ACE's own runtime already uses via leap_wiring,
# so their behaviour in production is proven. Every file argument is a
# workspace-relative path, guarded exactly like ace_op_file_write.
# Later batches extend ACE_TOOLBOX_SPECS; nothing here is a generic
# eval/import escape hatch - each entry names one verified function.
_OBJ = {"type": "object"}
_ARR = {"type": "array", "items": _OBJ}
_STR_ARR = {"type": "array", "items": _STR}

ACE_TOOLBOX_SPECS = (
    _spec("ace_op_tool_mastery_board",
          "Build ACE's cross-domain mastery board (tools.mastery_board) from per-domain metric inputs {domain: {closure|transfer|retention: number}}.",
          {"domains": _OBJ}, ("domains",)),
    _spec("ace_op_tool_metacog_consolidate",
          "Consolidate metacognitive memory (tools.metacog_memory_consolidate) over workspace JSONL inputs: failure/success clusters, negative-transfer alerts, superseded debt.",
          {"paths": _STR_ARR}, ("paths",)),
    _spec("ace_op_tool_occurrence_outliers",
          "Scan the operational store for occurrence outliers - gaps recurring without learning progress (tools.occurrence_outlier_scan, read-only).",
          {"db_path": _STR, "threshold": {"type": "integer"},
           "include_closed": {"type": "boolean"}}),
    _spec("ace_op_tool_candidate_census",
          "Census one candidate JSONL file (tools.candidate_census): readiness, schema and constraint checks, read-only.",
          {"path": _STR}, ("path",)),
    _spec("ace_op_tool_receipt_chain",
          "Verify a director execution receipt chain file (tools.receipt_chain_verify).",
          {"path": _STR}, ("path",)),
    _spec("ace_op_tool_custody_check",
          "Verify a custody manifest's SHA-256 entries against the workspace (tools.custody_manifest_check). Defaults mirror the runtime's own lookup.",
          {"manifest_path": _STR, "root": _STR}),
    _spec("ace_op_tool_prose_audit",
          "Audit prose/narrative text for unrecognized or unsupported claims (tools.director_prose_audit). Pass text directly or a workspace file path.",
          {"text": _STR, "path": _STR, "product_path": _STR}),
    _spec("ace_op_tool_practice_lint",
          "Lint practice tasks (tools.practice_task_lint): prompt leakage, evaluator validity, schema checks.",
          {"tasks": _ARR}, ("tasks",)),
    _spec("ace_op_tool_curriculum_ab",
          "Compare fixed vs generated curricula (tools.curriculum_ab_report) from gap/task rows.",
          {"fixed": _ARR, "generated": _ARR}, ("fixed", "generated")),
    _spec("ace_op_tool_cap_simulator",
          "Replay director receipt events through the AIMD daily-cap simulator (tools.director_cap_simulator). Defaults to the workspace's director receipt files.",
          {"paths": _STR_ARR}),
    _spec("ace_op_tool_gap_patterns",
          "Analyze gap patterns (tools.gap_pattern_report). Defaults to the store's own gaps when none are passed.",
          {"gaps": _ARR, "proposals": _ARR}),
    _spec("ace_op_tool_memory_chain",
          "Verify one memory chain file, or compare two chains for forks (tools.memory_chain_compare).",
          {"left": _STR, "right": _STR}, ("left",)),
)

OP_TOOL_SPECS = OP_TOOL_SPECS + ACE_TOOLBOX_SPECS

# -- Toolbox batch 2: memory hygiene/decay, gap root causes, director --
# helpers, failure task generation, and the candidate factories. The two
# factories WRITE inside the workspace, so they carry the operator
# write opt-in like every other mutating tool; the rest are read-only.
ACE_TOOLBOX2_SPECS = (
    _spec("ace_op_tool_memory_hygiene",
          "Audit a cognitive-memory JSONL log (tools.memory_hygiene_audit): duplicates, orphans, stale entries, chain state. Read-only.",
          {"path": _STR, "refs_path": _STR}),
    _spec("ace_op_tool_memory_decay_plan",
          "Build a memory archive PLAN (tools.memory_decay) - candidates only, nothing is deleted. Defaults to the workspace's memory and recall logs.",
          {"memory_path": _STR, "recall_log_path": _STR,
           "stale_days": {"type": "integer"}}),
    _spec("ace_op_tool_gap_root_causes",
          "Analyze root causes of gaps in the operational store (tools.gap_root_cause_report).",
          {"db_path": _STR}),
    _spec("ace_op_tool_director_challenge",
          "Challenge director proposals against reference facts (tools.director_challenger).",
          {"proposals": _ARR, "facts": _OBJ}, ("proposals", "facts")),
    _spec("ace_op_tool_director_fold",
          "Fold duplicate director proposals (tools.director_fold).",
          {"rows": _ARR}, ("rows",)),
    _spec("ace_op_tool_director_route",
          "Route director proposals to practice/umbrella/research queues (tools.director_queue_router). gap_error_types defaults to the store's own gap errors.",
          {"proposals": _ARR, "gap_error_types": _OBJ}, ("proposals",)),
    _spec("ace_op_tool_director_grounding",
          "Check quantitative claims in director proposals against facts (tools.director_grounding_check). facts defaults to counts loaded from the store.",
          {"proposals": _ARR, "facts": _OBJ}, ("proposals",)),
    _spec("ace_op_tool_failure_taskgen",
          "Generate and validate learning tasks from failure fingerprints (tools.failure_taskgen). Pure generation; nothing is stored.",
          {"fingerprints": _ARR}, ("fingerprints",)),
    _spec("ace_op_tool_candidate_factory_v2",
          "Generate a candidate v2 bundle into a workspace directory (tools.candidate_factory_v2), like the runtime's own leap step.",
          {**_AGENT_PROP, "output_dir": _STR,
           "id_lang_count": {"type": "integer"},
           "ml_lang_count": {"type": "integer"},
           "code_count": {"type": "integer"},
           "seed": {"type": "integer"}},
          (), write=True),
    _spec("ace_op_tool_discriminating_candidates",
          "Generate discriminating candidates (tools.discriminating_candidate_factory); when write_to is given, also writes the intake JSONL and its meta file inside the workspace.",
          {**_AGENT_PROP, "lang_count": {"type": "integer"},
           "code_count": {"type": "integer"},
           "seed": {"type": "integer"}, "write_to": _STR},
          (), write=True),
)

OP_TOOL_SPECS = OP_TOOL_SPECS + ACE_TOOLBOX2_SPECS

# -- Toolbox batch 3: organ/observation family. All read-only. Two --
# repo tools were deliberately NOT wired: organ_smoke (needs an
# injected transport callable) and daily_digest + verdict gates over
# the repo itself (outside the workspace sandbox; a repo-scoped read
# adapter is a separate owner decision).
ACE_TOOLBOX3_SPECS = (
    _spec("ace_op_tool_organ_scoreboard",
          "Aggregate per-organ quality metrics and weekly trends from receipts and grounding rows (tools.organ_quality_board).",
          {"receipts": _ARR, "grounding_rows": _ARR},
          ("receipts", "grounding_rows")),
    _spec("ace_op_tool_recall_delivery",
          "Audit held-out tasks against a memory store snapshot {records: [...]} for recall delivery (tools.recall_delivery_probe, default fixture recall).",
          {"tasks": _ARR, "store": _OBJ}, ("tasks", "store")),
    _spec("ace_op_tool_recall_precision",
          "Evaluate recall precision/recall/F1 over the workspace cognitive memory (tools.recall_precision_probe with its own retriever).",
          {"queries": _ARR, "memory_path": _STR}, ("queries",)),
    _spec("ace_op_tool_saturation_scan",
          "Scan result files for score saturation per task group (tools.saturation_scan).",
          {"paths": _STR_ARR}, ("paths",)),
    _spec("ace_op_tool_idle_report",
          "Compute daily idle minutes, cycles, and per-role budget burn from engine log records (tools.engine_idle_report).",
          {"log_records": _ARR, "snapshot_records": _ARR}, ("log_records",)),
    _spec("ace_op_tool_verdict_board",
          "Assemble the G1-G5 verdict board from gate JSON files inside the workspace (tools.verdict_board).",
          {"gate_paths": _OBJ}, ("gate_paths",)),
    _spec("ace_op_tool_transfer_probe",
          "Run the transfer probe over a suite file with the module's own structural toy solver, exactly as the runtime's leap step does (tools.transfer_probe).",
          {"suite_path": _STR, "seed": {"type": "integer"}}, ("suite_path",)),
    _spec("ace_op_tool_incident_summary",
          "Verify and summarize the incident book over an optional date period (tools.incident_book). Defaults to the workspace incidents file.",
          {"book_path": _STR, "start_date": _STR, "end_date": _STR}),
    _spec("ace_op_tool_anchor_audit",
          "Audit proposal rows against a verified-refs file (tools.memory_anchor_audit).",
          {"rows": _ARR, "refs_path": _STR}, ("rows", "refs_path")),
)

OP_TOOL_SPECS = OP_TOOL_SPECS + ACE_TOOLBOX3_SPECS

# -- Toolbox batch 4: agenda/curiosity/report family. All read-only.
# repo_status_dashboard_v3 stays unwired (repo-root scoped, same
# open question as daily_digest).
ACE_TOOLBOX4_SPECS = (
    _spec("ace_op_tool_curiosity_questions",
          "Generate ranked open curiosity questions from a world model and hypothesis book (tools.curiosity_questions).",
          {"world_model": _OBJ, "hypothesis_book": _OBJ,
           "asked_questions": _ARR}, ("world_model",)),
    _spec("ace_op_tool_capability_report",
          "Build the capability report structure from a gate board and store stats, marking unknowns honestly (tools.capability_report).",
          {"gate_board": _OBJ, "store_stats": _OBJ},
          ("gate_board", "store_stats")),
    _spec("ace_op_tool_assessment_verify",
          "Verify the hash chain of self-assessment versions (tools.self_assessment).",
          {"versions": _ARR}, ("versions",)),
    _spec("ace_op_tool_corpus_novelty",
          "Score candidate works for novelty against a corpus (tools.corpus_novelty).",
          {"corpus": _ARR, "candidates": _ARR}, ("corpus", "candidates")),
    _spec("ace_op_tool_evo_verdicts",
          "Tabulate EVO verdicts from consolidation/result files inside the workspace (tools.evo_results).",
          {"paths": _STR_ARR}, ("paths",)),
    _spec("ace_op_tool_periodic_report",
          "Build the periodic self-report from the workspace's self-model sources, read-only (tools.periodic_self_report).",
          {}),
    _spec("ace_op_tool_agenda_prioritize",
          "Prioritize agenda candidate items deterministically (tools.agenda_candidates).",
          {"items": _ARR}, ("items",)),
    _spec("ace_op_tool_failure_scan",
          "Scan failure documents (name -> text) for agenda-worthy failure patterns (tools.agenda_candidates).",
          {"documents": _OBJ}, ("documents",)),
)

OP_TOOL_SPECS = OP_TOOL_SPECS + ACE_TOOLBOX4_SPECS

# -- Toolbox batch 5: audit/agreement family. All read-only.
# evo_range_audit and director_screen stay unwired (repo-root /
# GitSnapshot-object inputs, not plain agent data).
ACE_TOOLBOX5_SPECS = (
    _spec("ace_op_tool_execution_invariants",
          "Audit receipts + execution logs against ACE's named execution invariants (tools.execution_invariants).",
          {"receipts": _ARR, "executions": _ARR,
           "daily_cap": {"type": "integer"}, "verified_refs": _STR_ARR},
          ("receipts", "executions")),
    _spec("ace_op_tool_introspect_recall",
          "Query the workspace memory introspectively (tools.introspect_recall).",
          {"query": _STR, "top_k": {"type": "integer"}}, ("query",)),
    _spec("ace_op_tool_bridge_self_check",
          "Self-check the brain bridge + engine status file (tools.bridge_self_check). Defaults to this workspace's bridge URL and engine_status.json.",
          {"bridge_url": _STR, "status_path": _STR}),
    _spec("ace_op_tool_story_consistency",
          "Check a structured chapter draft against the story state snapshot (tools.story_consistency_gate).",
          {"story_state": _OBJ, "chapter_draft": _OBJ},
          ("story_state", "chapter_draft")),
    _spec("ace_op_tool_fingerprint_diff",
          "Diff two behavior fingerprint snapshots per prompt category (tools.behavior_fingerprint).",
          {"baseline": _OBJ, "candidate": _OBJ}, ("baseline", "candidate")),
    _spec("ace_op_tool_organ_registry_validate",
          "Validate an organ-registry configuration object (tools.organ_registry_validate).",
          {"data": _OBJ}, ("data",)),
    _spec("ace_op_tool_recall_ablation",
          "Run the recall ablation over this workspace's operational store with the fixture recall (tools.recall_ablation).",
          {"tasks": _ARR, "seed": {"type": "integer"}}, ("tasks",)),
    _spec("ace_op_tool_cross_organ_agreement",
          "Evaluate cross-organ agreement (Cohen's kappa, abstention, consensus) from fixture records (tools.cross_organ_agreement).",
          {"records": _ARR}, ("records",)),
)

OP_TOOL_SPECS = OP_TOOL_SPECS + ACE_TOOLBOX5_SPECS

# -- Toolbox batch 6: simulation/design family. All read-only.
# program_glossary and handover_decision_extractor stay unwired
# (repo-root scoped, same open repo-adapter question).
ACE_TOOLBOX6_SPECS = (
    _spec("ace_op_tool_chapter_rubric",
          "Score a story chapter pack on the deterministic reader rubric (tools.arc_rubric).",
          {"pack": _OBJ}, ("pack",)),
    _spec("ace_op_tool_experiment_design",
          "Design the smallest falsifying experiment for each hypothesis (tools.experiment_designer).",
          {"hypotheses": _ARR}, ("hypotheses",)),
    _spec("ace_op_tool_cycle_plan_sim",
          "Simulate cycle step ordering/deferral against a world model (tools.cycle_planner_sim).",
          {"world_model": _OBJ, "steps": _ARR}, ("world_model", "steps")),
    _spec("ace_op_tool_failover_sim",
          "Simulate primary/fallback/wait failover decisions against budget state (tools.quota_failover_sim).",
          {"budget_state": _OBJ, "steps": _ARR}, ("budget_state", "steps")),
    _spec("ace_op_tool_specialization_delta",
          "Compare baseline vs candidate reports for per-domain specialization deltas (tools.specialization_delta).",
          {"baseline": _OBJ, "candidate": _OBJ}, ("baseline", "candidate")),
    _spec("ace_op_tool_writeback_diagnose",
          "Diagnose memory-writeback health over this workspace (tools.writeback_diagnose).",
          {}),
    _spec("ace_op_tool_dilemma_validate",
          "Validate one constitution dilemma item against the pack schema (tools.constitution_dilemma).",
          {"item": _OBJ}, ("item",)),
)

OP_TOOL_SPECS = OP_TOOL_SPECS + ACE_TOOLBOX6_SPECS

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

    # -- toolbox batch 1: ACE's own repo tools, opened to its agents -------
    def _ws_path(self, rel: str) -> Path:
        rel_path = Path(str(rel))
        if rel_path.is_absolute() or ".." in rel_path.parts or not str(rel):
            raise ValueError("path must be a workspace-relative path without '..'")
        dest = (self.store.workspace / rel_path).resolve()
        root = self.store.workspace.resolve()
        if dest != root and root not in dest.parents:
            raise ValueError("path escapes the ACE workspace")
        return dest

    def _repo_tool(self, module_name: str, func_name: str):
        repo_root = Path(__file__).resolve().parents[2]
        if (repo_root / "tools").is_dir() and str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        try:
            module = importlib.import_module(f"tools.{module_name}")
            return getattr(module, func_name)
        except Exception as exc:
            raise ValueError(f"tools.{module_name}.{func_name} unavailable: {exc}") from exc

    def _run_tool(self, module_name: str, func_name: str, *a, **kw) -> Any:
        fn = self._repo_tool(module_name, func_name)
        try:
            return _jsonable(fn(*a, **kw))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"tools.{module_name}.{func_name}: {exc}") from exc

    def _store_db(self, args: dict) -> Path:
        if args.get("db_path"):
            return self._ws_path(str(args["db_path"]))
        db = Path(getattr(self.store, "db_path", None)
                  or (self.store.workspace / "ace_operational.sqlite3"))
        if not db.is_file():
            raise ValueError(f"store database not found: {db.name}")
        return db

    def _do_ace_op_tool_mastery_board(self, args: dict) -> Any:
        domains = args["domains"]
        if not isinstance(domains, dict):
            raise ValueError("domains must be an object")
        return self._run_tool("mastery_board", "build_mastery_board", domains)

    def _do_ace_op_tool_metacog_consolidate(self, args: dict) -> Any:
        inputs = [self._ws_path(p) for p in args["paths"]]
        return self._run_tool(
            "metacog_memory_consolidate", "consolidate_metacognitive_memory",
            inputs, root=self.store.workspace)

    def _do_ace_op_tool_occurrence_outliers(self, args: dict) -> Any:
        if args.get("db_path"):
            db = self._ws_path(str(args["db_path"]))
        else:
            db = Path(getattr(self.store, "db_path", None)
                      or (self.store.workspace / "ace_operational.sqlite3"))
        if not db.is_file():
            raise ValueError(f"store database not found: {db.name}")
        kw: dict[str, Any] = {}
        if args.get("threshold") is not None:
            kw["threshold"] = int(args["threshold"])
        if args.get("include_closed") is not None:
            kw["include_closed"] = bool(args["include_closed"])
        return self._run_tool("occurrence_outlier_scan",
                              "scan_occurrence_outliers", db, **kw)

    def _do_ace_op_tool_candidate_census(self, args: dict) -> Any:
        return self._run_tool("candidate_census", "census_file",
                              self._ws_path(str(args["path"])))

    def _do_ace_op_tool_receipt_chain(self, args: dict) -> Any:
        return self._run_tool("receipt_chain_verify", "verify_receipts_file",
                              self._ws_path(str(args["path"])))

    def _do_ace_op_tool_custody_check(self, args: dict) -> Any:
        ws = self.store.workspace
        if args.get("manifest_path"):
            manifest = self._ws_path(str(args["manifest_path"]))
        elif (ws / "custody_manifest.json").is_file():
            manifest = ws / "custody_manifest.json"
        else:
            manifest = ws / "custody" / "custody_manifest.json"
        if not manifest.is_file():
            raise ValueError("no custody_manifest.json in the workspace")
        if args.get("root"):
            root = self._ws_path(str(args["root"]))
        else:
            root = (ws / "custody") if (ws / "custody").is_dir() else ws
        return self._run_tool("custody_manifest_check",
                              "verify_custody_manifest", manifest, root)

    def _do_ace_op_tool_prose_audit(self, args: dict) -> Any:
        if args.get("text"):
            text = str(args["text"])
            product = str(args.get("product_path") or "input.md")
        elif args.get("path"):
            path = self._ws_path(str(args["path"]))
            text = path.read_text(encoding="utf-8", errors="ignore")
            product = str(args.get("product_path") or path.name)
        else:
            raise ValueError("pass either text or a workspace file path")
        return self._run_tool("director_prose_audit", "audit_historical_prose",
                              text, product_path=product)

    def _do_ace_op_tool_practice_lint(self, args: dict) -> Any:
        return self._run_tool("practice_task_lint", "lint_practice_tasks",
                              list(args["tasks"]))

    def _do_ace_op_tool_curriculum_ab(self, args: dict) -> Any:
        return self._run_tool("curriculum_ab_report", "compare_curricula",
                              list(args["fixed"]), list(args["generated"]))

    def _do_ace_op_tool_cap_simulator(self, args: dict) -> Any:
        ws = self.store.workspace
        rels = list(args.get("paths") or
                    ["director_exec_receipts.jsonl",
                     "director_exec_a2_receipts.jsonl"])
        load = self._repo_tool("director_cap_simulator", "load_receipt_events")
        events: list = []
        malformed: list = []
        for rel in rels:
            path = self._ws_path(str(rel))
            if path.is_file():
                ev, bad = load(path)
                events.extend(ev)
                malformed.extend(bad)
        if not events and not malformed:
            raise ValueError("no director receipt files found in the workspace")
        sim = self._run_tool("director_cap_simulator", "simulate_daily_caps",
                             events)
        return {"simulation": sim, "events": len(events),
                "malformed_lines": len(malformed)}

    def _do_ace_op_tool_gap_patterns(self, args: dict) -> Any:
        gaps = list(args["gaps"]) if args.get("gaps") else self.store.list_gaps()
        proposals = list(args.get("proposals") or [])
        return self._run_tool("gap_pattern_report", "analyze_gap_patterns",
                              gaps, proposals)

    def _do_ace_op_tool_memory_chain(self, args: dict) -> Any:
        left = self._ws_path(str(args["left"]))
        if args.get("right"):
            return self._run_tool("memory_chain_compare",
                                  "compare_memory_chains",
                                  left, self._ws_path(str(args["right"])))
        entries, findings = self._run_tool("memory_chain_compare",
                                           "load_and_verify_chain", left)
        return {"entries": len(entries), "finding_count": len(findings),
                "findings": list(findings)[:20]}

    # -- toolbox batch 2 ---------------------------------------------------
    def _do_ace_op_tool_memory_hygiene(self, args: dict) -> Any:
        ws = self.store.workspace
        path = (self._ws_path(str(args["path"])) if args.get("path")
                else ws / "cognitive_memory" / "memory.jsonl")
        if not path.is_file():
            raise ValueError(f"memory log not found: {path.name}")
        kw: dict[str, Any] = {}
        if args.get("refs_path"):
            load_refs = self._repo_tool("memory_hygiene_audit", "load_refs_file")
            kw["known_refs"] = load_refs(self._ws_path(str(args["refs_path"])))
        return self._run_tool("memory_hygiene_audit", "audit_memory_log",
                              path, **kw)

    def _do_ace_op_tool_memory_decay_plan(self, args: dict) -> Any:
        from datetime import datetime, timezone
        ws = self.store.workspace
        mem = (self._ws_path(str(args["memory_path"])) if args.get("memory_path")
               else ws / "cognitive_memory" / "memory.jsonl")
        recall = (self._ws_path(str(args["recall_log_path"]))
                  if args.get("recall_log_path") else ws / "recall_probe.jsonl")
        kw: dict[str, Any] = {"as_of": datetime.now(timezone.utc)}
        if args.get("stale_days") is not None:
            kw["stale_days"] = int(args["stale_days"])
        return self._run_tool("memory_decay", "build_archive_plan",
                              mem, recall, **kw)

    def _do_ace_op_tool_gap_root_causes(self, args: dict) -> Any:
        return self._run_tool("gap_root_cause_report",
                              "analyze_gap_root_causes", self._store_db(args))

    def _do_ace_op_tool_director_challenge(self, args: dict) -> Any:
        return self._run_tool("director_challenger", "review_proposals",
                              list(args["proposals"]), dict(args["facts"]))

    def _do_ace_op_tool_director_fold(self, args: dict) -> Any:
        return self._run_tool("director_fold", "fold_proposals",
                              list(args["rows"]))

    def _do_ace_op_tool_director_route(self, args: dict) -> Any:
        if args.get("gap_error_types") is not None:
            gap_errors = dict(args["gap_error_types"])
        else:
            load = self._repo_tool("director_queue_router",
                                   "load_gap_errors_from_sqlite")
            gap_errors = load(self._store_db(args))
        return self._run_tool("director_queue_router", "route_proposals",
                              list(args["proposals"]), gap_errors)

    def _do_ace_op_tool_director_grounding(self, args: dict) -> Any:
        if args.get("facts") is not None:
            facts = dict(args["facts"])
        else:
            load = self._repo_tool("director_grounding_check",
                                   "load_facts_from_sqlite")
            facts = load(self._store_db(args))
        return self._run_tool("director_grounding_check",
                              "check_proposal_grounding",
                              list(args["proposals"]), facts)

    def _do_ace_op_tool_failure_taskgen(self, args: dict) -> Any:
        return self._run_tool("failure_taskgen", "generate_and_validate_tasks",
                              list(args["fingerprints"]))

    def _do_ace_op_tool_candidate_factory_v2(self, args: dict) -> Any:
        out_dir = self._ws_path(str(args.get("output_dir") or "candidates_v2"))
        kw: dict[str, Any] = {}
        for key in ("id_lang_count", "ml_lang_count", "code_count", "seed"):
            if args.get(key) is not None:
                kw[key] = int(args[key])
        result = self._run_tool("candidate_factory_v2",
                                "generate_candidate_v2_bundle", out_dir, **kw)
        self._log("ace_op_tool_candidate_factory_v2", args,
                  {"output_dir": str(args.get("output_dir") or "candidates_v2")})
        return result

    def _do_ace_op_tool_discriminating_candidates(self, args: dict) -> Any:
        kw: dict[str, Any] = {}
        for key in ("lang_count", "code_count", "seed"):
            if args.get(key) is not None:
                kw[key] = int(args[key])
        result = self._run_tool("discriminating_candidate_factory",
                                "generate_discriminating_candidates", **kw)
        summary = {"total_episodes": result.get("total_episodes"),
                   "rejected_count": result.get("rejected_count"),
                   "written": False}
        if args.get("write_to"):
            intake = self._ws_path(str(args["write_to"]))
            write = self._repo_tool("discriminating_candidate_factory",
                                    "write_new_candidate_file")
            write(intake, result,
                  meta_path=intake.with_suffix(".meta.json"))
            summary["written"] = True
            summary["intake_path"] = str(args["write_to"])
            if result.get("jsonl_sha256"):
                summary["jsonl_sha256"] = result["jsonl_sha256"]
        self._log("ace_op_tool_discriminating_candidates", args, summary)
        return summary

    # -- toolbox batch 3 ---------------------------------------------------
    def _do_ace_op_tool_organ_scoreboard(self, args: dict) -> Any:
        return self._run_tool("organ_quality_board", "build_organ_scoreboard",
                              list(args["receipts"]),
                              list(args["grounding_rows"]))

    def _do_ace_op_tool_recall_delivery(self, args: dict) -> Any:
        return self._run_tool("recall_delivery_probe", "probe_recall_delivery",
                              list(args["tasks"]), dict(args["store"]))

    def _do_ace_op_tool_recall_precision(self, args: dict) -> Any:
        ws = self.store.workspace
        mem = (self._ws_path(str(args["memory_path"])) if args.get("memory_path")
               else ws / "cognitive_memory" / "memory.jsonl")
        make = self._repo_tool("recall_precision_probe",
                               "make_cognitive_memory_retriever")
        try:
            retriever = make(mem)
        except Exception as exc:
            raise ValueError(f"tools.recall_precision_probe retriever: {exc}") from exc
        return self._run_tool("recall_precision_probe",
                              "evaluate_recall_precision",
                              list(args["queries"]), retriever)

    def _do_ace_op_tool_saturation_scan(self, args: dict) -> Any:
        paths = [self._ws_path(p) for p in args["paths"]]
        return self._run_tool("saturation_scan", "scan_saturation", paths)

    def _do_ace_op_tool_idle_report(self, args: dict) -> Any:
        return self._run_tool("engine_idle_report", "build_idle_report",
                              list(args["log_records"]),
                              list(args.get("snapshot_records") or []))

    def _do_ace_op_tool_verdict_board(self, args: dict) -> Any:
        gates = {str(k): self._ws_path(str(v))
                 for k, v in dict(args["gate_paths"]).items()}
        return self._run_tool("verdict_board", "assemble_verdict_board", gates)

    def _do_ace_op_tool_transfer_probe(self, args: dict) -> Any:
        load = self._repo_tool("transfer_probe", "load_transfer_suite")
        solver = self._repo_tool("transfer_probe", "structural_toy_solver")
        suite = load(self._ws_path(str(args["suite_path"])))
        kw: dict[str, Any] = {}
        if args.get("seed") is not None:
            kw["seed"] = int(args["seed"])
        return self._run_tool("transfer_probe", "run_transfer_probe",
                              suite, solver, **kw)

    def _do_ace_op_tool_incident_summary(self, args: dict) -> Any:
        ws = self.store.workspace
        book = (self._ws_path(str(args["book_path"])) if args.get("book_path")
                else ws / "incidents.jsonl")
        if not book.is_file():
            raise ValueError(f"incident book not found: {book.name}")
        kw: dict[str, Any] = {}
        if args.get("start_date"):
            kw["start_date"] = str(args["start_date"])
        if args.get("end_date"):
            kw["end_date"] = str(args["end_date"])
        return self._run_tool("incident_book", "summarize_period", book, **kw)

    def _do_ace_op_tool_anchor_audit(self, args: dict) -> Any:
        load = self._repo_tool("memory_anchor_audit", "load_verified_store")
        store = load(self._ws_path(str(args["refs_path"])))
        return self._run_tool("memory_anchor_audit", "audit_proposals",
                              list(args["rows"]), store)

    # -- toolbox batch 4 ---------------------------------------------------
    def _do_ace_op_tool_curiosity_questions(self, args: dict) -> Any:
        kw: dict[str, Any] = {}
        if args.get("asked_questions"):
            kw["asked_questions"] = list(args["asked_questions"])
        return self._run_tool("curiosity_questions",
                              "generate_curiosity_questions",
                              dict(args["world_model"]),
                              dict(args["hypothesis_book"])
                              if args.get("hypothesis_book") else None, **kw)

    def _do_ace_op_tool_capability_report(self, args: dict) -> Any:
        return self._run_tool("capability_report", "build_capability_report",
                              dict(args["gate_board"]),
                              dict(args["store_stats"]))

    def _do_ace_op_tool_assessment_verify(self, args: dict) -> Any:
        return self._run_tool("self_assessment", "verify_assessment_chain",
                              list(args["versions"]))

    def _do_ace_op_tool_corpus_novelty(self, args: dict) -> Any:
        return self._run_tool("corpus_novelty", "score_corpus_novelty",
                              list(args["corpus"]), list(args["candidates"]))

    def _do_ace_op_tool_evo_verdicts(self, args: dict) -> Any:
        paths = [self._ws_path(p) for p in args["paths"]]
        return self._run_tool("evo_results", "tabulate_verdicts", paths)

    def _do_ace_op_tool_periodic_report(self, args: dict) -> Any:
        return self._run_tool("periodic_self_report",
                              "build_periodic_self_report",
                              self.store.workspace)

    def _do_ace_op_tool_agenda_prioritize(self, args: dict) -> Any:
        return self._run_tool("agenda_candidates", "prioritize",
                              list(args["items"]))

    def _do_ace_op_tool_failure_scan(self, args: dict) -> Any:
        return self._run_tool("agenda_candidates", "scan_failure_documents",
                              dict(args["documents"]))

    # -- toolbox batch 5 ---------------------------------------------------
    def _do_ace_op_tool_execution_invariants(self, args: dict) -> Any:
        kw: dict[str, Any] = {}
        if args.get("daily_cap") is not None:
            kw["daily_cap"] = int(args["daily_cap"])
        if args.get("verified_refs"):
            kw["verified_refs"] = list(args["verified_refs"])
        return self._run_tool("execution_invariants",
                              "check_execution_invariants",
                              list(args["receipts"]),
                              list(args["executions"]), **kw)

    def _do_ace_op_tool_introspect_recall(self, args: dict) -> Any:
        kw: dict[str, Any] = {"root": self.store.workspace}
        if args.get("top_k") is not None:
            kw["top_k"] = int(args["top_k"])
        return self._run_tool("introspect_recall", "query_introspection",
                              str(args["query"]), **kw)

    def _do_ace_op_tool_bridge_self_check(self, args: dict) -> Any:
        url = (str(args["bridge_url"]) if args.get("bridge_url")
               else os.environ.get("ACE_BRAIN_BRIDGE_URL",
                                   "http://127.0.0.1:18931"))
        status = (self._ws_path(str(args["status_path"]))
                  if args.get("status_path")
                  else self.store.workspace / "engine_status.json")
        return self._run_tool("bridge_self_check", "self_check", url, status)

    def _do_ace_op_tool_story_consistency(self, args: dict) -> Any:
        return self._run_tool("story_consistency_gate",
                              "check_chapter_consistency",
                              dict(args["story_state"]),
                              dict(args["chapter_draft"]))

    def _do_ace_op_tool_fingerprint_diff(self, args: dict) -> Any:
        return self._run_tool("behavior_fingerprint",
                              "diff_fingerprint_snapshots",
                              dict(args["baseline"]), dict(args["candidate"]))

    def _do_ace_op_tool_organ_registry_validate(self, args: dict) -> Any:
        return self._run_tool("organ_registry_validate",
                              "validate_config_data", dict(args["data"]))

    def _do_ace_op_tool_recall_ablation(self, args: dict) -> Any:
        load = self._repo_tool("recall_ablation",
                               "load_sqlite_ablation_store")
        tasks = list(args["tasks"])
        store = load(self._store_db(), tasks)
        kw: dict[str, Any] = {}
        if args.get("seed") is not None:
            kw["seed"] = int(args["seed"])
        return self._run_tool("recall_ablation", "run_ablation",
                              store, tasks, **kw)

    def _do_ace_op_tool_cross_organ_agreement(self, args: dict) -> Any:
        parse = self._repo_tool("cross_organ_agreement",
                                "parse_fixture_records")
        matrix, anomalies = parse(list(args["records"]))
        return self._run_tool("cross_organ_agreement",
                              "evaluate_cross_organ_agreement",
                              matrix, anomalies=anomalies)

    # -- toolbox batch 6 ---------------------------------------------------
    def _do_ace_op_tool_chapter_rubric(self, args: dict) -> Any:
        return self._run_tool("arc_rubric", "score_chapter_pack",
                              dict(args["pack"]))

    def _do_ace_op_tool_experiment_design(self, args: dict) -> Any:
        return self._run_tool("experiment_designer", "design_batch",
                              list(args["hypotheses"]))

    def _do_ace_op_tool_cycle_plan_sim(self, args: dict) -> Any:
        return self._run_tool("cycle_planner_sim", "plan_cycle_steps",
                              dict(args["world_model"]), list(args["steps"]))

    def _do_ace_op_tool_failover_sim(self, args: dict) -> Any:
        return self._run_tool("quota_failover_sim", "simulate_failover",
                              dict(args["budget_state"]), list(args["steps"]))

    def _do_ace_op_tool_specialization_delta(self, args: dict) -> Any:
        return self._run_tool("specialization_delta", "compare_reports",
                              dict(args["baseline"]), dict(args["candidate"]))

    def _do_ace_op_tool_writeback_diagnose(self, args: dict) -> Any:
        return self._run_tool("writeback_diagnose", "diagnose",
                              self.store.workspace)

    def _do_ace_op_tool_dilemma_validate(self, args: dict) -> Any:
        return self._run_tool("constitution_dilemma",
                              "validate_dilemma_item", dict(args["item"]))
