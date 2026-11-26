"""Git Portable Dispatch & Return Envelope Protocol for Cloud AI Agent VMs (Pintu B).

Enables ACE to delegate tasks cleanly across disconnected cloud sandboxes
(such as Antigravity Cloud VM or Codex Cloud) purely over Git commits — Zero Paid APIs:
1. `export_dispatch_bundle`: writes secret-redacted `handover/dispatch/<work_order_id>.json` + `.md`
   including Directive Packet, skills, tool list, Quality Gate threshold, and prior feedback.
2. `ingest_return_envelope`: verifies `handover/returns/<work_order_id>.json` from a worker branch,
   runs `work_order_verifier` independently, stores `external` provenance memories, and advances Goal DAG.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .agent_director import orient_agent
from .connectors.vault import SecretVault, redact_secrets
from .orchestrator_playbook import tick_goal
from .work_order_verifier import verify_work_order


def export_dispatch_bundle(
    store: Any,
    memory: Any = None,
    *,
    work_order_id: str,
    output_root: str | Path | None = None,
    agent_id: str = "cloud-agent",
    vendor: str = "antigravity",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Export an auditable, secret-redacted handover/dispatch bundle for a remote VM agent."""
    wo = store.get_work_order(work_order_id)
    if not wo:
        raise KeyError(f"Work order tidak ditemukan: {work_order_id}")

    packet = orient_agent(
        store,
        memory,
        agent_id=agent_id,
        vendor=vendor,
        work_order_id=work_order_id,
        repo_root=Path(repo_root) if repo_root else None,
    )
    vault = SecretVault(store.workspace)
    secrets_tuple = vault.secret_values()

    bundle = {
        "schema": "ace.dispatch_bundle.v1",
        "work_order_id": work_order_id,
        "parent_task_id": wo["parent_task_id"],
        "goal_id": wo.get("goal_id", ""),
        "stage_id": wo.get("stage_id", ""),
        "objective": wo["objective"],
        "base_snapshot_hash": wo["base_snapshot_hash"],
        "acceptance_checks": wo.get("acceptance_checks", []),
        "directive_packet": packet,
        "return_contract": {
            "path": f"handover/returns/{work_order_id}.json",
            "schema": "ace.return_envelope.v1",
            "required_fields": ["schema", "work_order_id", "agent", "vendor", "result"],
        },
    }
    clean_bundle = redact_secrets(bundle, extra_secrets=secrets_tuple)
    canonical = json.dumps(clean_bundle, indent=2, sort_keys=True, ensure_ascii=False)
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    clean_bundle["bundle_sha256"] = digest

    out_base = Path(output_root or (Path(store.workspace) / "handover")).resolve()
    dispatch_dir = out_base / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    json_path = dispatch_dir / f"{work_order_id}.json"
    md_path = dispatch_dir / f"{work_order_id}.md"

    json_path.write_text(json.dumps(clean_bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    skills_md = "\n".join(
        f"- `{s['name']}` ({s['domain']}): {', '.join(s.get('procedure_steps', [])[:3])}"
        for s in packet.get("skills", [])
    ) or "- (belum ada skill spesifik)"
    tools_md = "\n".join(
        f"- `{t['name']}` [{t['mode']}]: {t['description'][:120]}"
        for t in packet.get("recommended_tools", [])
    )
    rev_notes = packet["assignment"]["revision_history"].get("revision_feedback") or []
    rev_block = ("\n## Umpan Balik Revisi Sebelumnya (WAJIB DIPERBAIKI)\n" + "\n".join(f"- {x}" for x in rev_notes) + "\n") if rev_notes else ""

    md_text = (
        f"# ACE Dispatch Work Order: `{work_order_id}`\n\n"
        f"- **Target Agen:** `{agent_id}` (`{vendor}`)\n"
        f"- **Domain:** `{packet['assignment']['domain']}`\n"
        f"- **Objektif:** {wo['objective']}\n"
        f"- **Min Quality Gate:** `{packet['quality_contract']['min_score_bp']} bp`\n"
        f"- **Dispatch SHA-256:** `{digest}`\n"
        f"{rev_block}\n"
        f"## Skill Disarankan ACE\n{skills_md}\n\n"
        f"## Tool ACE Relevan\n{tools_md}\n\n"
        f"## Protokol Pengembalian\n"
        f"Tulis hasil terverifikasi ke `handover/returns/{work_order_id}.json` mengikuti skema `ace.return_envelope.v1`.\n"
    )
    md_path.write_text(md_text, encoding="utf-8")

    return {
        "schema": "ace.dispatch_export.v1",
        "work_order_id": work_order_id,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "bundle_sha256": digest,
        "bundle": clean_bundle,
    }


def ingest_return_envelope(
    store: Any,
    memory: Any = None,
    *,
    return_path: str | Path,
    workspace: str | Path | None = None,
    repo_root: str | Path | None = None,
    verifier_agent: str = "ace-verifier",
    auto_tick_goal: bool = True,
) -> dict[str, Any]:
    """Ingest `handover/returns/<wo>.json`, store external provenance memories, verify, and advance DAG."""
    rpath = Path(return_path).resolve()
    if not rpath.is_file():
        raise FileNotFoundError(f"Berkas return envelope tidak ditemukan: {rpath}")
    data = json.loads(rpath.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Return envelope wajib berupa objek JSON")

    wo_id = str(data.get("work_order_id") or "").strip()
    if not wo_id:
        raise ValueError("Return envelope wajib memiliki `work_order_id`")
    agent = str(data.get("agent") or "cloud-agent").strip()[:80]
    vendor = str(data.get("vendor") or "external").strip().lower()[:40]
    result = data.get("result")
    if not isinstance(result, dict) or not result:
        raise ValueError("Return envelope wajib memiliki `result` non-kosong")

    # Register/heartbeat remote agent if not yet registered.
    store.register_agent(agent_id=agent, vendor=vendor, roles=[str(data.get("role") or "creator")], transport="git_handover")

    # Persist external memories cleanly tagged with external provenance (never forged as operator evidence).
    memories_saved = 0
    if memory is not None:
        for item in data.get("new_memories") or []:
            txt = str(item.get("text") if isinstance(item, dict) else item).strip()
            if txt:
                res = memory.remember_statement(
                    redact_secrets(txt),
                    source_kind="external",
                    source_ref=f"{vendor}:{agent}",
                    sensitivity="internal",
                )
                if res.get("stored"):
                    memories_saved += 1

    store.update_work_order(
        wo_id,
        status="SUBMITTED",
        claimed_by=agent,
        result=result,
        verification_status="UNVERIFIED",
    )

    ws_path = Path(workspace or store.workspace).resolve()
    root_path = Path(repo_root or ws_path).resolve()
    wo = store.get_work_order(wo_id)

    verification = verify_work_order(
        store,
        memory,
        work_order_id=wo_id,
        workspace=ws_path,
        repo_root=root_path,
        verifier_agent=verifier_agent,
    )

    tick_res = None
    if auto_tick_goal and wo and wo.get("goal_id") and verification["passed"]:
        # tick_goal expects SUBMITTED -> verifies, OR if already COMPLETED checks stage_advanced.
        tick_res = tick_goal(store, memory, goal_id=wo["goal_id"], workspace=ws_path, repo_root=root_path)

    return {
        "schema": "ace.return_ingest_report.v1",
        "work_order_id": wo_id,
        "agent": agent,
        "vendor": vendor,
        "memories_saved": memories_saved,
        "verification": verification,
        "goal_tick": tick_res,
    }
