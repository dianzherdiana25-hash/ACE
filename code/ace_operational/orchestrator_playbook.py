"""Goal DAG Playbooks & Tick Engine for ACE v3 Multi-Agent Orchestration.

Drives structured, multi-stage goals from inception to verified real-world delivery:
- `code_evolution`: PLAN -> IMPLEMENT -> CROSS_REVIEW -> QUALITY_GATE -> GIT_PR_AND_MERGE
- `video_reels`: TREND_RESEARCH -> STRATEGY_AND_SCRIPT -> RENDER_9_16_MP4 -> FINAL_MEDIA_QA -> PUBLISH_REELS
- `kbm_apps`: SERIES_AUDIT_AND_STRATEGY -> DRAFT_CHAPTERS -> KBM_HIGH_BAR_GATE -> ACCOUNT_EXECUTION
- `research` / `general`: PLAN -> PRODUCE -> QUALITY_GATE -> DELIVER

Strictly enforces High-Bar Quality Gates (`>= min_quality_score_bp`) before advancing
or triggering real-world executors (`git_ops`, `facebook_reels`, `kbm_operator`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .connectors import facebook_reels, kbm_operator
from .git_ops import load_host_policy, prepare_branch_and_commit, push_and_open_pr, verify_checks_and_merge_pr
from .quality_gate_engine import DEFAULT_MIN_QUALITY_SCORE_BP, evaluate_code_quality, evaluate_kbm_quality, evaluate_reels_quality
from .work_order_verifier import verify_work_order


def build_stages_for_domain(
    domain: str,
    *,
    preferred_vendors: dict[str, str] | None = None,
    stage_configs: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    prefs = preferred_vendors or {}
    cfgs = stage_configs or {}
    dom = str(domain or "general").strip().lower()

    if dom == "code_evolution":
        raw = [
            ("PLAN", "brain", [{"kind": "evidence_presence"}]),
            ("IMPLEMENT", "coder", [{"kind": "code_quality"}]),
            ("CROSS_REVIEW", "critic", [{"kind": "cross_review"}]),
            ("QUALITY_GATE", "ace_gate", []),
            ("GIT_PR_AND_MERGE", "executor:git_ops", []),
        ]
    elif dom == "video_reels":
        raw = [
            ("TREND_RESEARCH", "researcher", [{"kind": "research_grounding"}]),
            ("STRATEGY_AND_SCRIPT", "creator", [{"kind": "reels_quality", "require_rendered_mp4": False}]),
            ("RENDER_9_16_MP4", "executor:reels_pipeline", []),
            ("FINAL_MEDIA_QA", "ace_gate", []),
            ("PUBLISH_REELS", "executor:facebook_reels", []),
        ]
    elif dom == "kbm_apps":
        raw = [
            ("SERIES_AUDIT_AND_STRATEGY", "researcher", [{"kind": "evidence_presence"}]),
            ("DRAFT_CHAPTERS", "creator", [{"kind": "kbm_quality"}]),
            ("KBM_HIGH_BAR_GATE", "ace_gate", []),
            ("ACCOUNT_EXECUTION", "executor:kbm_operator", []),
        ]
    else:
        raw = [
            ("PLAN", "brain", [{"kind": "evidence_presence"}]),
            ("PRODUCE", "creator", [{"kind": "evidence_presence"}]),
            ("QUALITY_GATE", "ace_gate", []),
            ("DELIVER", "executor:deliver", []),
        ]

    stages = []
    for name, role, checks in raw:
        st_cfg = dict(cfgs.get(name) or {})
        if checks and "acceptance_checks" not in st_cfg:
            st_cfg["acceptance_checks"] = checks
        stages.append({
            "name": name,
            "required_role": role,
            "preferred_vendor": str(prefs.get(name) or prefs.get(role) or ""),
            "stage_config": st_cfg,
        })
    return stages


def _ensure_stage_work_order(store: Any, goal: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any] | None:
    if stage["required_role"] == "ace_gate" or stage["required_role"].startswith("executor:"):
        return None
    if stage.get("work_order_id"):
        existing = store.get_work_order(stage["work_order_id"])
        if existing:
            return existing

    # Avoid assigning reviewer to creator's own agent/vendor when multiple registered agents exist.
    meta = goal.get("metadata") or {}
    excl_agents: tuple[str, ...] = ()
    excl_vendors: tuple[str, ...] = ()
    if stage["required_role"] == "critic":
        c_agent = str(meta.get("creator_agent") or "").strip()
        c_vendor = str(meta.get("creator_vendor") or "").strip()
        if c_agent:
            excl_agents = (c_agent,)
        if c_vendor:
            excl_vendors = (c_vendor,)

    chosen = store.select_agent_for_role(
        stage["required_role"],
        preferred_vendor=stage.get("preferred_vendor", ""),
        exclude_agents=excl_agents,
        exclude_vendors=excl_vendors,
    )
    assigned_agent = chosen["agent_id"] if chosen else ""
    cfg = stage.get("stage_config") or {}
    checks = cfg.get("acceptance_checks") or [{"kind": "evidence_presence"}]
    payload = {
        "goal_title": goal["title"],
        "domain": goal["domain"],
        "stage_name": stage["name"],
        "min_quality_score_bp": goal["min_quality_score_bp"],
        "creator_agent": meta.get("creator_agent", ""),
        "creator_vendor": meta.get("creator_vendor", ""),
        "prior_stage_outputs": {
            k: v
            for k, v in meta.items()
            if k in ("latest_claims", "latest_reels_package", "latest_kbm_package", "latest_code_result", "rendered_bundle")
        },
        **cfg.get("payload", {}),
    }
    snap_hash = hashlib.sha256(
        json.dumps({"goal_id": goal["goal_id"], "stage": stage["stage_id"]}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    wo, _ = store.create_work_order(
        parent_task_id=goal["parent_task_id"],
        mission_id=goal["goal_id"],
        idempotency_key=f"goal:{goal['goal_id']}:stage:{stage['stage_order']}",
        worker_kind=stage["required_role"],
        objective=f"[{goal['domain']}:{stage['name']}] {goal['user_request']}",
        base_snapshot_hash=snap_hash,
        payload=payload,
        goal_id=goal["goal_id"],
        stage_id=stage["stage_id"],
        assigned_agent=assigned_agent,
        required_role=stage["required_role"],
        required_skills=cfg.get("required_skills", []),
        acceptance_checks=checks,
    )
    store.update_goal_stage(stage["stage_id"], work_order_id=wo["work_order_id"], status="ACTIVE")
    return wo


def create_goal(
    store: Any,
    *,
    title: str,
    user_request: str,
    domain: str = "general",
    publish_mode: str = "auto",
    min_quality_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
    max_revisions: int = 3,
    require_cross_review: bool = True,
    preferred_vendors: dict[str, str] | None = None,
    stage_configs: dict[str, dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    stages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create parent task + Goal DAG + initial work order ready for multi-agent execution."""
    parent = store.create_task(
        kind=f"goal_{domain}",
        title_id=title,
        user_request=user_request,
        normalized_goal=user_request,
        priority=10.0,
    )
    dag_stages = stages or build_stages_for_domain(
        domain,
        preferred_vendors=preferred_vendors,
        stage_configs=stage_configs,
    )
    goal = store.create_goal_with_stages(
        parent_task_id=parent["task_id"],
        title=title,
        user_request=user_request,
        domain=domain,
        publish_mode=publish_mode,
        min_quality_score_bp=min_quality_score_bp,
        max_revisions=max_revisions,
        require_cross_review=require_cross_review,
        quality_policy={"min_quality_score_bp": min_quality_score_bp, "reject_below_bar": True},
        metadata=metadata or {},
        stages=dag_stages,
    )
    first_stage = goal["stages"][0]
    _ensure_stage_work_order(store, goal, first_stage)
    store.emit_event(
        task_id=parent["task_id"],
        kind="goal_created",
        status="ACTIVE",
        summary_code="goal_dag_created",
        technical_detail={"goal_id": goal["goal_id"], "domain": domain, "stages": [s["name"] for s in dag_stages]},
    )
    return store.get_goal(goal["goal_id"])  # type: ignore[return-value]


def _absorb_stage_result_to_goal_meta(store: Any, goal: dict[str, Any], stage: dict[str, Any], wo: dict[str, Any], receipt_id: str, score_bp: int) -> dict[str, Any]:
    meta = dict(goal.get("metadata") or {})
    res = wo.get("result") or {}
    meta["last_receipt_id"] = receipt_id
    meta["last_quality_score_bp"] = score_bp
    if wo.get("claimed_by"):
        meta.setdefault("contributors", [])
        if wo["claimed_by"] not in meta["contributors"]:
            meta["contributors"] = [*meta["contributors"], wo["claimed_by"]]
        if stage["required_role"] in ("coder", "creator", "brain"):
            meta["creator_agent"] = wo["claimed_by"]
            ag = store.get_agent(wo["claimed_by"])
            meta["creator_vendor"] = ag["vendor"] if ag else ""

    if "claims" in res:
        meta["latest_claims"] = {"claims": res.get("claims"), "sources": res.get("sources")}
    if "reels_package" in res or "scenes" in res or "script_scenes" in res:
        pkg = dict(res.get("reels_package") if isinstance(res.get("reels_package"), dict) else res)
        meta["latest_reels_package"] = pkg
    if "kbm_package" in res or "chapters" in res or "manuscript_path" in res:
        pkg = dict(res.get("kbm_package") if isinstance(res.get("kbm_package"), dict) else res)
        meta["latest_kbm_package"] = pkg
    if "target_files" in res or "test_commands" in res or "commit_message" in res:
        meta["latest_code_result"] = {
            **dict(meta.get("latest_code_result") or {}),
            **{k: v for k, v in res.items() if k in ("target_files", "test_commands", "commit_message", "slug", "pr_title", "pr_body")},
        }
    return meta


def _advance_stage(store: Any, goal: dict[str, Any], stage_idx: int, *, receipt_id: str = "", score_bp: int = 0) -> dict[str, Any]:
    stages = goal["stages"]
    cur_stage = stages[stage_idx]
    store.update_goal_stage(
        cur_stage["stage_id"],
        status="COMPLETED",
        quality_score_bp=score_bp or cur_stage["quality_score_bp"],
        execution_receipt_id=receipt_id or cur_stage["execution_receipt_id"],
    )
    next_idx = stage_idx + 1
    if next_idx >= len(stages):
        if store.get_task(goal["parent_task_id"]):
            cur_t = store.get_task(goal["parent_task_id"])
            if cur_t and cur_t["status"] != "COMPLETED":
                try:
                    store.update_task(goal["parent_task_id"], status="COMPLETED")
                except ValueError:
                    pass
        return store.update_goal(
            goal["goal_id"],
            status="COMPLETED",
            current_stage_index=next_idx - 1,
            final_receipt_id=receipt_id or goal.get("final_receipt_id", ""),
        )
    next_stage = stages[next_idx]
    store.update_goal_stage(next_stage["stage_id"], status="ACTIVE")
    updated_goal = store.update_goal(goal["goal_id"], status="ACTIVE", current_stage_index=next_idx)
    _ensure_stage_work_order(store, updated_goal, updated_goal["stages"][next_idx])
    return store.get_goal(goal["goal_id"])  # type: ignore[return-value]


def _run_ace_gate_stage(store: Any, goal: dict[str, Any], stage: dict[str, Any], *, workspace: Path, repo_root: Path) -> dict[str, Any]:
    meta = goal.get("metadata") or {}
    min_bp = int(goal["min_quality_score_bp"])
    dom = goal["domain"]

    if dom == "video_reels":
        pkg = dict(meta.get("latest_reels_package") or {})
        rendered = meta.get("rendered_bundle") or {}
        if rendered.get("video_path"):
            pkg["video_path"] = rendered["video_path"]
        ver = evaluate_reels_quality(pkg, min_score_bp=min_bp, require_rendered_mp4=bool(pkg.get("video_path")))
    elif dom == "kbm_apps":
        pkg = dict(meta.get("latest_kbm_package") or {})
        ver = evaluate_kbm_quality(pkg, min_score_bp=min_bp)
    elif dom == "code_evolution":
        cr = meta.get("latest_code_result") or {}
        ver = evaluate_code_quality(
            workspace,
            repo_root=repo_root,
            target_files=cr.get("target_files") or (),
            test_commands=cr.get("test_commands") or (),
            min_score_bp=min_bp,
        )
    else:
        score = int(meta.get("last_quality_score_bp") or min_bp)
        passed = bool(meta.get("last_receipt_id")) and score >= min_bp
        ver = {
            "passed": passed,
            "verdict": "PASS" if passed else "REJECTED_BELOW_BAR",
            "score_bp": score if meta.get("last_receipt_id") else 0,
            "min_score_bp": min_bp,
            "revision_feedback": [] if passed else ["Belum ada bukti receipt yang memenuhi ambang kualitas."],
        }

    if not ver["passed"]:
        store.update_goal_stage(
            stage["stage_id"],
            status="REVISION_NEEDED",
            quality_score_bp=int(ver["score_bp"]),
            verifier_report=ver,
        )
        store.update_goal(
            goal["goal_id"],
            status="REVISION_NEEDED",
            error_summary="; ".join(ver.get("revision_feedback", []))[:400],
        )
        return {"action": "rejected_at_gate", "verdict": ver, "goal": store.get_goal(goal["goal_id"])}

    rcpt = store.record_receipt(
        task_id=goal["parent_task_id"],
        action_kind=f"goal_gate_{dom}",
        input_data=json.dumps({"goal_id": goal["goal_id"], "stage": stage["name"]}),
        output_data=json.dumps(ver, sort_keys=True, ensure_ascii=False),
        command_or_operation=f"ace_gate:{dom}",
        exit_code=0,
        stdout_text=f"PASS score_bp={ver['score_bp']}",
        verified_by="ace-quality-gate",
        passed=True,
    )
    store.update_goal(
        goal["goal_id"],
        metadata_updates={"last_receipt_id": rcpt["receipt_id"], "last_quality_score_bp": ver["score_bp"]},
    )
    updated_goal = _advance_stage(
        store, store.get_goal(goal["goal_id"]), stage["stage_order"], receipt_id=rcpt["receipt_id"], score_bp=int(ver["score_bp"])
    )
    return {"action": "gate_passed", "verdict": ver, "receipt": rcpt, "goal": updated_goal}


def _run_executor_stage(store: Any, goal: dict[str, Any], stage: dict[str, Any], *, workspace: Path, repo_root: Path) -> dict[str, Any]:
    role = stage["required_role"]
    meta = goal.get("metadata") or {}
    cfg = stage.get("stage_config") or {}

    if role == "executor:reels_pipeline":
        from ace_media_studio.reels_pipeline import render_vertical_reels

        pkg = dict(meta.get("latest_reels_package") or {})
        out_dir = Path(cfg.get("output_dir") or (workspace / "artifacts" / "reels" / goal["goal_id"]))
        bundle = render_vertical_reels(
            pkg,
            out_dir,
            width=int(cfg.get("width", 720)),
            height=int(cfg.get("height", 1280)),
            fps=int(cfg.get("fps", 24)),
            renderer=str(cfg.get("renderer") or "auto"),
        )
        pkg["video_path"] = bundle["video_path"]
        pkg["cover_path"] = bundle["cover_path"]
        rcpt = store.record_receipt(
            task_id=goal["parent_task_id"],
            action_kind="reels_render_mp4",
            input_data=json.dumps({"goal_id": goal["goal_id"], "renderer": bundle.get("renderer", "auto")}),
            output_data=json.dumps(bundle["probe"], sort_keys=True),
            command_or_operation="reels_pipeline.render_vertical_reels",
            exit_code=0,
            stdout_text=bundle["video_path"],
            artifacts_created=[bundle["video_path"], bundle["cover_path"], bundle["subtitle_path"]],
            verified_by="ace-reels-pipeline",
            passed=True,
        )
        store.update_goal(
            goal["goal_id"],
            metadata_updates={"rendered_bundle": bundle, "latest_reels_package": pkg},
        )
        updated = _advance_stage(
            store, store.get_goal(goal["goal_id"]), stage["stage_order"], receipt_id=rcpt["receipt_id"], score_bp=int(meta.get("last_quality_score_bp", 8500))
        )
        return {"action": "reels_rendered", "bundle": bundle, "goal": updated}

    if role == "executor:facebook_reels":
        pkg = dict(meta.get("latest_reels_package") or {})
        rendered = meta.get("rendered_bundle") or {}
        video_path = rendered.get("video_path") or pkg.get("video_path") or ""
        pub = facebook_reels.publish_reel(
            store,
            package=pkg,
            video_path=video_path,
            task_id=goal["parent_task_id"],
            backend=str(cfg.get("backend") or "live_browser"),
            publish_mode=goal["publish_mode"],
            dry_run=bool(cfg.get("dry_run", False)),
            min_score_bp=goal["min_quality_score_bp"],
            reels_create_url=str(cfg.get("reels_create_url") or facebook_reels.DEFAULT_FACEBOOK_REELS_URL),
            allowed_hosts=cfg.get("allowed_hosts") or (),
            selectors=cfg.get("selectors"),
            policy_override=bool(cfg.get("policy_override", False)),
        )
        if pub.get("verdict") == "WAITING_FOR_OWNER_AUTH":
            store.update_goal_stage(stage["stage_id"], status="WAITING_FOR_OWNER_AUTH", verifier_report=pub)
            store.update_goal(goal["goal_id"], status="WAITING_FOR_OWNER_AUTH", error_summary=str(pub.get("reason") or ""))
            return {"action": "waiting_for_owner_auth", "publish": pub, "goal": store.get_goal(goal["goal_id"])}
        if not pub.get("ok"):
            store.update_goal_stage(stage["stage_id"], status="BLOCKED", verifier_report=pub)
            store.update_goal(goal["goal_id"], status="BLOCKED", error_summary=str(pub.get("error") or pub.get("verdict")))
            return {"action": "publish_blocked", "publish": pub, "goal": store.get_goal(goal["goal_id"])}
        rcpt_id = (pub.get("receipt") or {}).get("receipt_id", "")
        updated = _advance_stage(
            store, store.get_goal(goal["goal_id"]), stage["stage_order"], receipt_id=rcpt_id, score_bp=int(pub.get("score_bp", goal["min_quality_score_bp"]))
        )
        return {"action": "facebook_reels_executed", "publish": pub, "goal": updated}

    if role == "executor:kbm_operator":
        pkg = dict(meta.get("latest_kbm_package") or {})
        chapters = pkg.get("chapters") or []
        ch_title = str(cfg.get("chapter_title") or (chapters[0].get("title") if chapters and isinstance(chapters[0], dict) else goal["title"]))
        ch_body = str(cfg.get("chapter_body") or (chapters[0].get("text") if chapters and isinstance(chapters[0], dict) else ""))
        res = kbm_operator.submit_kbm_chapter(
            store,
            chapter_package=pkg,
            chapter_title=ch_title,
            chapter_body=ch_body,
            task_id=goal["parent_task_id"],
            publish_mode=goal["publish_mode"],
            dry_run=bool(cfg.get("dry_run", False)),
            min_score_bp=goal["min_quality_score_bp"],
            kbm_url=str(cfg.get("kbm_url") or kbm_operator.DEFAULT_KBM_DASHBOARD_URL),
            allowed_hosts=cfg.get("allowed_hosts") or (),
            selectors=cfg.get("selectors"),
            policy_override=bool(cfg.get("policy_override", False)),
        )
        if res.get("verdict") == "WAITING_FOR_OWNER_AUTH":
            store.update_goal_stage(stage["stage_id"], status="WAITING_FOR_OWNER_AUTH", verifier_report=res)
            store.update_goal(goal["goal_id"], status="WAITING_FOR_OWNER_AUTH", error_summary=str(res.get("reason") or ""))
            return {"action": "waiting_for_owner_auth", "kbm": res, "goal": store.get_goal(goal["goal_id"])}
        if not res.get("ok"):
            store.update_goal_stage(stage["stage_id"], status="BLOCKED", verifier_report=res)
            store.update_goal(goal["goal_id"], status="BLOCKED", error_summary=str(res.get("error") or res.get("verdict")))
            return {"action": "kbm_blocked", "kbm": res, "goal": store.get_goal(goal["goal_id"])}
        rcpt_id = (res.get("receipt") or {}).get("receipt_id", "")
        updated = _advance_stage(
            store, store.get_goal(goal["goal_id"]), stage["stage_order"], receipt_id=rcpt_id, score_bp=int(res.get("score_bp", goal["min_quality_score_bp"]))
        )
        return {"action": "kbm_executed", "kbm": res, "goal": updated}

    if role == "executor:git_ops":
        cr = meta.get("latest_code_result") or {}
        receipt_id = str(meta.get("last_receipt_id") or "")
        score_bp = int(meta.get("last_quality_score_bp") or 0)
        targets = cr.get("target_files") or cfg.get("target_files") or ()
        policy = load_host_policy(workspace, repo_root)
        c_res = prepare_branch_and_commit(
            repo_root,
            store,
            task_id=goal["parent_task_id"],
            receipt_id=receipt_id,
            order_id=goal["goal_id"],
            slug=str(cr.get("slug") or goal["title"]),
            target_files=targets,
            commit_message=str(cr.get("commit_message") or goal["title"]),
            score_bp=score_bp,
        )
        if not c_res.get("ok"):
            store.update_goal_stage(stage["stage_id"], status="BLOCKED", verifier_report=c_res)
            store.update_goal(goal["goal_id"], status="BLOCKED", error_summary=str(c_res.get("error") or c_res.get("verdict")))
            return {"action": "git_commit_blocked", "git": c_res, "goal": store.get_goal(goal["goal_id"])}
        out: dict[str, Any] = {"commit": c_res}
        final_rcpt = receipt_id
        if policy.get("git_auto_pr"):
            p_res = push_and_open_pr(
                repo_root,
                store,
                task_id=goal["parent_task_id"],
                receipt_id=receipt_id,
                branch=c_res["branch"],
                title=str(cr.get("pr_title") or goal["title"]),
                body=str(cr.get("pr_body") or goal["user_request"]),
                draft=goal["publish_mode"] == "draft_first",
                score_bp=score_bp,
            )
            out["pr"] = p_res
            if not p_res.get("ok"):
                store.update_goal_stage(stage["stage_id"], status="BLOCKED", verifier_report=out)
                return {"action": "git_pr_blocked", **out, "goal": store.get_goal(goal["goal_id"])}
            final_rcpt = p_res["receipt"]["receipt_id"]
            if policy.get("git_auto_merge") and goal["publish_mode"] == "auto":
                m_res = verify_checks_and_merge_pr(
                    repo_root,
                    store,
                    task_id=goal["parent_task_id"],
                    receipt_id=receipt_id,
                    pr_number=p_res["pr_number"],
                    expected_head_sha=p_res["head_sha"],
                    score_bp=score_bp,
                )
                out["merge"] = m_res
                if m_res.get("ok"):
                    final_rcpt = m_res["receipt"]["receipt_id"]
        updated = _advance_stage(
            store, store.get_goal(goal["goal_id"]), stage["stage_order"], receipt_id=final_rcpt, score_bp=score_bp
        )
        return {"action": "git_ops_executed", **out, "goal": updated}

    # Generic `executor:deliver`
    updated = _advance_stage(
        store,
        goal,
        stage["stage_order"],
        receipt_id=str(meta.get("last_receipt_id") or ""),
        score_bp=int(meta.get("last_quality_score_bp") or goal["min_quality_score_bp"]),
    )
    return {"action": "delivered", "goal": updated}


def tick_goal(
    store: Any,
    memory: Any = None,
    *,
    goal_id: str,
    workspace: Path | None = None,
    repo_root: Path | None = None,
    allow_executors: bool = True,
) -> dict[str, Any]:
    """Advance a Goal DAG by one verified step: verify submitted work order or run ready gate/executor."""
    goal = store.get_goal(goal_id)
    if not goal:
        raise KeyError(f"Goal tidak ditemukan: {goal_id}")
    if goal["status"] in ("COMPLETED", "FAILED"):
        return {"action": "terminal", "status": goal["status"], "goal": goal}

    ws_path = Path(workspace or store.workspace).resolve()
    root_path = Path(repo_root or ws_path).resolve()
    idx = int(goal["current_stage_index"])
    stages = goal["stages"]
    if not 0 <= idx < len(stages):
        return {"action": "invalid_stage_index", "goal": goal}

    stage = stages[idx]
    role = stage["required_role"]

    if role == "ace_gate":
        return _run_ace_gate_stage(store, goal, stage, workspace=ws_path, repo_root=root_path)

    if role.startswith("executor:"):
        if not allow_executors:
            return {"action": "awaiting_executor_opt_in", "stage": stage["name"], "goal": goal}
        return _run_executor_stage(store, goal, stage, workspace=ws_path, repo_root=root_path)

    wo = _ensure_stage_work_order(store, goal, stage)
    assert wo is not None
    if wo["status"] in ("PENDING", "CLAIMED", "REVISION_NEEDED"):
        return {
            "action": "awaiting_agent_submission",
            "stage": stage["name"],
            "work_order_id": wo["work_order_id"],
            "wo_status": wo["status"],
            "assigned_agent": wo.get("assigned_agent", ""),
            "goal": store.get_goal(goal_id),
        }

    if wo["status"] == "SUBMITTED":
        ver = verify_work_order(
            store,
            memory,
            work_order_id=wo["work_order_id"],
            workspace=ws_path,
            repo_root=root_path,
            min_score_bp=goal["min_quality_score_bp"],
        )
        if not ver["passed"]:
            next_wo_status = ver["work_order"]["status"]
            g_status = "FAILED" if next_wo_status == "FAILED" else "ACTIVE"
            store.update_goal(
                goal_id,
                status=g_status,
                error_summary="; ".join(ver["revision_feedback"])[:400],
            )
            return {
                "action": "revision_required" if g_status != "FAILED" else "failed_max_revisions",
                "verification": ver,
                "goal": store.get_goal(goal_id),
            }

        new_meta = _absorb_stage_result_to_goal_meta(
            store,
            goal,
            stage,
            ver["work_order"],
            ver["receipt"]["receipt_id"],
            ver["score_bp"],
        )
        store.update_goal(goal_id, metadata_updates=new_meta)
        refreshed = store.get_goal(goal_id)
        updated_goal = _advance_stage(
            store,
            refreshed,
            idx,
            receipt_id=ver["receipt"]["receipt_id"],
            score_bp=ver["score_bp"],
        )
        return {
            "action": "stage_verified_and_advanced",
            "verification": ver,
            "goal": updated_goal,
        }

    if wo["status"] == "COMPLETED" and wo.get("verification_status") == "VERIFIED":
        rcpt_id = stage.get("execution_receipt_id") or ((wo.get("payload") or {}).get("last_verification") or {}).get("receipt_id", "")
        sc_bp = wo.get("quality_score_bp") or goal["min_quality_score_bp"]
        new_meta = _absorb_stage_result_to_goal_meta(
            store,
            goal,
            stage,
            wo,
            rcpt_id,
            sc_bp,
        )
        store.update_goal(goal_id, metadata_updates=new_meta)
        refreshed = store.get_goal(goal_id)
        updated_goal = _advance_stage(
            store,
            refreshed,
            idx,
            receipt_id=rcpt_id,
            score_bp=sc_bp,
        )
        return {"action": "stage_advanced", "goal": updated_goal}

    return {"action": "no_op", "wo_status": wo["status"], "goal": goal}
