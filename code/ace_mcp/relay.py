"""Zero-Infra Browser Copy-Paste Relay for Web AIs (ChatGPT, Gemini, Muse.ai, Claude Web — Pintu C).

Requires ZERO paid LLM API keys, ZERO public HTTP tunnels, and ZERO browser extensions:
1. `build_relay_prompt`: exports a compact, copy-paste-ready Markdown prompt carrying
   Directive Packet, skills, recommended tools, and `ace.relay_reply.v1` JSON contract.
2. `ingest_relay_reply`: handles both:
   - `type = "tool_requests"`: executes requested tools via ACEBridge (respecting
     `allow_writes` gating and redacting any secrets) and returns a ready-to-paste
     `continuation_prompt` carrying real tool outputs back to the Web AI!
   - `type = "submission"`: stores external memories cleanly and routes `result`
     directly into `work_order_verifier` (generating a `revision_prompt` if score
     is below Quality Gate threshold).
"""
from __future__ import annotations

import json
from typing import Any

from ace_operational.agent_director import orient_agent
from ace_operational.connectors.vault import SecretVault, contains_secret_pattern, redact_secrets
from ace_operational.work_order_verifier import verify_work_order

VENDOR_PROFILES: dict[str, dict[str, str]] = {
    "chatgpt": {
        "label": "ChatGPT Web",
        "role_hint": "Berperanlah sebagai Strategist/Coder/Reviewer presisi tinggi. Pastikan setiap klaim punya source_ref.",
    },
    "gemini": {
        "label": "Gemini Web",
        "role_hint": "Manfaatkan riset mendalam & verifikasi silang; sertakan source_ref pada tiap fakta & tren.",
    },
    "muse.ai": {
        "label": "Muse.ai Web",
        "role_hint": "Fokus sebagai Creative Builder & Video/Media Strategist: susun hook tajam, scene visual, retention pacing, & metadata siap-produksi.",
    },
    "claude": {
        "label": "Claude Web",
        "role_hint": "Fokus pada arsitektur bersih, audit kode/naskah ketat, serta analisis risiko & edge case.",
    },
    "generic": {
        "label": "AI Web Agent",
        "role_hint": "Kerjakan objektif berbekal tool & skill ACE secara terukur tanpa mengarang.",
    },
}


def extract_relay_json(raw_text: str) -> dict[str, Any]:
    """Parse JSON from raw text or Markdown ```json fenced reply."""
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("Balasan relay kosong")
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except ValueError:
        pass

    if "```" in text:
        for block in text.split("```"):
            cand = block.strip()
            if cand.lower().startswith("json"):
                cand = cand[4:].strip()
            if cand.startswith("{"):
                try:
                    loaded = json.loads(cand)
                    if isinstance(loaded, dict):
                        return loaded
                except ValueError:
                    continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        loaded = json.loads(text[start : end + 1])
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("Tidak ditemukan balasan JSON `ace.relay_reply.v1` yang valid")


def build_relay_prompt(
    bridge: Any,
    *,
    objective: str = "",
    vendor: str = "chatgpt",
    agent_id: str = "",
    goal_id: str = "",
    work_order_id: str = "",
    role: str = "",
) -> dict[str, Any]:
    """Build a copy-paste prompt packet for any browser-based Web AI."""
    op = bridge._operational_bridge()
    vkey = str(vendor or "generic").strip().lower()
    profile = VENDOR_PROFILES.get(vkey, VENDOR_PROFILES["generic"])
    eff_agent = agent_id or f"web:{vkey}"

    packet = orient_agent(
        op.store,
        op.memory,
        agent_id=eff_agent,
        vendor=vkey,
        role=role,
        goal_id=goal_id,
        work_order_id=work_order_id,
        objective=objective,
        tool_specs=bridge.tools(),
    )

    tools_summary = "\n".join(
        f"- `{t['name']}` ({t['mode']}): {t['description'][:110]} | args={json.dumps(t['example_args'], ensure_ascii=False)}"
        for t in packet["recommended_tools"]
    )
    skills_summary = "\n".join(
        f"- `{s['name']}`: langkah={json.dumps(s['procedure_steps'], ensure_ascii=False)}"
        for s in packet["skills"]
    ) or "- (belum ada skill terkait)"

    rev_fb = packet["assignment"]["revision_history"].get("revision_feedback") or []
    rev_section = ""
    if rev_fb:
        rev_section = "\n## REVISI WAJIB (Ditolak Quality Gate sebelumnya)\n" + "\n".join(f"- {f}" for f in rev_fb) + "\n"

    prompt = (
        f"Anda sedang dikendalikan oleh **ACE Orchestrator** via Browser Relay ({profile['label']}).\n"
        f"{profile['role_hint']}\n\n"
        f"## Penugasan\n"
        f"- **Work Order ID:** `{packet['assignment']['work_order_id'] or '(sesi ad-hoc)'}`\n"
        f"- **Domain:** `{packet['assignment']['domain']}`\n"
        f"- **Objektif:** {packet['assignment']['objective']}\n"
        f"- **Ambang Mutu Wajib:** `{packet['quality_contract']['min_score_bp']} bp` (hasil di bawah nilai ini otomatis DITOLAK).\n"
        f"{rev_section}\n"
        f"## Skill Aktif ACE\n{skills_summary}\n\n"
        f"## Tool ACE yang Bisa Anda Minta Dieksekusi\n{tools_summary}\n\n"
        f"## Format Balasan WAJIB (`ace.relay_reply.v1`)\n"
        f"Balas **HANYA** dengan blok ```json dalam salah satu dari 2 format ini:\n\n"
        f"### Opsi A — Jika Anda butuh data dari tool ACE terlebih dulu:\n"
        f"```json\n"
        f"{{\n"
        f"  \"schema\": \"ace.relay_reply.v1\",\n"
        f"  \"type\": \"tool_requests\",\n"
        f"  \"requests\": [\n"
        f"    {{\"tool\": \"ace_op_memory_recall\", \"arguments\": {{\"query\": \"...\"}}}}\n"
        f"  ]\n"
        f"}}\n"
        f"```\n\n"
        f"### Opsi B — Jika siap menyerahkan hasil final terverifikasi:\n"
        f"```json\n"
        f"{{\n"
        f"  \"schema\": \"ace.relay_reply.v1\",\n"
        f"  \"type\": \"submission\",\n"
        f"  \"work_order_id\": \"{packet['assignment']['work_order_id']}\",\n"
        f"  \"result\": {{}},\n"
        f"  \"new_memories\": []\n"
        f"}}\n"
        f"```\n"
    )
    return {
        "schema": "ace.relay_export.v1",
        "vendor": vkey,
        "agent_id": eff_agent,
        "work_order_id": packet["assignment"]["work_order_id"],
        "prompt": prompt,
        "directive_packet": packet,
    }


def ingest_relay_reply(
    bridge: Any,
    raw_reply: str,
    *,
    agent_id: str = "",
    vendor: str = "chatgpt",
    work_order_id: str = "",
) -> dict[str, Any]:
    """Process one copy-pasted reply from a Web AI (`tool_requests` or `submission`)."""
    sec = contains_secret_pattern(raw_reply)
    if sec:
        raise ValueError(f"Balasan relay ditolak karena mengandung pola kredensial ({sec}); jangan tempel secret ke AI web.")

    parsed = extract_relay_json(raw_reply)
    reply_type = str(parsed.get("type") or "").strip().lower()
    if reply_type not in ("tool_requests", "submission"):
        raise ValueError("Field `type` pada ace.relay_reply.v1 wajib `'tool_requests'` atau `'submission'`")

    op = bridge._operational_bridge()
    vault = SecretVault(op.store.workspace)
    secrets_tuple = vault.secret_values()
    vkey = str(vendor or "chatgpt").strip().lower()
    eff_agent = agent_id or f"web:{vkey}"
    op.store.register_agent(agent_id=eff_agent, vendor=vkey, roles=["brain", "creator"], transport="web_relay")

    if reply_type == "tool_requests":
        requests = parsed.get("requests")
        if not isinstance(requests, list) or not requests:
            raise ValueError("`tool_requests` wajib menyertakan list `requests` tidak kosong")
        outcomes: list[dict[str, Any]] = []
        for idx, req in enumerate(requests[:12], 1):
            if not isinstance(req, dict) or not req.get("tool"):
                outcomes.append({"index": idx, "ok": False, "error": "request tanpa field `tool`"})
                continue
            tname = str(req["tool"])
            targs = req.get("arguments") or {}
            if not isinstance(targs, dict):
                outcomes.append({"index": idx, "tool": tname, "ok": False, "error": "`arguments` wajib objek JSON"})
                continue
            try:
                res = bridge.call(tname, targs)
                outcomes.append({
                    "index": idx,
                    "tool": tname,
                    "ok": True,
                    "output": redact_secrets(res, extra_secrets=secrets_tuple),
                })
            except Exception as exc:
                outcomes.append({"index": idx, "tool": tname, "ok": False, "error": str(exc)})

        continuation = (
            f"## Hasil Eksekusi Tool ACE ({len(outcomes)} panggilan)\n"
            f"```json\n{json.dumps(outcomes, indent=2, ensure_ascii=False)}\n```\n\n"
            f"Gunakan hasil tool nyata di atas (jangan mengarang), lalu balas lagi memakai skema "
            f"`ace.relay_reply.v1` (`type=\"tool_requests\"` jika butuh tool lagi, atau `type=\"submission\"` jika siap diverifikasi ACE)."
        )
        return {
            "schema": "ace.relay_ingest.v1",
            "mode": "tool_requests",
            "agent_id": eff_agent,
            "tool_results": outcomes,
            "continuation_prompt": continuation,
        }

    # `submission` branch
    eff_wo_id = str(parsed.get("work_order_id") or work_order_id or "").strip()
    result_obj = parsed.get("result")
    if not isinstance(result_obj, dict) or not result_obj:
        raise ValueError("`submission` wajib menyertakan objek `result` non-kosong")

    mem_saved = 0
    for m in parsed.get("new_memories") or []:
        txt = str(m.get("text") if isinstance(m, dict) else m).strip()
        if txt:
            res = op.memory.remember_statement(
                redact_secrets(txt, extra_secrets=secrets_tuple),
                source_kind="external",
                source_ref=eff_agent,
                sensitivity="internal",
            )
            if res.get("stored"):
                mem_saved += 1

    if not eff_wo_id:
        return {
            "schema": "ace.relay_ingest.v1",
            "mode": "submission_ad_hoc",
            "agent_id": eff_agent,
            "memories_saved": mem_saved,
            "result": result_obj,
        }

    op.store.update_work_order(
        eff_wo_id,
        status="SUBMITTED",
        claimed_by=eff_agent,
        result=result_obj,
        verification_status="UNVERIFIED",
    )
    ver = verify_work_order(
        op.store,
        op.memory,
        work_order_id=eff_wo_id,
        workspace=op.store.workspace,
        verifier_agent="ace-verifier",
    )
    revision_prompt = ""
    if not ver["passed"]:
        revision_prompt = (
            f"## HASIL DITOLAK QUALITY GATE ACE (`{ver['verdict']}`, skor `{ver['score_bp']} bp` < `{ver['min_score_bp']} bp`)\n"
            f"Alasan spesifik yang WAJIB diperbaiki:\n"
            + "\n".join(f"- {f}" for f in ver["revision_feedback"])
            + "\n\nPerbaiki bagian lemah di atas dan kirim ulang JSON `ace.relay_reply.v1` dengan `type=\"submission\"`."
        )

    return {
        "schema": "ace.relay_ingest.v1",
        "mode": "submission",
        "agent_id": eff_agent,
        "work_order_id": eff_wo_id,
        "memories_saved": mem_saved,
        "verification": ver,
        "revision_prompt": revision_prompt,
    }
