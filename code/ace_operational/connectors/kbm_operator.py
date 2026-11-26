"""KBM Apps Account Operator & Quality-Gated Publishing Suite for ACE v3.

Unifies:
- `tools.kbm_titles` & `tools.kbm_schedule` (portfolio planning & pacing)
- `tools.kbm_qc`, `tools.arc_rubric`, `tools.cover_check`, `tools.kbm_produce`
- `tools.royalty_track` (Decimal royalty ledger + Pasal 7 author share calculation)
- `live_browser` with owner's KBM browser profile vault (`vault/browser_profiles/kbm`)
  and `WAITING_FOR_OWNER_AUTH` stop-gate.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools import kbm_produce, kbm_schedule, kbm_titles, royalty_track

from ..git_ops import load_host_policy
from ..quality_gate_engine import DEFAULT_MIN_QUALITY_SCORE_BP, evaluate_kbm_quality
from .live_browser import TransportFn, run_browser_workflow

DEFAULT_KBM_DASHBOARD_URL = "https://kbm.id/author/chapters/new"


def audit_kbm_catalog(
    catalog_path: str | Path,
    *,
    as_of_date: str | None = None,
    default_weekly_target: int = 3,
) -> dict[str, Any]:
    """Run KBM portfolio title report + deterministic release pacing schedule."""
    cat = Path(catalog_path).resolve()
    titles = kbm_titles.build_report(cat)
    schedule = kbm_schedule.build_schedule(
        cat,
        as_of_date=as_of_date,
        default_weekly_target=default_weekly_target,
    )
    return {
        "schema": "ace.kbm_portfolio_audit.v1",
        "titles": titles,
        "schedule": schedule,
    }


def summarize_kbm_royalties(
    csv_paths: Sequence[str | Path],
    *,
    map_path: str | Path | None = None,
) -> dict[str, Any]:
    """Parse KBM CSV royalty sheets and calculate Pasal 7 cumulative author revenue share."""
    col_map = royalty_track.load_column_map(Path(map_path) if map_path else None)
    summary = royalty_track.summarize_royalties([Path(p) for p in csv_paths], column_map=col_map)
    return summary


def run_kbm_production_bundle(
    *,
    materials: str | Path,
    manuscript: str | Path,
    cover: str | Path,
    bundle_dir: str | Path,
    royalty_paths: Sequence[str | Path],
    title_config: str | Path | None = None,
    expected_chapters: int = 30,
    min_words: int = 1000,
    min_score_bp: int = DEFAULT_MIN_QUALITY_SCORE_BP,
) -> dict[str, Any]:
    """Run KBM arc_rubric + kbm_qc + kbm_produce bundling, rejecting bundles below high-bar score."""
    cfg_dict = None
    if title_config and Path(title_config).is_file():
        cfg_dict = json.loads(Path(title_config).read_text(encoding="utf-8"))
    qv = evaluate_kbm_quality(
        {
            "manuscript_path": str(manuscript),
            "title_config": cfg_dict or {"characters": ["Tokoh"]},
            "cover_path": str(cover),
            "min_words": min_words,
        },
        min_score_bp=min_score_bp,
        min_words_per_chapter=min_words,
    )
    if not qv["passed"]:
        return {
            "ok": False,
            "verdict": "REJECTED_BELOW_BAR",
            "score_bp": qv["score_bp"],
            "revision_feedback": qv["revision_feedback"],
            "quality": qv,
        }
    prod = kbm_produce.run_production(
        materials=Path(materials),
        manuscript=Path(manuscript),
        cover=Path(cover),
        bundle_dir=Path(bundle_dir),
        royalty_paths=[Path(p) for p in royalty_paths],
        title_config=Path(title_config) if title_config else None,
        expected_chapters=expected_chapters,
        min_words=min_words,
    )
    return {
        "ok": bool(prod.get("passed")),
        "verdict": "PACKAGED" if prod.get("passed") else "PRODUCE_FAILED",
        "score_bp": qv["score_bp"],
        "quality": qv,
        "production": prod,
    }


def submit_kbm_chapter(
    store: Any,
    *,
    chapter_package: dict[str, Any],
    chapter_title: str,
    chapter_body: str,
    task_id: str = "",
    publish_mode: str = "auto",
    dry_run: bool = False,
    min_score_bp: int | None = None,
    kbm_url: str = DEFAULT_KBM_DASHBOARD_URL,
    allowed_hosts: Sequence[str] = (),
    headless: bool = True,
    selectors: dict[str, str] | None = None,
    browser_transport: TransportFn | None = None,
    policy_override: bool = False,
) -> dict[str, Any]:
    """Verify KBM chapter passes high-bar arc_rubric + kbm_qc, then draft/publish via KBM browser session."""
    policy = load_host_policy(store.workspace)
    threshold_bp = int(min_score_bp if min_score_bp is not None else policy.get("min_quality_score_bp", DEFAULT_MIN_QUALITY_SCORE_BP))

    qv = evaluate_kbm_quality(chapter_package, min_score_bp=threshold_bp)
    if not qv["passed"]:
        return {
            "ok": False,
            "submitted": False,
            "verdict": "REJECTED_BELOW_BAR",
            "score_bp": qv["score_bp"],
            "min_score_bp": threshold_bp,
            "revision_feedback": qv["revision_feedback"],
            "quality": qv,
        }

    if dry_run:
        return {
            "ok": True,
            "submitted": False,
            "verdict": "PREFLIGHT_DRY_RUN_READY",
            "score_bp": qv["score_bp"],
            "chapter_title": chapter_title,
            "publish_mode": publish_mode,
            "quality": qv,
        }

    if not policy_override and not policy.get("allow_live_kbm_actions"):
        return {
            "ok": False,
            "submitted": False,
            "verdict": "POLICY_DISABLED",
            "score_bp": qv["score_bp"],
            "error": "Aksi live KBM belum diaktifkan di .ace_policy.json (`allow_live_kbm_actions: true`).",
            "quality": qv,
        }

    sel = {
        "title_input": 'input[name="title"], [data-testid="kbm_chapter_title"]',
        "body_input": 'textarea[name="content"], [contenteditable="true"], [data-testid="kbm_chapter_body"]',
        "publish_button": '[data-testid="kbm_publish_btn"], button[type="submit"]',
        "draft_button": '[data-testid="kbm_draft_btn"], button[data-action="draft"]',
        "result_marker": '[data-testid="kbm_status"], [role="status"], body',
        **(selectors or {}),
    }
    btn = sel["draft_button"] if publish_mode == "draft_first" else sel["publish_button"]
    steps = [
        {"id": "open_kbm_editor", "op": "navigate", "url": kbm_url, "stop_on_auth": True},
        {"id": "wait_title", "op": "wait_selector", "selector": sel["title_input"]},
        {"id": "fill_title", "op": "fill", "selector": sel["title_input"], "value": chapter_title},
        {"id": "fill_body", "op": "fill", "selector": sel["body_input"], "value": chapter_body},
        {"id": "submit_chapter", "op": "click", "selector": btn},
        {"id": "read_status", "op": "read_text", "selector": sel["result_marker"]},
        {"id": "kbm_proof_shot", "op": "screenshot", "filename": "kbm_submission_proof.png"},
    ]
    bres = run_browser_workflow(
        store,
        venue="kbm",
        steps=steps,
        allowed_hosts=allowed_hosts,
        headless=headless,
        task_id=task_id,
        transport=browser_transport,
    )
    if bres["status"] == "WAITING_FOR_OWNER_AUTH":
        return {
            "ok": False,
            "submitted": False,
            "verdict": "WAITING_FOR_OWNER_AUTH",
            "reason": bres["reason"],
            "profile_dir": bres["profile_dir"],
            "score_bp": qv["score_bp"],
            "browser": bres,
        }
    return {
        "ok": bres["ok"],
        "submitted": bres["ok"],
        "verdict": "PUBLISHED" if (bres["ok"] and publish_mode == "auto") else ("DRAFT_SAVED" if bres["ok"] else "KBM_SUBMIT_FAILED"),
        "score_bp": qv["score_bp"],
        "receipt": bres.get("receipt"),
        "browser": bres,
        "quality": qv,
    }
