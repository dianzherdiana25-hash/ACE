"""Thin CLI over ACE Orchestrator v3 (`ACEBridge` + multi-agent transports).

The CLI and the MCP server (`ace_mcp.server`) call the identical `ACEBridge` /
`OperationalStore` core. Every command prints exactly one JSON object to stdout.

Existing core usage:
    python -m ace_mcp.cli --workspace <dir> [--read-write] [--tool-profile core|full] list
    python -m ace_mcp.cli --workspace <dir> [--read-write] call <tool> '<json-args>'
    python -m ace_mcp.cli --workspace <dir> [--read-write] call <tool> --args-file <path>

Orchestrator v3 subcommands:
    goal create|list|status|tick
    agent register|list|orient|discover-cli|run-cli
    dispatch export|ingest
    relay export|ingest
    vault status|set-facebook|browser-login
    setup [--vendor all|antigravity|gemini|claude|codex|chatgpt|muse.ai]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .bridge import ACEBridge
from .relay import build_relay_prompt, ingest_relay_reply


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False))


def _vendor_configs(workspace: Path, repo_root: Path) -> dict[str, dict]:
    ws_str = str(workspace.resolve())
    code_dir = str((repo_root / "code").resolve())
    mcp_block = {
        "command": sys.executable,
        "args": [
            "-m", "ace_mcp.server",
            "--workspace", ws_str,
            "--transport", "stdio",
            "--read-write",
            "--tool-profile", "full",
        ],
        "env": {"PYTHONPATH": code_dir},
    }
    return {
        "antigravity": {
            "transport": "mcp_stdio / git_handover",
            "mcpServers": {"ace": mcp_block},
            "cloud_vm_dispatch": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} --read-write dispatch export <work_order_id>",
        },
        "gemini": {
            "transport": "mcp_stdio / local_cli / web_relay",
            "mcpServers": {"ace": mcp_block},
            "cli_adapter": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} --read-write agent run-cli --cli gemini --work-order-id <wo_id>",
            "web_relay": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} relay export --vendor gemini --objective \"<tugas>\"",
        },
        "claude": {
            "transport": "mcp_stdio / local_cli / web_relay",
            "mcpServers": {"ace": mcp_block},
            "cli_adapter": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} --read-write agent run-cli --cli claude --work-order-id <wo_id>",
            "web_relay": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} relay export --vendor claude --objective \"<tugas>\"",
        },
        "codex": {
            "transport": "mcp_stdio / local_cli / git_handover",
            "mcpServers": {"ace": mcp_block},
            "cli_adapter": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} --read-write agent run-cli --cli codex --work-order-id <wo_id>",
        },
        "chatgpt": {
            "transport": "web_relay (Zero-API Copy-Paste Loop)",
            "export_cmd": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} relay export --vendor chatgpt --work-order-id <wo_id>",
            "ingest_cmd": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} --read-write relay ingest --vendor chatgpt --reply-file reply.txt",
        },
        "muse.ai": {
            "transport": "web_relay (Creative & Reels Builder Loop)",
            "export_cmd": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} relay export --vendor muse.ai --work-order-id <wo_id>",
            "ingest_cmd": f"PYTHONPATH={code_dir} {sys.executable} -m ace_mcp.cli --workspace {ws_str} --read-write relay ingest --vendor muse.ai --reply-file reply.txt",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--read-write", action="store_true",
                        help="Operator opt-in: enable write tools (same flag as the MCP server)")
    parser.add_argument("--research-only", action="store_true",
                        help="Disable the operational tool layer (ace_op_* tools)")
    parser.add_argument("--tool-profile", choices=("full", "core"), default="full",
                        help="Tool schema profile (`full` or `core`)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all available tools with their schemas")

    p_call = sub.add_parser("call", help="Call one tool")
    p_call.add_argument("tool")
    p_call.add_argument("args_json", nargs="?", default=None,
                        help="JSON object of tool arguments")
    p_call.add_argument("--args-file", default=None,
                        help="Read the JSON arguments object from a file instead")

    # `goal` subcommands
    p_goal = sub.add_parser("goal", help="Manage autonomous Goal DAGs")
    g_sub = p_goal.add_subparsers(dest="goal_cmd", required=True)
    p_gc = g_sub.add_parser("create")
    p_gc.add_argument("--title", required=True)
    p_gc.add_argument("--request", required=True)
    p_gc.add_argument("--domain", default="general")
    p_gc.add_argument("--publish-mode", choices=("auto", "draft_first"), default="auto")
    p_gc.add_argument("--min-score-bp", type=int, default=8500)
    p_gl = g_sub.add_parser("list")
    p_gl.add_argument("--status", default=None)
    p_gs = g_sub.add_parser("status")
    p_gs.add_argument("goal_id")
    p_gt = g_sub.add_parser("tick")
    p_gt.add_argument("goal_id")
    p_gt.add_argument("--no-executors", action="store_true")

    # `agent` subcommands
    p_agent = sub.add_parser("agent", help="Manage multi-vendor AI agents")
    a_sub = p_agent.add_subparsers(dest="agent_cmd", required=True)
    p_ar = a_sub.add_parser("register")
    p_ar.add_argument("--agent-id", required=True)
    p_ar.add_argument("--vendor", required=True)
    p_ar.add_argument("--role", action="append", default=[])
    p_ar.add_argument("--transport", default="mcp_stdio")
    p_al = a_sub.add_parser("list")
    p_al.add_argument("--vendor", default=None)
    p_ao = a_sub.add_parser("orient")
    p_ao.add_argument("--agent-id", required=True)
    p_ao.add_argument("--vendor", default="")
    p_ao.add_argument("--goal-id", default="")
    p_ao.add_argument("--work-order-id", default="")
    p_ao.add_argument("--objective", default="")
    a_sub.add_parser("discover-cli")
    p_ac = a_sub.add_parser("run-cli")
    p_ac.add_argument("--cli", required=True)
    p_ac.add_argument("--work-order-id", required=True)

    # `dispatch` subcommands (Git Portable Dispatch — Pintu B)
    p_disp = sub.add_parser("dispatch", help="Export/ingest Git Portable Dispatch bundles")
    d_sub = p_disp.add_subparsers(dest="disp_cmd", required=True)
    p_de = d_sub.add_parser("export")
    p_de.add_argument("work_order_id")
    p_de.add_argument("--agent-id", default="cloud-agent")
    p_de.add_argument("--vendor", default="antigravity")
    p_de.add_argument("--output-root", default=None)
    p_di = d_sub.add_parser("ingest")
    p_di.add_argument("return_file")

    # `relay` subcommands (Web Copy-Paste Relay — Pintu C)
    p_rel = sub.add_parser("relay", help="Zero-infra Copy-Paste Browser Relay (ChatGPT/Gemini/Muse.ai Web)")
    r_sub = p_rel.add_subparsers(dest="rel_cmd", required=True)
    p_re = r_sub.add_parser("export")
    p_re.add_argument("--vendor", default="chatgpt")
    p_re.add_argument("--agent-id", default="")
    p_re.add_argument("--goal-id", default="")
    p_re.add_argument("--work-order-id", default="")
    p_re.add_argument("--objective", default="")
    p_ri = r_sub.add_parser("ingest")
    p_ri.add_argument("--vendor", default="chatgpt")
    p_ri.add_argument("--agent-id", default="")
    p_ri.add_argument("--work-order-id", default="")
    p_ri.add_argument("--reply-json", default=None)
    p_ri.add_argument("--reply-file", default=None)

    # `vault` subcommands
    p_vault = sub.add_parser("vault", help="Manage isolated SecretVault & browser login sessions")
    v_sub = p_vault.add_subparsers(dest="vault_cmd", required=True)
    v_sub.add_parser("status")
    p_vfb = v_sub.add_parser("set-facebook")
    p_vfb.add_argument("--page-id", default="")
    p_vfb.add_argument("--page-token", default="")
    p_vbl = v_sub.add_parser("browser-login")
    p_vbl.add_argument("--venue", choices=("facebook", "kbm"), required=True)
    p_vbl.add_argument("--login-url", default="")
    p_vbl.add_argument("--wait-ms", type=int, default=180000)

    # `setup` onboarding generator
    p_setup = sub.add_parser("setup", help="Generate multi-vendor onboarding templates (antigravity/gemini/claude/codex/chatgpt/muse.ai)")
    p_setup.add_argument("--vendor", default="all")

    args = parser.parse_args(argv)
    bridge = ACEBridge(args.workspace, allow_writes=args.read_write,
                       operational=not args.research_only,
                       tool_profile=args.tool_profile)

    try:
        if args.cmd == "list":
            print(json.dumps({"tools": bridge.tools()}, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "call":
            raw = args.args_json
            if args.args_file:
                raw = Path(args.args_file).read_text(encoding="utf-8")
            arguments = json.loads(raw) if raw else {}
            if not isinstance(arguments, dict):
                raise ValueError("tool arguments must be a JSON object")
            _print_json(bridge.call(args.tool, arguments))
            return 0

        if args.cmd == "goal":
            if args.goal_cmd == "create":
                res = bridge.call("ace_op_goal_create", {
                    "title": args.title,
                    "user_request": args.request,
                    "domain": args.domain,
                    "publish_mode": args.publish_mode,
                    "min_quality_score_bp": args.min_score_bp,
                })
            elif args.goal_cmd == "list":
                res = bridge.call("ace_op_goal_list", {"status": args.status} if args.status else {})
            elif args.goal_cmd == "status":
                res = bridge.call("ace_op_goal_status", {"goal_id": args.goal_id})
            else:
                res = bridge.call("ace_op_goal_tick", {
                    "goal_id": args.goal_id,
                    "allow_executors": not args.no_executors,
                })
            _print_json(res)
            return 0

        if args.cmd == "agent":
            if args.agent_cmd == "register":
                res = bridge.call("ace_op_agent_register", {
                    "agent_id": args.agent_id,
                    "vendor": args.vendor,
                    "roles": args.role or ["creator"],
                    "transport": args.transport,
                })
            elif args.agent_cmd == "list":
                res = bridge.call("ace_op_agent_list", {"vendor": args.vendor} if args.vendor else {})
            elif args.agent_cmd == "orient":
                res = bridge.call("ace_op_agent_orient", {
                    "agent_id": args.agent_id,
                    "vendor": args.vendor,
                    "goal_id": args.goal_id,
                    "work_order_id": args.work_order_id,
                    "objective": args.objective,
                })
            elif args.agent_cmd == "discover-cli":
                from ace_operational.agent_cli_bridge import discover_installed_cli_agents
                res = {"clis": discover_installed_cli_agents()}
            else:
                if not args.read_write:
                    raise PermissionError("run-cli requires --read-write")
                op = bridge._operational_bridge()
                from ace_operational.agent_cli_bridge import run_local_cli_agent
                res = run_local_cli_agent(
                    op.store,
                    op.memory,
                    cli_name=args.cli,
                    work_order_id=args.work_order_id,
                )
            _print_json(res)
            return 0

        if args.cmd == "dispatch":
            op = bridge._operational_bridge()
            from ace_operational.portable_dispatch import export_dispatch_bundle, ingest_return_envelope
            if args.disp_cmd == "export":
                res = export_dispatch_bundle(
                    op.store,
                    op.memory,
                    work_order_id=args.work_order_id,
                    output_root=args.output_root,
                    agent_id=args.agent_id,
                    vendor=args.vendor,
                )
            else:
                if not args.read_write:
                    raise PermissionError("dispatch ingest requires --read-write")
                res = ingest_return_envelope(op.store, op.memory, return_path=args.return_file)
            _print_json(res)
            return 0

        if args.cmd == "relay":
            if args.rel_cmd == "export":
                res = build_relay_prompt(
                    bridge,
                    objective=args.objective,
                    vendor=args.vendor,
                    agent_id=args.agent_id,
                    goal_id=args.goal_id,
                    work_order_id=args.work_order_id,
                )
            else:
                if not args.read_write:
                    raise PermissionError("relay ingest requires --read-write")
                raw = Path(args.reply_file).read_text(encoding="utf-8") if args.reply_file else (args.reply_json or "")
                res = ingest_relay_reply(
                    bridge,
                    raw,
                    agent_id=args.agent_id,
                    vendor=args.vendor,
                    work_order_id=args.work_order_id,
                )
            _print_json(res)
            return 0

        if args.cmd == "vault":
            op = bridge._operational_bridge()
            from ace_operational.connectors.vault import SecretVault
            vault = SecretVault(op.store.workspace)
            if args.vault_cmd == "status":
                res = vault.all_status()
            elif args.vault_cmd == "set-facebook":
                if not args.read_write:
                    raise PermissionError("vault set-facebook requires --read-write")
                vals = {}
                if args.page_id:
                    vals["page_id"] = args.page_id
                if args.page_token:
                    vals["page_access_token"] = args.page_token
                res = vault.set_venue_credentials("facebook", vals)
            else:
                if not args.read_write:
                    raise PermissionError("vault browser-login requires --read-write")
                from ace_operational.connectors.live_browser import bootstrap_owner_login
                res = bootstrap_owner_login(
                    op.store,
                    venue=args.venue,
                    login_url=args.login_url,
                    headless=False,
                    wait_ms=args.wait_ms,
                )
            _print_json(res)
            return 0

        if args.cmd == "setup":
            repo_root = Path(__file__).resolve().parents[2]
            cfgs = _vendor_configs(Path(args.workspace), repo_root)
            want = str(args.vendor).strip().lower()
            res = {"schema": "ace.setup.v3", "workspace": str(Path(args.workspace).resolve()),
                   "vendors": cfgs if want == "all" else {want: cfgs.get(want, {})}}
            _print_json(res)
            return 0

    except Exception as exc:  # surfaced as data, mirroring the MCP error shape
        _print_json({"status": "ACE_TOOL_ERROR", "error": str(exc)})
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
