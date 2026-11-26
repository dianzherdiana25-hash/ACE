"""Live Chromium Browser Operator backed by SecretVault session profiles.

Separates production browser workflows (Facebook login/Reels upload, KBM Apps)
from the strict `127.0.0.1` test-fixture runtime (`ace_web_operator/browser_engine.py`),
while preserving ironclad safeguards:
1. Per-venue domain allowlist enforced both pre-launch and inside CDP Fetch interception.
2. Persistent per-venue Chromium `userDataDir` inside `<workspace>/vault/browser_profiles/`.
3. Automatic CAPTCHA / 2FA / Login checkpoint detection -> immediately halts with
   `status="WAITING_FOR_OWNER_AUTH"` and screenshot proof (never bypasses verification).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Sequence
from urllib.parse import urlparse

from .vault import SecretVault

RUNTIME_SCRIPT = Path(__file__).with_name("_live_browser_runtime.mjs")

DEFAULT_VENUE_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "facebook": ("facebook.com", ".facebook.com", ".fbcdn.net", ".fbsbx.com", "static.xx.fbcdn.net"),
    "kbm": ("kbm.id", ".kbm.id", "kbmapp.com", ".kbmapp.com", "app.kbm.id"),
    "local_test": ("127.0.0.1", "localhost"),
}

TransportFn = Callable[[dict[str, Any], float], dict[str, Any]]


def host_allowed(host: str, allowlist: Sequence[str]) -> bool:
    h = str(host or "").strip().lower()
    if not h:
        return False
    for raw in allowlist:
        rule = str(raw or "").strip().lower()
        if not rule:
            continue
        if h == rule:
            return True
        if rule.startswith(".") and (h.endswith(rule) or h == rule[1:]):
            return True
        if not rule.startswith(".") and h.endswith("." + rule):
            return True
    return False


def detect_browser_binaries() -> tuple[str | None, str | None]:
    node = shutil.which("node")
    browser = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chromium-browser")
    return node, browser


def _default_cdp_transport(plan: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
    node, browser = detect_browser_binaries()
    if not node or not browser:
        return {
            "status": "failed",
            "reason": "browser_binary_unavailable",
            "blocked_requests": 0,
            "steps": [],
        }
    plan_with_bin = {**plan, "browser_binary": browser}
    res = subprocess.run(
        [node, str(RUNTIME_SCRIPT)],
        input=json.dumps(plan_with_bin, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    stdout = (res.stdout or "").strip()
    if not stdout:
        return {
            "status": "failed",
            "reason": res.stderr.strip()[:260] or f"runtime_exit_{res.returncode}",
            "blocked_requests": 0,
            "steps": [],
        }
    last_line = stdout.splitlines()[-1]
    try:
        return json.loads(last_line)
    except ValueError:
        return {
            "status": "failed",
            "reason": f"invalid_runtime_output: {last_line[:180]}",
            "blocked_requests": 0,
            "steps": [],
        }


def run_browser_workflow(
    store: Any,
    *,
    venue: str,
    steps: Sequence[dict[str, Any]],
    allowed_hosts: Sequence[str] = (),
    headless: bool = True,
    timeout_ms: int = 12000,
    no_sandbox: bool | None = None,
    task_id: str = "",
    transport: TransportFn | None = None,
) -> dict[str, Any]:
    """Execute a live allowlisted browser workflow with persistent owner session & receipts."""
    key = str(venue).strip().lower()
    base_allow = DEFAULT_VENUE_ALLOWLISTS.get(key, ())
    eff_allow = tuple(dict.fromkeys([*base_allow, *(str(h) for h in allowed_hosts if str(h).strip())]))
    if not eff_allow:
        raise ValueError(f"Tidak ada domain_allowlist terdaftar untuk venue {venue!r}")
    if not steps:
        raise ValueError("Browser workflow membutuhkan minimal 1 step")

    # Pre-validate all navigation URLs against domain allowlist before launching Chromium.
    for idx, step in enumerate(steps, 1):
        if step.get("op") == "navigate":
            url = str(step.get("url") or "")
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not host_allowed(parsed.hostname or "", eff_allow):
                raise PermissionError(
                    f"DOMAIN_BLOCKED (step {idx}): URL {url!r} berada di luar allowlist {eff_allow}"
                )

    vault = SecretVault(store.workspace)
    profile_dir = vault.browser_profile_dir(key)
    evidence_dir = Path(store.workspace).resolve() / "artifacts" / "browser_evidence" / key
    evidence_dir.mkdir(parents=True, exist_ok=True)

    plan = {
        "venue": key,
        "allowed_hosts": list(eff_allow),
        "user_data_dir": str(profile_dir),
        "screenshot_dir": str(evidence_dir),
        "headless": bool(headless),
        "no_sandbox": no_sandbox,
        "timeout_ms": int(timeout_ms),
        "steps": list(steps),
    }

    runner = transport or _default_cdp_transport
    timeout_sec = max(20.0, (len(steps) * int(timeout_ms) / 1000.0) + 15.0)
    raw = runner(plan, timeout_sec)
    status = str(raw.get("status") or "failed")
    reason = raw.get("reason")
    passed = status == "completed"

    if status == "WAITING_FOR_OWNER_AUTH":
        store.emit_event(
            task_id=task_id or f"venue_{key}",
            kind="task_paused",
            status="WAITING_FOR_DEPENDENCY",
            summary_code="waiting_for_owner_auth",
            verification_passed=False,
            technical_detail={
                "venue": key,
                "reason": reason or "LOGIN_OR_AUTH_REQUIRED",
                "profile_dir": str(profile_dir),
            },
        )
        return {
            "ok": False,
            "status": "WAITING_FOR_OWNER_AUTH",
            "reason": reason or "LOGIN_REQUIRED",
            "venue": key,
            "profile_dir": str(profile_dir),
            "blocked_requests": int(raw.get("blocked_requests") or 0),
            "steps": raw.get("steps") or [],
            "receipt": None,
        }

    rcpt = store.record_receipt(
        task_id=task_id or f"venue_{key}",
        action_kind=f"live_browser_{key}",
        input_data=json.dumps({"venue": key, "step_count": len(steps), "allowed_hosts": eff_allow}, sort_keys=True),
        output_data=json.dumps(raw, sort_keys=True, ensure_ascii=False),
        command_or_operation=f"live_browser:{key}",
        exit_code=0 if passed else 1,
        stdout_text=f"status={status}",
        stderr_text=str(reason or ""),
        artifacts_created=[
            st["evidence"]["screenshot_path"]
            for st in (raw.get("steps") or [])
            if isinstance(st, dict) and isinstance(st.get("evidence"), dict) and st["evidence"].get("screenshot_path")
        ],
        verified_by="ace-live-browser",
        passed=passed,
    )
    return {
        "ok": passed,
        "status": status,
        "reason": reason,
        "venue": key,
        "profile_dir": str(profile_dir),
        "blocked_requests": int(raw.get("blocked_requests") or 0),
        "steps": raw.get("steps") or [],
        "receipt": rcpt,
    }


def bootstrap_owner_login(
    store: Any,
    *,
    venue: str,
    login_url: str = "",
    headless: bool = False,
    wait_ms: int = 180_000,
    transport: TransportFn | None = None,
) -> dict[str, Any]:
    """Open interactive Chromium window for the owner to log into Facebook or KBM once and persist session cookies."""
    key = str(venue).strip().lower()
    default_urls = {
        "facebook": "https://www.facebook.com/",
        "kbm": "https://kbm.id/",
    }
    target_url = login_url or default_urls.get(key)
    if not target_url:
        raise ValueError(f"Sertakan login_url untuk venue {venue!r}")

    res = run_browser_workflow(
        store,
        venue=key,
        steps=[
            {"id": "open_login", "op": "navigate", "url": target_url, "stop_on_auth": False},
            {"id": "wait_auth", "op": "wait_for_owner_login", "wait_ms": int(wait_ms)},
            {"id": "confirm_shot", "op": "screenshot", "filename": f"{key}_login_verified.png"},
        ],
        headless=headless,
        timeout_ms=max(15000, int(wait_ms) // 2),
        transport=transport,
    )
    if res["ok"]:
        vault = SecretVault(store.workspace)
        vstat = vault.mark_browser_session_ready(key, account_label="owner_browser_session")
        res["vault_status"] = vstat
    return res
