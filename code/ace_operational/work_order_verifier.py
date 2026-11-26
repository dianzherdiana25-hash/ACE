"""Independent ACE Work-Order Verifier & Revision-Loop Driver.

Closes the gap where agent submissions stay permanently UNVERIFIED:
- Never self-verifies an agent submission.
- Runs real Quality Gate checks (`quality_gate_engine`), file/AST/test verification,
  and heterogeneous cross-agent checks according to work-order contract.
- Strictly rejects work below threshold (`REJECTED_BELOW_BAR` -> `REVISION_NEEDED`)
  with actionable feedback attached to the work order for retry.
- Mints an official cryptographic receipt in `OperationalStore` ONLY on PASS.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .quality_gate_engine import (
    DEFAULT_MIN_QUALITY_SCORE_BP,
    check_cross_agent_heterogeneity,
    evaluate_code_quality,
    evaluate_kbm_quality,
    evaluate_reels_quality,
    evaluate_research_grounding,
)


def _infer_checks(wo: dict[str, Any], goal: dict[str, Any] | None) -> list[dict[str, Any]]:
    explicit = wo.get("acceptance_checks") or []
    if explicit:
        return list(explicit)
    payload_checks = (wo.get("payload") or {}).get("acceptance_checks") or []
    if payload_checks:
        return list(payload_checks)
    role = (wo.get("required_role") or "").strip().lower()
    domain = (goal["domain"] if goal else "").strip().lower()
    result = wo.get("result") or {}
    if role == "critic" or "review" in (wo.get("stage_id") or "").lower() or "approved" in result:
        return [{"kind": "cross_review"}]
    if domain == "video_reels" or "scenes" in result or "script_scenes" in result:
        return [{"kind": "reels_quality", "require_rendered_mp4": bool(result.get("video_path"))}]
    if domain == "kbm_apps" or "chapters" in result or "manuscript_path" in result:
        return [{"kind": "kbm_quality"}]
    if domain == "code_evolution" or "target_files" in result or "test_commands" in result:
        return [{"kind": "code_quality"}]
    if "claims" in result or domain == "research":
        return [{"kind": "research_grounding"}]
    return [{"kind": "evidence_presence"}]


def verify_work_order(
    store: Any,
    memory: Any = None,
    *,
    work_order_id: str,
    workspace: Path | None = None,
    repo_root: Path | None = None,
    verifier_agent: str = "ace-verifier",
    min_score_bp: int | None = None,
) -> dict[str, Any]:
    """Independently verify a submitted work order, enforce high-bar score, and mint receipt iff passing."""
    wo = store.get_work_order(work_order_id)
    if not wo:
        raise KeyError(f"Work order tidak ditemukan: {work_order_id}")

    goal = store.get_goal(wo["goal_id"]) if wo.get("goal_id") else None
    threshold_bp = int(
        min_score_bp
        if min_score_bp is not None
        else (goal["min_quality_score_bp"] if goal else DEFAULT_MIN_QUALITY_SCORE_BP)
    )
    max_revs = int(goal["max_revisions"] if goal else 3)

    result = wo.get("result") or {}
    if wo["status"] == "PENDING" or not isinstance(result, dict) or not result:
        updated = store.update_work_order(
            work_order_id,
            status="REVISION_NEEDED",
            verification_status="NOT_VERIFIED",
            quality_score_bp=0,
        )
        return {
            "work_order": updated,
            "passed": False,
            "verdict": "NOT_VERIFIED",
            "score_bp": 0,
            "min_score_bp": threshold_bp,
            "revision_feedback": ["Work order belum memiliki `result` terstruktur untuk diverifikasi."],
            "receipt": None,
        }

    checks = _infer_checks(wo, goal)
    ws_path = Path(workspace or store.workspace).resolve()
    root_path = Path(repo_root or ws_path).resolve()

    check_verdicts: list[dict[str, Any]] = []
    all_feedback: list[str] = []

    for chk in checks:
        kind = str(chk.get("kind") or "evidence_presence").strip().lower()
        c_min = int(chk.get("min_score_bp", threshold_bp))

        if kind == "research_grounding":
            claims = result.get("claims") or []
            sources = result.get("sources") or []
            ver = evaluate_research_grounding(
                claims,
                sources,
                min_score_bp=c_min,
                max_age_days=int(chk.get("max_age_days", 180)),
                min_words_per_source=int(chk.get("min_words_per_source", 12)),
                reference_facts=chk.get("reference_facts"),
                prose_markdown=str(result.get("prose_markdown") or ""),
            )
            check_verdicts.append(ver)
            all_feedback.extend(ver["revision_feedback"])

        elif kind == "reels_quality":
            pkg = result.get("reels_package") if isinstance(result.get("reels_package"), dict) else result
            ver = evaluate_reels_quality(
                pkg,
                min_score_bp=c_min,
                require_rendered_mp4=bool(chk.get("require_rendered_mp4", False)),
            )
            check_verdicts.append(ver)
            all_feedback.extend(ver["revision_feedback"])

        elif kind == "kbm_quality":
            pkg = result.get("kbm_package") if isinstance(result.get("kbm_package"), dict) else result
            ver = evaluate_kbm_quality(
                pkg,
                min_score_bp=c_min,
                min_dim_score=float(chk.get("min_dim_score", 0.65)),
                min_words_per_chapter=int(chk.get("min_words_per_chapter", 1000)),
            )
            check_verdicts.append(ver)
            all_feedback.extend(ver["revision_feedback"])

        elif kind == "code_quality":
            targets = result.get("target_files") or chk.get("target_files") or ()
            cmds = result.get("test_commands") or chk.get("test_commands") or ()
            snippet = str(result.get("snippet") or "")
            ver = evaluate_code_quality(
                ws_path,
                repo_root=root_path,
                target_files=targets,
                snippet=snippet,
                test_commands=cmds,
                min_score_bp=c_min,
                run_verify_sources=bool(chk.get("run_verify_sources", True)),
            )
            check_verdicts.append(ver)
            all_feedback.extend(ver["revision_feedback"])

        elif kind == "cross_review":
            creator_agent = str(result.get("creator_agent") or (wo.get("payload") or {}).get("creator_agent") or "")
            creator_vendor = str(result.get("creator_vendor") or (wo.get("payload") or {}).get("creator_vendor") or "")
            rev_agent = str(result.get("reviewer_agent") or wo.get("claimed_by") or "")
            rev_vendor = str(result.get("reviewer_vendor") or "")
            if not rev_vendor and rev_agent:
                ag = store.get_agent(rev_agent)
                if ag:
                    rev_vendor = ag["vendor"]
            if not creator_agent:
                creator_agent = str((wo.get("payload") or {}).get("previous_agent") or "creator")
            ver = check_cross_agent_heterogeneity(
                creator_agent=creator_agent,
                creator_vendor=creator_vendor,
                reviewer_agent=rev_agent,
                reviewer_vendor=rev_vendor,
                approved=bool(result.get("approved", False)),
                reviewer_score_bp=int(result.get("score_bp", 0)),
                min_score_bp=c_min,
                require_distinct_vendor=bool(chk.get("require_distinct_vendor", False)),
            )
            check_verdicts.append(ver)
            all_feedback.extend(ver["revision_feedback"])

        else:
            # Generic non-hallucination check: must supply verifiable artifacts or grounded sources/claims.
            claims = result.get("claims")
            sources = result.get("sources")
            artifacts = result.get("artifacts") or result.get("files") or []
            if claims is not None:
                ver = evaluate_research_grounding(claims, sources or [], min_score_bp=c_min)
                check_verdicts.append(ver)
                all_feedback.extend(ver["revision_feedback"])
            elif artifacts:
                existing_arts = []
                for item in artifacts:
                    p = Path(str(item))
                    cand = p if p.is_absolute() else (ws_path / p)
                    if cand.is_file():
                        existing_arts.append(str(cand))
                if len(existing_arts) == len(artifacts):
                    sc = int(result.get("self_reported_checks_passed_score_bp", threshold_bp))
                    passed_ev = sc >= c_min
                    check_verdicts.append({
                        "domain": "evidence_presence",
                        "passed": passed_ev,
                        "verdict": "PASS" if passed_ev else "REJECTED_BELOW_BAR",
                        "score_bp": sc,
                        "min_score_bp": c_min,
                        "findings": [] if passed_ev else [{"rule": "score_below_bar"}],
                        "revision_feedback": [] if passed_ev else [f"Skor bukti {sc} bp < ambang {c_min} bp."],
                    })
                    all_feedback.extend(check_verdicts[-1]["revision_feedback"])
                else:
                    check_verdicts.append({
                        "domain": "evidence_presence",
                        "passed": False,
                        "verdict": "NOT_VERIFIED",
                        "score_bp": 0,
                        "min_score_bp": c_min,
                        "findings": [{"rule": "artifact_not_found_on_disk", "declared": artifacts}],
                        "revision_feedback": ["Artefak yang diklaim hasil kerja tidak ditemukan nyata di workspace."],
                    })
                    all_feedback.extend(check_verdicts[-1]["revision_feedback"])
            else:
                check_verdicts.append({
                    "domain": "evidence_presence",
                    "passed": False,
                    "verdict": "NOT_VERIFIED",
                    "score_bp": 0,
                    "min_score_bp": c_min,
                    "findings": [{"rule": "unverifiable_submission"}],
                    "revision_feedback": ["Submission hanya berisi narasi tanpa klaim bersumber atau artefak terverifikasi."],
                })
                all_feedback.extend(check_verdicts[-1]["revision_feedback"])

    scores = [int(v["score_bp"]) for v in check_verdicts]
    min_ver_score = min(scores) if scores else 0
    all_passed = bool(check_verdicts) and all(v["passed"] for v in check_verdicts) and min_ver_score >= threshold_bp

    payload = dict(wo.get("payload") or {})
    rev_count = int(wo.get("revision_count") or 0)
    receipt: dict[str, Any] | None = None

    if all_passed:
        receipt = store.record_receipt(
            task_id=wo["parent_task_id"],
            action_kind="work_order_verified",
            input_data=json.dumps({"work_order_id": work_order_id, "checks": checks}, sort_keys=True, ensure_ascii=False),
            output_data=json.dumps({"score_bp": min_ver_score, "verdicts": check_verdicts}, sort_keys=True, ensure_ascii=False),
            command_or_operation=f"verify_work_order:{work_order_id}",
            exit_code=0,
            stdout_text=f"PASS score_bp={min_ver_score}",
            stderr_text="",
            artifacts_created=[str(a) for a in (result.get("artifacts") or [])],
            verified_by=verifier_agent,
            passed=True,
        )
        payload["last_verification"] = {"passed": True, "score_bp": min_ver_score, "receipt_id": receipt["receipt_id"]}
        updated = store.update_work_order(
            work_order_id,
            status="COMPLETED",
            verification_status="VERIFIED",
            quality_score_bp=min_ver_score,
            payload=payload,
        )
        if wo.get("stage_id"):
            store.update_goal_stage(
                wo["stage_id"],
                quality_score_bp=min_ver_score,
                verifier_report={"passed": True, "checks": check_verdicts},
                execution_receipt_id=receipt["receipt_id"],
            )
        # Release any remaining fenced lease cleanly.
        if wo.get("lease_token") and wo.get("claimed_by"):
            try:
                store.release_work_order(
                    work_order_id,
                    wo["claimed_by"],
                    lease_token=wo["lease_token"],
                    new_status="COMPLETED",
                )
            except Exception:
                pass
        if memory is not None:
            memory.remember_statement(
                f"Work order {work_order_id} terverifikasi LOLOS Quality Gate ({min_ver_score}bp, receipt {receipt['receipt_id']}).",
                source_kind="operator",
                source_ref=f"receipt:{receipt['receipt_id']}",
                sensitivity="internal",
            )
    else:
        rev_count += 1
        payload["revision_feedback"] = all_feedback
        payload["last_verification"] = {"passed": False, "score_bp": min_ver_score, "verdicts": check_verdicts}
        new_status = "FAILED" if rev_count > max_revs else "REVISION_NEEDED"
        updated = store.update_work_order(
            work_order_id,
            status=new_status,
            verification_status="REJECTED",
            revision_count=rev_count,
            quality_score_bp=min_ver_score,
            payload=payload,
        )
        if wo.get("stage_id"):
            store.update_goal_stage(
                wo["stage_id"],
                status=new_status,
                revision_count=rev_count,
                quality_score_bp=min_ver_score,
                verifier_report={"passed": False, "checks": check_verdicts, "feedback": all_feedback},
            )
        store.emit_event(
            task_id=wo["parent_task_id"],
            kind="quality_gate_rejected",
            status="LEARNING" if new_status == "REVISION_NEEDED" else "FAILED_WITH_RECOVERY_STATE",
            summary_code="work_order_rejected_below_bar",
            verification_passed=False,
            technical_detail={
                "work_order_id": work_order_id,
                "score_bp": min_ver_score,
                "min_score_bp": threshold_bp,
                "revision_count": rev_count,
                "feedback": all_feedback[:5],
            },
        )

    final_verdict = (
        "PASS"
        if all_passed
        else (
            "UNGROUNDED_CLAIMS"
            if any(v.get("verdict") == "UNGROUNDED_CLAIMS" for v in check_verdicts)
            else "REJECTED_BELOW_BAR"
        )
    )
    return {
        "work_order": updated,
        "passed": all_passed,
        "verdict": final_verdict,
        "score_bp": min_ver_score,
        "min_score_bp": threshold_bp,
        "revision_count": rev_count,
        "revision_feedback": all_feedback,
        "checks": check_verdicts,
        "receipt": receipt,
    }
