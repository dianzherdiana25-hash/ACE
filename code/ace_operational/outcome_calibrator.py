"""Post-Publish & Post-Execution Outcome Calibration for ACE v3.

Compares predicted Quality Gate scores against actual real-world performance
(Reels views/completion, KBM reads/royalties via Pasal 7, GitHub CI/merge status),
updates `OperationalStore.record_skill_outcome`, and records verified memory episodes.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.royalty_track import pasal7_author_share


def compute_actual_score_bp(domain: str, actual_metrics: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Compute a deterministic 0..10000 actual outcome score without fabricating uncollected metrics."""
    dom = str(domain or "general").strip().lower()
    details: dict[str, Any] = {}

    if dom == "video_reels":
        views = max(0, int(actual_metrics.get("views", 0) or 0))
        completion_rate = float(actual_metrics.get("completion_rate", 0.0) or 0.0)
        avg_watch_sec = float(actual_metrics.get("avg_watch_sec", 0.0) or 0.0)
        target_sec = max(5.0, float(actual_metrics.get("duration_sec", 15.0) or 15.0))
        engagement = int(actual_metrics.get("likes", 0) or 0) + 2 * int(actual_metrics.get("shares", 0) or 0) + int(actual_metrics.get("comments", 0) or 0)

        watch_ratio = min(1.0, avg_watch_sec / target_sec) if avg_watch_sec > 0 else min(1.0, completion_rate)
        completion_norm = min(1.0, completion_rate if completion_rate <= 1.0 else completion_rate / 100.0)
        engagement_rate = min(1.0, (engagement / max(1, views)) * 10.0) if views > 0 else 0.0
        reach_norm = min(1.0, views / 10000.0) if views > 0 else 0.0
        score = round(10000 * (0.45 * max(watch_ratio, completion_norm) + 0.30 * engagement_rate + 0.25 * reach_norm))
        details["watch_ratio"] = round(watch_ratio, 4)
        details["engagement_rate_scaled"] = round(engagement_rate, 4)
        return max(0, min(10000, score)), details

    if dom == "kbm_apps":
        reads = max(0, int(actual_metrics.get("reads", 0) or 0))
        coins = max(0, int(actual_metrics.get("coins_earned", 0) or 0))
        omzet_raw = actual_metrics.get("omzet_idr", 0)
        omzet_dec = Decimal(str(omzet_raw or 0))
        pasal7 = pasal7_author_share(omzet_dec) if omzet_dec >= 0 else None
        if pasal7:
            details["pasal7_author_share"] = pasal7
        rating = float(actual_metrics.get("rating", 0.0) or 0.0)
        read_norm = min(1.0, reads / 5000.0) if reads > 0 else 0.0
        rev_norm = min(1.0, (float(omzet_dec) / 250000.0) if omzet_dec > 0 else (coins / 500.0))
        rating_norm = min(1.0, rating / 5.0) if rating > 0 else 0.5
        score = round(10000 * (0.40 * read_norm + 0.40 * rev_norm + 0.20 * rating_norm))
        return max(0, min(10000, score)), details

    if dom == "code_evolution":
        ci_passed = bool(actual_metrics.get("ci_passed", False))
        merged = bool(actual_metrics.get("merged", False))
        reverted = bool(actual_metrics.get("reverted", False))
        if reverted:
            return 0, {"reverted": True}
        score = (6000 if ci_passed else 0) + (4000 if merged else 0)
        return score, {"ci_passed": ci_passed, "merged": merged}

    # Generic outcome score.
    if "score_bp" in actual_metrics:
        return max(0, min(10000, int(actual_metrics["score_bp"]))), details
    return (10000 if actual_metrics.get("success") else 2500), details


def record_real_outcome(
    store: Any,
    memory: Any = None,
    *,
    goal_id: str,
    stage_id: str = "",
    domain: str = "",
    asset_ref: str = "",
    predicted_score_bp: int | None = None,
    actual_metrics: dict[str, Any],
    skill_ids: Sequence[str] = (),
    min_success_score_bp: int = 7000,
) -> dict[str, Any]:
    """Persist real-world outcome, update skill reliability, and record calibration memory."""
    goal = store.get_goal(goal_id) if goal_id else None
    eff_domain = domain or (goal["domain"] if goal else "general")
    if predicted_score_bp is None and goal is not None:
        scored_stages = [s["quality_score_bp"] for s in goal["stages"] if s.get("quality_score_bp")]
        predicted_score_bp = scored_stages[-1] if scored_stages else goal["min_quality_score_bp"]
    pred_bp = int(predicted_score_bp if predicted_score_bp is not None else 8500)

    actual_bp, computed_details = compute_actual_score_bp(eff_domain, actual_metrics)
    enriched_metrics = {**actual_metrics, "computed": computed_details}
    record = store.record_outcome_metric(
        goal_id=goal_id,
        stage_id=stage_id,
        domain=eff_domain,
        asset_ref=asset_ref,
        predicted_score_bp=pred_bp,
        actual_metrics=enriched_metrics,
        actual_score_bp=actual_bp,
        skill_ids=list(skill_ids),
    )

    success = actual_bp >= int(min_success_score_bp)
    negative_transfer = bool(actual_metrics.get("reverted")) or (pred_bp >= 8500 and actual_bp < 4000)
    skill_updates: list[dict[str, Any]] = []
    for sid in skill_ids:
        try:
            sk = store.record_skill_outcome(sid, success=success, negative_transfer=negative_transfer)
            skill_updates.append({"skill_id": sid, "status": sk["status"], "success_count": sk["success_count"], "failure_count": sk["failure_count"]})
        except KeyError:
            pass

    if memory is not None:
        memory.remember_statement(
            f"Kalibrasi outcome domain {eff_domain} (goal {goal_id}): prediksi {pred_bp}bp, aktual {actual_bp}bp, delta {record['calibration_delta_bp']:+d}bp.",
            source_kind="operator",
            source_ref=f"outcome:{record['outcome_id']}",
            sensitivity="internal",
        )

    store.emit_event(
        task_id=goal["parent_task_id"] if goal else goal_id,
        kind="outcome_calibrated",
        status="COMPLETED" if success else "ACTIVE",
        summary_code="outcome_calibrated",
        verification_passed=success,
        technical_detail={
            "goal_id": goal_id,
            "domain": eff_domain,
            "predicted_score_bp": pred_bp,
            "actual_score_bp": actual_bp,
            "calibration_delta_bp": record["calibration_delta_bp"],
            "skill_updates": skill_updates,
        },
    )

    return {
        "outcome": record,
        "success": success,
        "negative_transfer": negative_transfer,
        "skill_updates": skill_updates,
    }


def calibration_report(store: Any, *, domain: str | None = None) -> dict[str, Any]:
    """Summarize prediction error and empirical calibration across recorded real outcomes."""
    rows = store.list_outcomes(domain=domain, limit=200)
    if not rows:
        return {
            "schema": "ace.calibration_report.v1",
            "domain": domain or "all",
            "count": 0,
            "mean_predicted_bp": 0,
            "mean_actual_bp": 0,
            "mean_bias_bp": 0,
            "mae_bp": 0,
            "outcomes": [],
        }
    n = len(rows)
    mean_pred = round(sum(r["predicted_score_bp"] for r in rows) / n)
    mean_act = round(sum(r["actual_score_bp"] for r in rows) / n)
    mean_bias = round(sum(r["calibration_delta_bp"] for r in rows) / n)
    mae = round(sum(abs(r["calibration_delta_bp"]) for r in rows) / n)
    return {
        "schema": "ace.calibration_report.v1",
        "domain": domain or "all",
        "count": n,
        "mean_predicted_bp": mean_pred,
        "mean_actual_bp": mean_act,
        "mean_bias_bp": mean_bias,
        "mae_bp": mae,
        "outcomes": rows[:25],
    }
