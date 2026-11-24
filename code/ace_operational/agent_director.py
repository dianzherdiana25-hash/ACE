"""Agent Director: unified tool/skill indexing, agent orientation, and verified skill absorption.

Combines:
- Catalog search across ACE's full MCP & repo toolbox (`search_tools`)
- Role-aware Directive Packet builder (`orient_agent`) tailored to each agent/work-order
- Skill absorption bridge linking `ace_web_operator` gating & verification into `OperationalStore.skills`
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Sequence

from ace_web_operator import skill_absorber, skill_verifier, source_quality_gate
from ace_web_operator._contracts import ContractError
from .connectors.vault import SecretVault, redact_secrets

_TOKEN_RE = re.compile(r"[a-z0-9_]+")

CORE_PROFILE_TOOLS: frozenset[str] = frozenset({
    "ace_status",
    "ace_op_status",
    "ace_op_task_list",
    "ace_op_task_get",
    "ace_op_task_create",
    "ace_op_task_update_status",
    "ace_op_memory_remember",
    "ace_op_memory_recall",
    "ace_op_memory_forget",
    "ace_op_memory_audit",
    "ace_op_receipt_list",
    "ace_op_skill_list",
    "ace_op_skill_get",
    "ace_op_skill_create",
    "ace_op_skill_record_outcome",
    "ace_op_skill_absorb",
    "ace_op_frontier_list",
    "ace_op_gap_list",
    "ace_op_gap_report",
    "ace_op_work_order_create",
    "ace_op_work_order_list",
    "ace_op_work_order_submit",
    "ace_op_work_order_claim",
    "ace_op_work_order_release",
    "ace_op_work_order_verify",
    "ace_op_agent_register",
    "ace_op_agent_heartbeat",
    "ace_op_agent_list",
    "ace_op_agent_orient",
    "ace_op_goal_create",
    "ace_op_goal_status",
    "ace_op_goal_tick",
    "ace_op_tool_search",
    "ace_op_tool_invoke",
    "ace_op_quality_evaluate",
    "ace_op_outcome_record",
    "ace_op_vault_status",
    "ace_op_file_write",
    "ace_op_verify_task",
})


def classify_tool_category(name: str, description: str = "") -> str:
    n = name.lower()
    desc = description.lower()
    if n.startswith("ace_op_agent_"):
        return "agents"
    if n.startswith("ace_op_goal_"):
        return "goals"
    if n.startswith("ace_op_work_order_"):
        return "work_orders"
    if n.startswith("ace_op_task_"):
        return "tasks"
    if "memory" in n:
        return "memory"
    if "skill" in n:
        return "skills"
    if n.startswith("ace_op_quality") or n.startswith("ace_op_outcome") or n == "ace_op_verify_task":
        return "quality"
    if "kbm" in n or "arc_rubric" in desc:
        return "kbm"
    if "reels" in n or "media" in n or "video" in desc:
        return "media"
    if "git" in n:
        return "git"
    if n.startswith("ace_op_tool_guardian"):
        return "guardian"
    if n.startswith("ace_op_tool_presence"):
        return "presence"
    if n.startswith("ace_op_tool_deliberation"):
        return "deliberation"
    if n.startswith("ace_op_tool_factory"):
        return "software_factory"
    if n in ("ace_status", "ace_op_status", "ace_op_tool_search", "ace_op_tool_invoke", "ace_op_vault_status"):
        return "orchestrator_core"
    if n.startswith("ace_op_"):
        return "operational_tools"
    return "research_runtime"


def _load_default_specs() -> list[dict[str, Any]]:
    from ace_mcp.op_bridge import OP_TOOL_SPECS

    return list(OP_TOOL_SPECS)


def is_core_profile_tool(name: str) -> bool:
    return name in CORE_PROFILE_TOOLS


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(str(text).lower()) if len(t) >= 2}


def _example_args_for_schema(schema: dict[str, Any]) -> dict[str, Any]:
    props = schema.get("properties") or {}
    req = list(schema.get("required") or ())
    example: dict[str, Any] = {}
    keys = req if req else list(props.keys())[:4]
    for key in keys:
        spec = props.get(key) or {}
        t = spec.get("type", "string")
        if t == "integer":
            example[key] = 1
        elif t == "number":
            example[key] = 1.0
        elif t == "boolean":
            example[key] = True
        elif t == "array":
            example[key] = []
        elif t == "object":
            example[key] = {}
        else:
            enum = spec.get("enum")
            example[key] = enum[0] if enum else f"<{key}>"
    return example


def search_tools(
    query: str = "",
    *,
    category: str | None = None,
    mode: str | None = None,
    tool_specs: Sequence[dict[str, Any]] | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Search ACE's registered MCP/operational tool catalog by query, category, or read/write mode."""
    specs = list(tool_specs) if tool_specs is not None else _load_default_specs()
    q_tokens = _tokens(query)
    q_lower = str(query or "").strip().lower()
    want_cat = str(category).strip().lower() if category else None
    want_mode = str(mode).strip().lower() if mode else None

    matches: list[tuple[int, str, dict[str, Any]]] = []
    for spec in specs:
        name = str(spec["name"])
        desc = str(spec.get("description") or "")
        cat = classify_tool_category(name, desc)
        readonly = bool((spec.get("annotations") or {}).get("readOnlyHint", True))
        tool_mode = "read" if readonly else "write"

        if want_cat and cat != want_cat:
            continue
        if want_mode and tool_mode != want_mode:
            continue

        score = 0
        if not q_tokens:
            score = 10 if name in CORE_PROFILE_TOOLS else 5
        else:
            name_toks = _tokens(name.replace("_", " "))
            desc_toks = _tokens(desc)
            cat_toks = _tokens(cat)
            if q_lower and q_lower in name.lower():
                score += 40
            score += 12 * len(q_tokens & name_toks)
            score += 8 * len(q_tokens & cat_toks)
            score += 3 * len(q_tokens & desc_toks)
            if score == 0:
                continue

        schema = spec.get("inputSchema") or {}
        entry = {
            "name": name,
            "category": cat,
            "mode": tool_mode,
            "core_profile": name in CORE_PROFILE_TOOLS,
            "required_args": list(schema.get("required") or []),
            "description": desc,
            "example_args": _example_args_for_schema(schema),
        }
        matches.append((score, name, entry))

    matches.sort(key=lambda row: (-row[0], row[1]))
    lim = max(1, min(50, int(limit or 12)))
    selected = [row[2] for row in matches[:lim]]
    return {
        "schema": "ace.tool_search.v1",
        "query": query,
        "category": want_cat or "",
        "mode": want_mode or "",
        "total_catalog": len(specs),
        "matched_count": len(matches),
        "tools": selected,
    }


def _frozen_upstream_paths(repo_root: Path | None = None) -> list[str]:
    root = repo_root or Path(__file__).resolve().parents[2]
    manifest = root / "docs" / "UPSTREAM_SOURCES.json"
    if not manifest.is_file():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        files = data.get("files") if isinstance(data, dict) else []
        if isinstance(files, list):
            return [str(f.get("path") or "") for f in files if isinstance(f, dict) and f.get("path")]
    except (OSError, ValueError):
        return []
    return []


def orient_agent(
    store: Any,
    memory: Any,
    *,
    agent_id: str,
    vendor: str = "",
    role: str = "",
    goal_id: str = "",
    work_order_id: str = "",
    objective: str = "",
    tool_specs: Sequence[dict[str, Any]] | None = None,
    repo_root: Path | None = None,
    record_heartbeat: bool = True,
) -> dict[str, Any]:
    """Build an authoritative Directive Packet telling an AI agent what to do, which skills/tools to use, and what Quality Gate bar applies."""
    vault = SecretVault(store.workspace)
    extra_secrets = vault.secret_values()

    agent_rec = store.get_agent(agent_id)
    if record_heartbeat:
        if agent_rec is None and vendor:
            agent_rec = store.register_agent(
                agent_id=agent_id,
                vendor=vendor,
                roles=[role or "creator"],
                transport="mcp_stdio",
            )
        elif agent_rec is not None:
            agent_rec = store.heartbeat_agent(agent_id, status="ONLINE")

    eff_vendor = vendor or (agent_rec["vendor"] if agent_rec else "generic")
    wo = store.get_work_order(work_order_id) if work_order_id else None
    goal = store.get_goal(goal_id or (wo["goal_id"] if wo else "")) if (goal_id or (wo and wo.get("goal_id"))) else None

    eff_role = role or (wo["required_role"] if wo and wo.get("required_role") else "creator")
    eff_objective = objective or (wo["objective"] if wo else (goal["user_request"] if goal else ""))
    eff_domain = (goal["domain"] if goal else "") or "general"

    query_text = " ".join(x for x in (eff_domain, eff_role, eff_objective) if x).strip()
    q_tokens = _tokens(query_text)

    # Top-3 relevant active skills (exclude suspended skills).
    skills = store.list_skills(active_only=True)
    ranked_skills: list[tuple[int, dict[str, Any]]] = []
    for sk in skills:
        sk_tokens = _tokens(" ".join([sk["name"], sk["domain"], " ".join(sk["procedure_steps"])]))
        overlap = len(q_tokens & sk_tokens)
        dom_bonus = 5 if eff_domain != "general" and eff_domain in sk["domain"].lower() else 0
        succ_bonus = min(5, int(sk.get("success_count", 0)))
        ranked_skills.append((overlap * 10 + dom_bonus + succ_bonus, sk))
    ranked_skills.sort(key=lambda r: (-r[0], r[1]["name"]))
    top_skills = [r[1] for r in ranked_skills[:3]]

    # Top-8 relevant ACE tools for the domain/role.
    tool_query = query_text
    if eff_domain == "video_reels":
        tool_query += " reels media video quality"
    elif eff_domain == "kbm_apps":
        tool_query += " kbm arc_rubric quality"
    elif eff_domain == "code_evolution":
        tool_query += " git code quality work_order"
    recommended_tools = search_tools(
        tool_query,
        tool_specs=tool_specs,
        limit=8,
    )["tools"]

    # Relevant non-private memories (never private, scrubbed of secrets).
    recalled = memory.recall_memories(
        query_text or eff_domain,
        limit=6,
        include_private=False,
        include_superseded=False,
    ) if memory is not None else {"results": []}

    open_gaps = store.list_gaps(status="OPEN")[:5]

    min_score_bp = int(goal["min_quality_score_bp"]) if goal else 8500
    max_revs = int(goal["max_revisions"]) if goal else 3

    revision_history: dict[str, Any] = {}
    if wo:
        revision_history = {
            "revision_count": wo.get("revision_count", 0),
            "last_quality_score_bp": wo.get("quality_score_bp", 0),
            "revision_feedback": (wo.get("payload") or {}).get("revision_feedback", []),
        }

    packet = {
        "schema": "ace.directive_packet.v1",
        "agent": {
            "agent_id": agent_id,
            "vendor": eff_vendor,
            "role": eff_role,
            "registered": agent_rec is not None,
        },
        "assignment": {
            "goal_id": goal["goal_id"] if goal else "",
            "domain": eff_domain,
            "publish_mode": goal["publish_mode"] if goal else "auto",
            "work_order_id": wo["work_order_id"] if wo else "",
            "objective": eff_objective,
            "required_skills": wo.get("required_skills", []) if wo else [],
            "acceptance_checks": wo.get("acceptance_checks", []) if wo else [],
            "payload": wo.get("payload", {}) if wo else {},
            "revision_history": revision_history,
        },
        "quality_contract": {
            "min_score_bp": min_score_bp,
            "max_revisions": max_revs,
            "reject_below_bar": True,
            "anti_hallucination_rules": [
                "Setiap klaim riset, angka, atau tren wajib menyertakan `source_ref` yang dapat diverifikasi; klaim tanpa rujukan otomatis ditolak (`UNGROUNDED_CLAIMS`).",
                "Hasil dengan skor di bawah ambang Quality Gate (`min_score_bp`) ditolak (`REJECTED_BELOW_BAR`) dan tidak boleh masuk auto-merge atau auto-publish.",
                "Pekerjaan sensitif atau lintas tahap memerlukan cross-review oleh agen/vendor berbeda bila tersedia.",
            ],
        },
        "skills": top_skills,
        "recommended_tools": recommended_tools,
        "memories": recalled.get("results", []),
        "open_gaps": open_gaps,
        "protected_paths": {
            "forbidden_vault_dir": "vault/",
            "upstream_frozen_count": len(_frozen_upstream_paths(repo_root)),
            "upstream_frozen_sample": _frozen_upstream_paths(repo_root)[:5],
        },
        "submission_protocol": {
            "submit_tool": "ace_op_work_order_submit",
            "verify_tool": "ace_op_work_order_verify",
            "agent_field": agent_id,
        },
    }
    return redact_secrets(packet, extra_secrets=extra_secrets)


def absorb_verified_skill(
    store: Any,
    memory: Any = None,
    *,
    name: str,
    domain: str,
    procedure_steps: Sequence[str],
    preconditions: Sequence[str] = (),
    boundary_limitations: Sequence[str] = (),
    verification_template: dict[str, Any] | None = None,
    source_task_ids: Sequence[str] = (),
    source_refs: Sequence[str] = (),
    checks_passed: Sequence[str] = (),
    verified_score_bp: int = 8500,
    min_score_bp: int = 8500,
    absorption_root: Path | None = None,
    quality_policy: dict[str, Any] | None = None,
    curriculum: dict[str, Any] | None = None,
    verification_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate external research/skills via quality/verification checks before storing in OperationalStore.skills."""
    if not procedure_steps or not any(str(s).strip() for s in procedure_steps):
        raise ValueError("Skill wajib memiliki minimal 1 procedure_step nyata")
    if not source_refs:
        raise ValueError("Penyerapan skill ditolak (UNGROUNDED): wajib menyertakan minimal 1 source_ref bukti")
    if not checks_passed:
        raise ValueError("Penyerapan skill ditolak (UNVERIFIED): wajib menyertakan minimal 1 bukti cek lolos")
    if int(verified_score_bp) < int(min_score_bp):
        return {
            "accepted": False,
            "reason": "BELOW_QUALITY_BAR",
            "score_bp": int(verified_score_bp),
            "min_score_bp": int(min_score_bp),
        }

    gate_receipt: dict[str, Any] | None = None
    if quality_policy is not None and curriculum is not None and absorption_root is not None:
        expected_policy_sha = sha256(
            json.dumps(quality_policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        try:
            skill_pkg, gate_receipt = source_quality_gate.sift_and_absorb(
                absorption_root, quality_policy, expected_policy_sha, curriculum
            )
        except ContractError as exc:
            return {"accepted": False, "reason": "SOURCE_QUALITY_CONTRACT_ERROR", "error": str(exc)}
        if skill_pkg is None:
            return {"accepted": False, "reason": "SOURCE_QUALITY_HELD", "gate_receipt": gate_receipt}
        # Confirm held-out verifier passes if full verification bundle supplied.
        if verification_bundle is not None:
            pkg = verification_bundle.get("package", skill_pkg)
            pkg_sha = verification_bundle["package_sha256"]
            suite = verification_bundle["suite"]
            answers = verification_bundle["answers"]
            ans_sha = verification_bundle["answer_sha256"]
            proof = skill_verifier.evaluate(pkg, pkg_sha, suite, answers, ans_sha)
            if not proof.get("passed"):
                return {"accepted": False, "reason": "HELDOUT_VERIFIER_FAILED", "proof": proof}

    # Verify absorber's normalizer is exercised for deterministic skill key naming.
    canonical_name = skill_absorber.normalized(name).replace(" ", "_")
    saved = store.save_skill(
        name=canonical_name,
        domain=str(domain).strip() or "general",
        preconditions=[str(p) for p in preconditions],
        boundary_limitations=[str(b) for b in boundary_limitations],
        procedure_steps=[str(s) for s in procedure_steps],
        verification_template={
            **(verification_template or {}),
            "source_refs": [str(r) for r in source_refs],
            "checks_passed": [str(c) for c in checks_passed],
            "verified_score_bp": int(verified_score_bp),
        },
        source_task_ids=[str(t) for t in source_task_ids],
    )
    if memory is not None:
        memory.remember_statement(
            f"Skill terverifikasi '{canonical_name}' (domain {domain}, skor {verified_score_bp}bp) aktif disimpan.",
            source_kind="operator",
            source_ref=f"skill:{saved['skill_id']}",
            sensitivity="internal",
        )
    return {
        "accepted": True,
        "skill": saved,
        "gate_receipt": gate_receipt,
    }
