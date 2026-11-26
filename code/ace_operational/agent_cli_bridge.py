"""Local Subscribed CLI Agent Bridge (Zero Paid LLM API Adapter — Pintu D).

Discovers and invokes locally installed CLI agents (such as `gemini`, `claude`, `codex`)
that already use the owner's interactive login / subscription — never requiring paid API keys.
Fails cleanly when CLIs are not installed on the current host, and routes every CLI
submission strictly through `work_order_verifier` before accepting or triggering executors.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Sequence

from .agent_director import orient_agent
from .work_order_verifier import verify_work_order

CliRunner = Callable[..., subprocess.CompletedProcess[str]]

DEFAULT_CLI_SPECS: dict[str, dict[str, Any]] = {
    "gemini": {"binary": "gemini", "args_template": ["-p", "{prompt}"], "vendor": "gemini"},
    "claude": {"binary": "claude", "args_template": ["-p", "{prompt}"], "vendor": "claude"},
    "codex": {"binary": "codex", "args_template": ["exec", "{prompt}"], "vendor": "codex"},
}


def discover_installed_cli_agents(specs: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Detect subscribed AI CLI binaries available on PATH."""
    catalog = specs or DEFAULT_CLI_SPECS
    found: list[dict[str, Any]] = []
    for name, cfg in sorted(catalog.items()):
        bin_name = str(cfg.get("binary") or name)
        resolved = shutil.which(bin_name)
        found.append({
            "name": name,
            "vendor": str(cfg.get("vendor") or name),
            "binary": bin_name,
            "path": resolved or "",
            "available": bool(resolved),
        })
    return found


def _default_cli_runner(cmd: Sequence[str], *, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("Keluaran CLI kosong")
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass
    # Extract fenced ```json ... ``` or outermost `{...}` block.
    if "```" in text:
        for chunk in text.split("```"):
            stripped = chunk.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                try:
                    obj = json.loads(stripped)
                    if isinstance(obj, dict):
                        return obj
                except ValueError:
                    continue
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        obj = json.loads(text[first : last + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("Tidak ditemukan objek JSON yang sah pada output CLI agen")


def run_local_cli_agent(
    store: Any,
    memory: Any = None,
    *,
    cli_name: str,
    work_order_id: str,
    workspace: str | Path | None = None,
    repo_root: str | Path | None = None,
    agent_id: str = "",
    timeout_sec: int = 180,
    custom_cmd: Sequence[str] | None = None,
    runner: CliRunner = _default_cli_runner,
    verify: bool = True,
) -> dict[str, Any]:
    """Orient a local subscribed CLI agent on a work order, invoke it, and independently verify the output."""
    wo = store.get_work_order(work_order_id)
    if not wo:
        raise KeyError(f"Work order tidak ditemukan: {work_order_id}")

    spec = DEFAULT_CLI_SPECS.get(cli_name.strip().lower(), {"binary": cli_name, "args_template": ["{prompt}"], "vendor": cli_name})
    eff_agent = agent_id or f"cli:{cli_name}"
    eff_vendor = str(spec.get("vendor") or cli_name)

    if custom_cmd is None:
        resolved_bin = shutil.which(str(spec["binary"]))
        if not resolved_bin:
            return {
                "ok": False,
                "verdict": "CLI_NOT_INSTALLED",
                "cli_name": cli_name,
                "error": f"CLI lokal `{spec['binary']}` tidak terpasang di PATH; gunakan MCP atau Web Relay.",
            }
    else:
        resolved_bin = str(custom_cmd[0])

    store.register_agent(
        agent_id=eff_agent,
        vendor=eff_vendor,
        roles=[wo.get("required_role") or "creator"],
        transport="local_cli",
    )
    packet = orient_agent(
        store,
        memory,
        agent_id=eff_agent,
        vendor=eff_vendor,
        work_order_id=work_order_id,
        repo_root=Path(repo_root) if repo_root else None,
    )
    prompt = (
        f"Anda adalah agen {eff_agent} bekerja di bawah orkestrasi ACE.\n"
        f"Work Order: {work_order_id}\n"
        f"Objektif: {wo['objective']}\n"
        f"Ambil Directive Packet JSON berikut, kerjakan tugasnya secara nyata, "
        f"dan balas HANYA satu JSON berbentuk "
        f"{{\"schema\":\"ace.cli_submission.v1\",\"work_order_id\":\"{work_order_id}\",\"result\":{{...}}}}.\n\n"
        f"DIRECTIVE_PACKET:\n{json.dumps(packet, ensure_ascii=False)}"
    )

    if custom_cmd is not None:
        argv = [str(part).replace("{prompt}", prompt) for part in custom_cmd]
    else:
        argv = [resolved_bin, *[str(part).replace("{prompt}", prompt) for part in spec["args_template"]]]

    ws_path = Path(workspace or store.workspace).resolve()
    proc = runner(argv, cwd=ws_path, timeout=timeout_sec)
    if proc.returncode != 0:
        return {
            "ok": False,
            "verdict": "CLI_FAILED",
            "cli_name": cli_name,
            "exit_code": proc.returncode,
            "stderr": (proc.stderr or "")[:400],
        }

    parsed = _extract_json_payload(proc.stdout)
    result_obj = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
    store.update_work_order(
        work_order_id,
        status="SUBMITTED",
        claimed_by=eff_agent,
        result=result_obj,
        verification_status="UNVERIFIED",
    )

    verification = None
    if verify:
        verification = verify_work_order(
            store,
            memory,
            work_order_id=work_order_id,
            workspace=ws_path,
            repo_root=Path(repo_root or ws_path),
            verifier_agent="ace-verifier",
        )

    return {
        "ok": bool(verification["passed"]) if verification else True,
        "verdict": verification["verdict"] if verification else "SUBMITTED_UNVERIFIED",
        "cli_name": cli_name,
        "agent_id": eff_agent,
        "verification": verification,
    }
