"""Bounded, explicit ACE runtime facade for MCP; no arbitrary code execution.

This module only forwards well-typed requests to the real SQLite ACE Runtime.
The transport decides whether a caller is authenticated; write tools are disabled
unless the operator explicitly enables them.
"""
from __future__ import annotations

import json
from pathlib import Path

from ace_runtime.engine import Runtime

VERSION = "0.1.0"
PROTOCOL = "2025-06-18"
WRITE_TOOLS = frozenset(("ace_submit_task", "ace_run_tasks", "ace_evaluate"))
TOOL_SPECS = (
    {
        "name": "ace_status",
        "description": "Read the current ACE task queue, retained capability count, and runtime state. ACE is limited to labeled a/b strings; this is not evidence of general intelligence.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "ace_submit_task",
        "description": "Queue one bounded labeled binary-string development task. Requires explicit operator write permission; does not execute the task or deploy a learned model.",
        "inputSchema": {"type": "object", "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string", "minLength": 1, "maxLength": 80},
                            "train": {"type": "array", "minItems": 1, "maxItems": 63,
                                      "items": {"type": "array", "minItems": 2, "maxItems": 2}},
                            "validation": {"type": "array", "minItems": 1, "maxItems": 128,
                                           "items": {"type": "array", "minItems": 2, "maxItems": 2}},
                        },
                        "required": ["name", "train", "validation"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "ace_run_tasks",
        "description": "Run at most 1-16 queued ACE local development tasks and persist receipts. Pure bounded computation, no external APIs or deployment. Requires operator write permission.",
        "inputSchema": {"type": "object", "additionalProperties": False,
                        "properties": {"max_tasks": {"type": "integer", "minimum": 1, "maximum": 16}},
                        "required": ["max_tasks"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "ace_get_report",
        "description": "Read one persisted ACE task report, including whether the model was validated or inherited. Requires an actual task ID.",
        "inputSchema": {"type": "object", "additionalProperties": False,
                        "properties": {"task_id": {"type": "string", "minLength": 64, "maxLength": 64}},
                        "required": ["task_id"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "ace_predict",
        "description": "Predict a binary a/b string using only a previously staged, validated task-specific ACE program. Prediction is not guaranteed under semantic drift.",
        "inputSchema": {"type": "object", "additionalProperties": False,
                        "properties": {"task_id": {"type": "string", "minLength": 64, "maxLength": 64},
                                       "word": {"type": "string", "maxLength": 100,
                                                "pattern": "^[ab]*$"}},
                        "required": ["task_id", "word"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "ace_evaluate",
        "description": "Bind a separate terminal dataset exactly once to a completed ACE task. Subsequent differing evaluation data are rejected. Requires operator write permission; no model training.",
        "inputSchema": {"type": "object", "additionalProperties": False,
                        "properties": {"task_id": {"type": "string", "minLength": 64, "maxLength": 64},
                                       "rows": {"type": "array", "minItems": 1, "maxItems": 128,
                                                "items": {"type": "array", "minItems": 2, "maxItems": 2}}},
                        "required": ["task_id", "rows"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
)

CODE_DIAGNOSTIC = {
    "name": "ace_code_diagnostic",
    "description": "Run an opt-in local synthetic sandbox diagnostic; never authorizes promotion.",
    "inputSchema": {"type": "object", "additionalProperties": False,
                    "properties": {"source": {"type": "string", "minLength": 1, "maxLength": 4096}},
                    "required": ["source"]},
    "annotations": {"readOnlyHint": False, "destructiveHint": False},
}


class ToolInputError(ValueError):
    pass


def _object_args(value, required):
    if type(value) is not dict or set(value) != set(required):
        raise ToolInputError("wrong tool arguments")
    return value


def _task_id(value):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ToolInputError("invalid task_id")
    return value


def _binary_word(value):
    if type(value) is not str or len(value) > 100 or set(value) - {"a", "b"}:
        raise ToolInputError("word must be an a/b string of at most 100 characters")
    return value


class ACEBridge:
    def __init__(self, workspace: str | Path, allow_writes: bool = False, enable_code_diagnostic: bool = False):
        if type(allow_writes) is not bool:
            raise TypeError("allow_writes must be bool")
        self.workspace = Path(workspace)
        self.allow_writes = allow_writes
        if type(enable_code_diagnostic) is not bool:
            raise TypeError("enable_code_diagnostic must be bool")
        self.enable_code_diagnostic = enable_code_diagnostic

    def tools(self):
        return list(TOOL_SPECS) + ([CODE_DIAGNOSTIC] if self.enable_code_diagnostic else [])

    def call(self, name, arguments):
        if type(name) is not str or name not in {s["name"] for s in self.tools()}:
            raise ToolInputError("unknown tool")
        if name == "ace_code_diagnostic":
            args = _object_args(arguments, ("source",))
            from .code_diagnostic import evaluate
            return evaluate(args["source"])
        if name in WRITE_TOOLS and not self.allow_writes:
            raise PermissionError("ACE write tools are disabled; administrator must enable them")
        if name == "ace_status":
            _object_args(arguments, ())
            with Runtime(self.workspace) as runtime:
                result = runtime.status()
        elif name == "ace_submit_task":
            args = _object_args(arguments, ("name", "train", "validation"))
            # Runtime validates duplicate labels, disjointness, data types and all budgets.
            with Runtime(self.workspace) as runtime:
                result = {"task_id": runtime.enqueue(args), "queued": True}
        elif name == "ace_run_tasks":
            args = _object_args(arguments, ("max_tasks",))
            n = args["max_tasks"]
            if type(n) is not int or not 1 <= n <= 16:
                raise ToolInputError("max_tasks must be an integer from 1 to 16")
            with Runtime(self.workspace) as runtime:
                outcome = runtime.run(max_tasks=n)
                result = {"outcomes": outcome, "status": runtime.status()}
        elif name == "ace_get_report":
            args = _object_args(arguments, ("task_id",))
            with Runtime(self.workspace) as runtime:
                result = runtime.report(_task_id(args["task_id"]))
        elif name == "ace_predict":
            args = _object_args(arguments, ("task_id", "word"))
            identity, word = _task_id(args["task_id"]), _binary_word(args["word"])
            with Runtime(self.workspace) as runtime:
                result = {"task_id": identity, "word": word,
                          "prediction": runtime.predict(identity, word),
                          "not_open_world_guaranteed": True}
        else:
            args = _object_args(arguments, ("task_id", "rows"))
            identity = _task_id(args["task_id"])
            # Strict terminal row contract, no list-of-strings, bool/int aliases, or >128.
            from ace_capability_evolution.compositional import validate_rows
            validate_rows(args["rows"], 128)
            with Runtime(self.workspace) as runtime:
                result = {"task_id": identity, "evaluation": runtime.evaluate(identity, args["rows"])}
        return result


def json_rpc(request, bridge: ACEBridge):
    """Return MCP JSON-RPC response, or None for notifications."""
    if type(request) is not dict:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    identity = request.get("id")
    if (request.get("jsonrpc") != "2.0" or type(request.get("method")) is not str or
            ("id" in request and (type(identity) not in (str, int) or type(identity) is bool))):
        return {"jsonrpc": "2.0", "id": identity if type(identity) in (str, int) else None,
                "error": {"code": -32600, "message": "Invalid Request"}}
    method = request["method"]
    if "id" not in request:
        # Notifications never invoke runtime tools or require an acknowledgment.
        return None
    try:
        if method == "initialize":
            params = request.get("params", {})
            if type(params) is not dict:
                raise ToolInputError("invalid initialize")
            result = {"protocolVersion": PROTOCOL,
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "ACE Bounded Runtime Bridge", "version": VERSION},
                      "instructions": "Tools operate only on bounded labeled a/b strings. No novel algorithm discovery, open-world safety, or OAIE claim."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            if request.get("params", {}) not in ({}, None):
                raise ToolInputError("tools/list takes no arguments")
            result = {"tools": bridge.tools()}
        elif method == "tools/call":
            params = _object_args(request.get("params"), ("name", "arguments"))
            try:
                value = bridge.call(params["name"], params["arguments"])
            except (ValueError, TypeError, PermissionError, RuntimeError, KeyError) as exc:
                return {"jsonrpc": "2.0", "id": identity,
                        "result": {"content": [{"type": "text",
                                               "text": json.dumps({"status": "ACE_TOOL_ERROR",
                                                                   "error": str(exc)}, sort_keys=True)}],
                                   "isError": True}}
            text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            result = {"content": [{"type": "text", "text": text}], "isError": False}
        else:
            return {"jsonrpc": "2.0", "id": identity,
                    "error": {"code": -32601, "message": "Method not found"}}
    except ToolInputError as exc:
        return {"jsonrpc": "2.0", "id": identity, "error": {"code": -32602, "message": str(exc)}}
    return {"jsonrpc": "2.0", "id": identity, "result": result}
