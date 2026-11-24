"""Facebook Reels Publisher Connector for ACE v3.

Aligned with owner directive ("Langsung aja login facebookku" + "Hanya untuk kualitas tinggi"):
1. Strict High-Bar Quality Precheck: refuses upload (`REJECTED_BELOW_BAR`) unless the
   Reels package & rendered 9:16 MP4 pass `evaluate_reels_quality >= min_score_bp`.
2. Primary Transport (`live_browser`): operates through owner's persisted Chrome login
   profile in `vault/browser_profiles/facebook` (Profile Profesional or Halaman),
   halting safely as `WAITING_FOR_OWNER_AUTH` on login/2FA/CAPTCHA checkpoints.
3. Optional Secondary Transport (`meta_graph_api`): supports 3-phase Graph API upload
   & insight fetching when Page ID + Page Access Token exist in SecretVault.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.request import Request, urlopen

from ..git_ops import load_host_policy
from ..quality_gate_engine import DEFAULT_MIN_QUALITY_SCORE_BP, evaluate_reels_quality
from .live_browser import TransportFn, run_browser_workflow
from .vault import SecretVault

DEFAULT_FACEBOOK_REELS_URL = "https://www.facebook.com/reels/create"


def _default_urlopen(req: Request, timeout: int = 30) -> tuple[int, dict[str, Any]]:
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return int(resp.status), json.loads(raw) if raw.strip() else {}


def build_facebook_reels_caption(package: dict[str, Any]) -> str:
    title = str(package.get("title") or "").strip()
    cta = str(package.get("cta") or "").strip()
    facts = [
        str(f.get("text") or "").strip()
        for f in (package.get("facts") or [])
        if isinstance(f, dict) and f.get("approved") and str(f.get("text") or "").strip()
    ]
    tags = [f"#{str(t).lstrip('#').strip()}" for t in (package.get("tags") or []) if str(t).strip()]
    parts: list[str] = []
    if title:
        parts.append(title)
    if facts:
        parts.append("\n".join(facts[:4]))
    if cta:
        parts.append(cta)
    if tags:
        parts.append(" ".join(tags[:15]))
    return "\n\n".join(parts)[:2200]


def publish_reel(
    store: Any,
    *,
    package: dict[str, Any],
    video_path: str | Path,
    task_id: str = "",
    backend: str = "live_browser",
    publish_mode: str = "auto",
    dry_run: bool = False,
    min_score_bp: int | None = None,
    reels_create_url: str = DEFAULT_FACEBOOK_REELS_URL,
    allowed_hosts: Sequence[str] = (),
    headless: bool = True,
    selectors: dict[str, str] | None = None,
    browser_transport: TransportFn | None = None,
    http_opener: Callable[..., tuple[int, dict[str, Any]]] | None = None,
    graph_api_base: str = "https://graph.facebook.com/v21.0",
    policy_override: bool = False,
) -> dict[str, Any]:
    """Verify high-bar quality & publish (or draft) a 9:16 video to Facebook Reels."""
    policy = load_host_policy(store.workspace)
    threshold_bp = int(min_score_bp if min_score_bp is not None else policy.get("min_quality_score_bp", DEFAULT_MIN_QUALITY_SCORE_BP))

    mp4 = Path(video_path).resolve()
    eval_pkg = {**package, "video_path": str(mp4)}
    qv = evaluate_reels_quality(eval_pkg, min_score_bp=threshold_bp, require_rendered_mp4=True)
    if not qv["passed"]:
        return {
            "ok": False,
            "published": False,
            "verdict": "REJECTED_BELOW_BAR",
            "score_bp": qv["score_bp"],
            "min_score_bp": threshold_bp,
            "revision_feedback": qv["revision_feedback"],
            "quality": qv,
        }

    vault = SecretVault(store.workspace)
    fb_status = vault.venue_status("facebook")
    caption = build_facebook_reels_caption(package)

    if dry_run:
        return {
            "ok": True,
            "published": False,
            "verdict": "PREFLIGHT_DRY_RUN_READY",
            "score_bp": qv["score_bp"],
            "backend": backend,
            "publish_mode": publish_mode,
            "caption_preview": caption,
            "video_path": str(mp4),
            "vault_status": fb_status,
            "quality": qv,
        }

    if not policy_override and not policy.get("allow_live_facebook_publish"):
        return {
            "ok": False,
            "published": False,
            "verdict": "POLICY_DISABLED",
            "score_bp": qv["score_bp"],
            "error": "Upload live Facebook belum diaktifkan di .ace_policy.json (`allow_live_facebook_publish: true`). Gunakan dry_run=True atau aktifkan policy.",
            "quality": qv,
        }

    chosen = backend.strip().lower()
    if chosen == "auto":
        chosen = "live_browser" if (fb_status["browser_session_present"] or not fb_status["has_api_credentials"]) else "meta_graph_api"

    if chosen == "live_browser":
        sel = {
            "file_input": 'input[type="file"][accept*="video"], input[type="file"]',
            "next_button": '[aria-label="Berikutnya"], [aria-label="Next"], [data-testid="reels_next_btn"]',
            "caption_input": 'textarea[name="description"], [aria-label*="Deskripsikan"], [aria-label*="Describe your reel"], [contenteditable="true"][role="textbox"]',
            "publish_button": '[aria-label="Bagikan"], [aria-label="Share"], [aria-label="Terbitkan"], [aria-label="Publish"], [data-testid="reels_publish_btn"]',
            "draft_button": '[aria-label="Simpan draf"], [aria-label="Save draft"], [data-testid="reels_draft_btn"]',
            "result_marker": '[data-testid="reels_published_banner"], [role="status"], body',
            **(selectors or {}),
        }
        submit_sel = sel["draft_button"] if publish_mode == "draft_first" else sel["publish_button"]
        steps: list[dict[str, Any]] = [
            {"id": "open_reels_composer", "op": "navigate", "url": reels_create_url, "stop_on_auth": True},
            {"id": "wait_file_input", "op": "wait_selector", "selector": sel["file_input"]},
            {"id": "upload_mp4", "op": "upload_file", "selector": sel["file_input"], "file_path": str(mp4)},
        ]
        if sel.get("next_button"):
            steps.append({
                "id": "click_next_optional",
                "op": "click_if_present",
                "selector": sel["next_button"],
                "timeout_ms": 600 if not (selectors and "next_button" in selectors) else 5000,
            })
        steps.extend([
            {"id": "wait_caption", "op": "wait_selector", "selector": sel["caption_input"]},
            {"id": "fill_caption", "op": "fill", "selector": sel["caption_input"], "value": caption},
            {"id": "click_submit", "op": "click", "selector": submit_sel},
            {"id": "verify_result", "op": "read_text", "selector": sel["result_marker"]},
            {"id": "proof_shot", "op": "screenshot", "filename": "fb_reels_submission_proof.png"},
        ])
        bres = run_browser_workflow(
            store,
            venue="facebook",
            steps=steps,
            allowed_hosts=allowed_hosts,
            headless=headless,
            task_id=task_id,
            transport=browser_transport,
        )
        if bres["status"] == "WAITING_FOR_OWNER_AUTH":
            return {
                "ok": False,
                "published": False,
                "verdict": "WAITING_FOR_OWNER_AUTH",
                "reason": bres["reason"],
                "profile_dir": bres["profile_dir"],
                "score_bp": qv["score_bp"],
                "browser": bres,
            }
        return {
            "ok": bres["ok"],
            "published": bres["ok"] and publish_mode == "auto",
            "draft_saved": bres["ok"] and publish_mode == "draft_first",
            "verdict": "PUBLISHED" if (bres["ok"] and publish_mode == "auto") else ("DRAFT_SAVED" if bres["ok"] else "UPLOAD_FAILED"),
            "backend": "live_browser",
            "score_bp": qv["score_bp"],
            "receipt": bres.get("receipt"),
            "browser": bres,
            "quality": qv,
        }

    if chosen == "meta_graph_api":
        creds = vault.get_venue_credentials("facebook")
        page_id = str(creds.get("page_id") or "").strip()
        token = str(creds.get("page_access_token") or "").strip()
        if not page_id or not token:
            return {
                "ok": False,
                "published": False,
                "verdict": "MISSING_CREDENTIALS",
                "error": "Meta Graph API memerlukan `page_id` & `page_access_token` di SecretVault.",
            }
        opener = http_opener or _default_urlopen
        base = graph_api_base.rstrip("/")

        # Phase 1: start upload session
        start_req = Request(
            f"{base}/{page_id}/video_reels",
            data=json.dumps({"upload_phase": "start", "access_token": token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _, start_data = opener(start_req, timeout=30)
        video_id = str(start_data.get("video_id") or "")
        upload_url = str(start_data.get("upload_url") or "")
        if not video_id or not upload_url:
            return {"ok": False, "published": False, "verdict": "GRAPH_START_FAILED", "response": start_data}

        # Phase 2: binary upload
        video_bytes = mp4.read_bytes()
        up_req = Request(
            upload_url,
            data=video_bytes,
            headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(len(video_bytes)),
                "Content-Type": "application/octet-stream",
            },
            method="POST",
        )
        _, up_data = opener(up_req, timeout=120)

        # Phase 3: finish
        video_state = "DRAFT" if publish_mode == "draft_first" else "PUBLISHED"
        fin_req = Request(
            f"{base}/{page_id}/video_reels",
            data=json.dumps({
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": video_state,
                "description": caption,
                "access_token": token,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _, fin_data = opener(fin_req, timeout=30)
        success = bool(fin_data.get("success", True))
        rcpt = store.record_receipt(
            task_id=task_id or "fb_reels",
            action_kind="facebook_reels_graph_upload",
            input_data=json.dumps({"page_id": page_id, "video_sha256": qv["checks"]["mp4_probe"]}),
            output_data=json.dumps({"video_id": video_id, "video_state": video_state, "finish": fin_data}),
            command_or_operation=f"graph_api:{page_id}/video_reels",
            exit_code=0 if success else 1,
            stdout_text=f"video_id={video_id}",
            verified_by="ace-facebook-reels",
            passed=success,
        )
        return {
            "ok": success,
            "published": success and video_state == "PUBLISHED",
            "draft_saved": success and video_state == "DRAFT",
            "verdict": video_state if success else "GRAPH_FINISH_FAILED",
            "backend": "meta_graph_api",
            "video_id": video_id,
            "score_bp": qv["score_bp"],
            "upload_response": up_data,
            "finish_response": fin_data,
            "receipt": rcpt,
            "quality": qv,
        }

    raise ValueError(f"Backend Facebook Reels tidak dikenal: {backend!r}")
