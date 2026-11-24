"""Thin CLI over the same ACE bridge core (tool layer v1, plan D2).

The CLI and the MCP server (`ace_mcp.server`) call the identical
`ACEBridge` / operational core - there is no duplicated logic. Every
command prints exactly one JSON object to stdout.

Usage:
    python -m ace_mcp.cli --workspace <dir> [--read-write] list
    python -m ace_mcp.cli --workspace <dir> [--read-write] call <tool> '<json-args>'
    python -m ace_mcp.cli --workspace <dir> [--read-write] call <tool> --args-file <path>

Exit code 0 on success, 1 on a tool error (the JSON object carries
`status: ACE_TOOL_ERROR` and the error message).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .bridge import ACEBridge


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--read-write", action="store_true",
                        help="Operator opt-in: enable write tools (same flag as the MCP server)")
    parser.add_argument("--research-only", action="store_true",
                        help="Disable the operational tool layer (ace_op_* tools)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List all available tools with their schemas")
    p_call = sub.add_parser("call", help="Call one tool")
    p_call.add_argument("tool")
    p_call.add_argument("args_json", nargs="?", default=None,
                        help="JSON object of tool arguments")
    p_call.add_argument("--args-file", default=None,
                        help="Read the JSON arguments object from a file instead")
    args = parser.parse_args(argv)

    bridge = ACEBridge(args.workspace, allow_writes=args.read_write,
                       operational=not args.research_only)
    if args.cmd == "list":
        print(json.dumps({"tools": bridge.tools()}, ensure_ascii=False, indent=2))
        return 0

    raw = args.args_json
    if args.args_file:
        raw = Path(args.args_file).read_text(encoding="utf-8")
    try:
        arguments = json.loads(raw) if raw else {}
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be a JSON object")
        result = bridge.call(args.tool, arguments)
    except Exception as exc:  # surfaced as data, mirroring the MCP error shape
        print(json.dumps({"status": "ACE_TOOL_ERROR", "error": str(exc)},
                         ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
