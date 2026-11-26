"""Autonomous Git & GitHub Delivery Manager for ACE v3.

Enforces three strict invariants:
1. Opt-in Host Policy: `git_auto_pr` / `git_auto_merge` default fail-closed (`False`)
   unless configured by the owner in `<workspace>/.ace_policy.json` or `ACE_GIT_AUTONOMY`.
2. Strict High-Bar Quality Gate: Refuses to commit, open PR, or auto-merge any work
   without a verified `OperationalStore` receipt scoring >= `min_quality_score_bp`
   (default 8500 / 85%). Everything below the bar is rejected.
3. Custody & Secret Safety: Never commits to protected `main` directly, never touches
   the 25 frozen files in `docs/UPSTREAM_SOURCES.json`, never commits secrets/vault files,
   and verifies `headRefOid == expected_head_sha` (anti-TOCTOU) before `gh pr merge`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable, Sequence

from .connectors.vault import contains_secret_pattern
from .quality_gate_engine import DEFAULT_MIN_QUALITY_SCORE_BP, _frozen_upstream_set

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

POLICY_FILENAME = ".ace_policy.json"
DEFAULT_POLICY: dict[str, Any] = {
    "git_auto_pr": False,
    "git_auto_merge": False,
    "allow_live_facebook_publish": False,
    "allow_live_kbm_actions": False,
    "publish_mode": "auto",
    "min_quality_score_bp": DEFAULT_MIN_QUALITY_SCORE_BP,
    "protected_branches": ["main", "master"],
}


def load_host_policy(workspace: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Load explicit owner autonomy policy from workspace/.ace_policy.json + ACE_GIT_AUTONOMY env."""
    policy = dict(DEFAULT_POLICY)
    candidates = []
    if repo_root is not None:
        candidates.append(Path(repo_root) / POLICY_FILENAME)
    candidates.append(Path(workspace) / POLICY_FILENAME)
    for cfg_path in candidates:
        if cfg_path.is_file():
            try:
                loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    policy.update(loaded)
            except (OSError, ValueError):
                pass
    env_git = os.environ.get("ACE_GIT_AUTONOMY", "").strip().lower()
    if env_git == "pr":
        policy["git_auto_pr"] = True
    elif env_git == "merge":
        policy["git_auto_pr"] = True
        policy["git_auto_merge"] = True
    elif env_git == "off":
        policy["git_auto_pr"] = False
        policy["git_auto_merge"] = False
    policy["min_quality_score_bp"] = int(policy.get("min_quality_score_bp", DEFAULT_MIN_QUALITY_SCORE_BP))
    return policy


def _default_run(
    cmd: Sequence[str],
    *,
    cwd: Path,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _slugify(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9\-]+", "-", str(raw).strip().lower()).strip("-")
    return slug[:48] or "change"


def _verify_high_bar_receipt(
    store: Any,
    *,
    task_id: str,
    receipt_id: str,
    score_bp: int | None,
    min_score_bp: int,
) -> tuple[bool, str, dict[str, Any] | None]:
    receipts = store.list_receipts(task_id) if task_id else store.list_receipts()
    match = next((r for r in receipts if r["receipt_id"] == receipt_id), None)
    if not match or not match.get("passed"):
        return False, f"Receipt terverifikasi lulus tidak ditemukan di store: {receipt_id!r}", None
    effective_score = int(score_bp if score_bp is not None else 0)
    if effective_score == 0:
        wos = store.list_work_orders(task_id) if task_id else []
        wo_scores = [int(w.get("quality_score_bp", 0)) for w in wos if w.get("quality_score_bp", 0) > 0]
        if wo_scores:
            effective_score = max(wo_scores)
    if effective_score < int(min_score_bp):
        return (
            False,
            f"DITOLAK (REJECTED_BELOW_BAR): skor kualitas {effective_score} bp < ambang minimum {min_score_bp} bp.",
            match,
        )
    return True, "", match


def _validate_target_paths(repo: Path, target_files: Sequence[str]) -> list[str]:
    if not target_files:
        raise ValueError("target_files tidak boleh kosong")
    frozen = _frozen_upstream_set(repo)
    cleaned: list[str] = []
    for raw in target_files:
        norm = str(raw).replace("\\", "/").lstrip("./")
        if not norm or ".." in Path(norm).parts or Path(norm).is_absolute():
            raise ValueError(f"Path file tidak valid untuk commit: {raw!r}")
        if norm in frozen or norm == "docs/UPSTREAM_SOURCES.json":
            raise PermissionError(f"CUSTODY_VIOLATION: dilarang memodifikasi berkas beku {norm}")
        if norm.startswith("vault/") or ".ace-web-auth" in norm or norm.endswith(".sqlite3"):
            raise PermissionError(f"SECRET_OR_STATE_EXPOSURE: berkas {norm} dilarang di-commit ke Git")
        full = (repo / norm).resolve()
        if not full.is_file():
            raise FileNotFoundError(f"Berkas target commit tidak ditemukan: {norm}")
        text = full.read_text(encoding="utf-8", errors="replace")
        sec = contains_secret_pattern(text)
        if sec:
            raise PermissionError(f"SECRET_PATTERN_DETECTED di {norm}: {sec}")
        cleaned.append(norm)
    return cleaned


def prepare_branch_and_commit(
    repo_root: str | Path,
    store: Any,
    *,
    task_id: str,
    receipt_id: str,
    order_id: str,
    slug: str,
    target_files: Sequence[str],
    commit_message: str,
    agent_id: str = "ace-orchestrator",
    score_bp: int | None = None,
    base_branch: str = "main",
    runner: CommandRunner = _default_run,
) -> dict[str, Any]:
    """Create isolated `ace-auto/*` branch, verify high-bar quality receipt, stage target_files, and commit."""
    repo = Path(repo_root).resolve()
    policy = load_host_policy(store.workspace, repo)
    min_score = int(policy["min_quality_score_bp"])

    ok, err, receipt = _verify_high_bar_receipt(
        store, task_id=task_id, receipt_id=receipt_id, score_bp=score_bp, min_score_bp=min_score
    )
    if not ok:
        return {"ok": False, "verdict": "REJECTED_BELOW_BAR", "error": err}

    try:
        clean_files = _validate_target_paths(repo, target_files)
    except Exception as exc:
        return {"ok": False, "verdict": "CUSTODY_OR_SECRET_BLOCK", "error": str(exc)}

    branch_name = f"ace-auto/{_slugify(order_id)}-{_slugify(slug)}"
    if branch_name in policy.get("protected_branches", ["main", "master"]):
        return {"ok": False, "verdict": "PROTECTED_BRANCH", "error": f"Branch {branch_name} dilindungi"}

    # Check whether origin exists; if so try non-destructive fetch before branching.
    rem_res = runner(["git", "remote"], cwd=repo, timeout=15)
    has_origin = "origin" in (rem_res.stdout or "").split()
    if has_origin:
        runner(["git", "fetch", "origin", base_branch], cwd=repo, timeout=30)

    # Create or reset branch cleanly from HEAD or origin/base_branch when on base_branch.
    cur_res = runner(["git", "branch", "--show-current"], cwd=repo, timeout=10)
    cur_branch = (cur_res.stdout or "").strip()
    start_ref = "HEAD"
    if cur_branch == base_branch and has_origin:
        rev = runner(["git", "rev-parse", "--verify", f"origin/{base_branch}"], cwd=repo, timeout=10)
        if rev.returncode == 0:
            # Fast-forward only if working tree is clean on target files doesn't lose local uncommitted edits.
            pass

    chk = runner(["git", "checkout", "-B", branch_name, start_ref], cwd=repo, timeout=15)
    if chk.returncode != 0:
        return {"ok": False, "verdict": "GIT_ERROR", "error": chk.stderr.strip() or chk.stdout.strip()}

    add_res = runner(["git", "add", "--", *clean_files], cwd=repo, timeout=15)
    if add_res.returncode != 0:
        return {"ok": False, "verdict": "GIT_ERROR", "error": add_res.stderr.strip()}

    diff_res = runner(["git", "diff", "--cached", "--name-only"], cwd=repo, timeout=15)
    staged = [ln.strip() for ln in (diff_res.stdout or "").splitlines() if ln.strip()]
    if not staged:
        return {"ok": False, "verdict": "NO_CHANGES", "error": "Tidak ada perubahan staged pada target_files"}

    full_msg = (
        f"{commit_message.strip()}\n\n"
        f"X-ACE-Task: {task_id}\n"
        f"X-ACE-Receipt: {receipt_id}\n"
        f"X-ACE-Agent: {agent_id}\n"
        f"X-ACE-Quality-Score-Bp: {score_bp or min_score}"
    )
    com_res = runner(["git", "commit", "-m", full_msg], cwd=repo, timeout=30)
    if com_res.returncode != 0:
        return {"ok": False, "verdict": "GIT_COMMIT_FAILED", "error": com_res.stderr.strip() or com_res.stdout.strip()}

    sha_res = runner(["git", "rev-parse", "HEAD"], cwd=repo, timeout=10)
    head_sha = (sha_res.stdout or "").strip()
    return {
        "ok": True,
        "verdict": "COMMITTED",
        "branch": branch_name,
        "head_sha": head_sha,
        "staged_files": staged,
        "receipt_id": receipt_id,
    }


def push_and_open_pr(
    repo_root: str | Path,
    store: Any,
    *,
    task_id: str,
    receipt_id: str,
    branch: str,
    title: str,
    body: str,
    base_branch: str = "main",
    draft: bool = False,
    score_bp: int | None = None,
    gh_bin: str | None = None,
    runner: CommandRunner = _default_run,
) -> dict[str, Any]:
    """Push `ace-auto/*` branch and open a GitHub Pull Request via `gh`, gated by owner opt-in policy & quality receipt."""
    repo = Path(repo_root).resolve()
    policy = load_host_policy(store.workspace, repo)
    if not policy.get("git_auto_pr"):
        return {
            "ok": False,
            "verdict": "POLICY_DISABLED",
            "error": "Auto-PR belum diaktifkan di .ace_policy.json (`git_auto_pr: true`) atau ACE_GIT_AUTONOMY=pr|merge.",
        }
    if not branch.startswith("ace-auto/"):
        return {"ok": False, "verdict": "INVALID_BRANCH", "error": f"Branch harus berawalan ace-auto/: {branch}"}

    ok, err, _ = _verify_high_bar_receipt(
        store,
        task_id=task_id,
        receipt_id=receipt_id,
        score_bp=score_bp,
        min_score_bp=int(policy["min_quality_score_bp"]),
    )
    if not ok:
        return {"ok": False, "verdict": "REJECTED_BELOW_BAR", "error": err}

    gh = gh_bin or shutil.which("gh") or "gh"
    push_res = runner(["git", "push", "--no-follow-tags", "-u", "origin", branch], cwd=repo, timeout=60)
    if push_res.returncode != 0:
        return {"ok": False, "verdict": "GIT_PUSH_FAILED", "error": push_res.stderr.strip() or push_res.stdout.strip()}

    cmd = [gh, "pr", "create", "--base", base_branch, "--head", branch, "--title", title, "--body", body]
    if draft:
        cmd.append("--draft")
    pr_res = runner(cmd, cwd=repo, timeout=60)
    if pr_res.returncode != 0:
        return {"ok": False, "verdict": "GH_PR_CREATE_FAILED", "error": pr_res.stderr.strip() or pr_res.stdout.strip()}

    pr_url = (pr_res.stdout or "").strip().splitlines()[-1].strip()
    pr_num = 0
    m = re.search(r"/pull/(\d+)", pr_url)
    if m:
        pr_num = int(m.group(1))
    else:
        view = runner([gh, "pr", "view", branch, "--json", "number,url,headRefOid"], cwd=repo, timeout=30)
        if view.returncode == 0 and view.stdout.strip():
            info = json.loads(view.stdout)
            pr_num = int(info.get("number") or 0)
            pr_url = str(info.get("url") or pr_url)

    sha_res = runner(["git", "rev-parse", "HEAD"], cwd=repo, timeout=10)
    head_sha = (sha_res.stdout or "").strip()

    rcpt = store.record_receipt(
        task_id=task_id,
        action_kind="git_pr_opened",
        input_data=json.dumps({"branch": branch, "base": base_branch, "receipt_id": receipt_id}),
        output_data=json.dumps({"pr_number": pr_num, "pr_url": pr_url, "head_sha": head_sha}),
        command_or_operation=f"gh pr create --head {branch}",
        exit_code=0,
        stdout_text=pr_url,
        verified_by="ace-git-ops",
        passed=True,
    )
    return {
        "ok": True,
        "verdict": "PR_OPENED",
        "branch": branch,
        "pr_number": pr_num,
        "pr_url": pr_url,
        "head_sha": head_sha,
        "receipt": rcpt,
    }


def verify_checks_and_merge_pr(
    repo_root: str | Path,
    store: Any,
    *,
    task_id: str,
    receipt_id: str,
    pr_number: int | str,
    expected_head_sha: str,
    score_bp: int | None = None,
    method: str = "squash",
    base_branch: str = "main",
    gh_bin: str | None = None,
    runner: CommandRunner = _default_run,
) -> dict[str, Any]:
    """Verify anti-TOCTOU head SHA, CI checks, and high-bar quality score, then merge PR into main."""
    repo = Path(repo_root).resolve()
    policy = load_host_policy(store.workspace, repo)
    if not policy.get("git_auto_merge"):
        return {
            "ok": False,
            "verdict": "POLICY_DISABLED",
            "error": "Auto-merge belum diaktifkan di .ace_policy.json (`git_auto_merge: true`) atau ACE_GIT_AUTONOMY=merge.",
        }

    ok, err, _ = _verify_high_bar_receipt(
        store,
        task_id=task_id,
        receipt_id=receipt_id,
        score_bp=score_bp,
        min_score_bp=int(policy["min_quality_score_bp"]),
    )
    if not ok:
        return {"ok": False, "verdict": "REJECTED_BELOW_BAR", "error": err}

    gh = gh_bin or shutil.which("gh") or "gh"
    view_res = runner(
        [
            gh,
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,url,state,mergeable,headRefOid,headRefName,statusCheckRollup",
        ],
        cwd=repo,
        timeout=30,
    )
    if view_res.returncode != 0:
        return {"ok": False, "verdict": "GH_VIEW_FAILED", "error": view_res.stderr.strip() or view_res.stdout.strip()}

    info = json.loads(view_res.stdout)
    actual_sha = str(info.get("headRefOid") or "")
    if expected_head_sha and actual_sha != expected_head_sha:
        return {
            "ok": False,
            "verdict": "HEAD_SHA_MISMATCH",
            "error": f"Anti-TOCTOU: headRefOid berubah ({actual_sha} != {expected_head_sha}); wajib verifikasi ulang.",
        }
    if str(info.get("state") or "").upper() != "OPEN":
        return {"ok": False, "verdict": "PR_NOT_OPEN", "error": f"Status PR bukan OPEN: {info.get('state')}"}
    if str(info.get("mergeable") or "").upper() == "CONFLICTING":
        return {"ok": False, "verdict": "MERGE_CONFLICT", "error": "PR memiliki konflik merge dengan branch target."}

    rollup = info.get("statusCheckRollup") or []
    failing = [
        c
        for c in rollup
        if isinstance(c, dict)
        and (
            str(c.get("conclusion") or "").upper() in ("FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED")
            or str(c.get("status") or "").upper() in ("IN_PROGRESS", "QUEUED", "PENDING")
        )
    ]
    if failing:
        return {
            "ok": False,
            "verdict": "CI_NOT_GREEN",
            "error": "Status checks GitHub belum seluruhnya hijau/selesai.",
            "checks": failing,
        }

    merge_flag = {"squash": "--squash", "merge": "--merge", "rebase": "--rebase"}.get(method, "--squash")
    merge_res = runner(
        [gh, "pr", "merge", str(pr_number), merge_flag, "--delete-branch"],
        cwd=repo,
        timeout=60,
    )
    if merge_res.returncode != 0:
        return {"ok": False, "verdict": "GH_MERGE_FAILED", "error": merge_res.stderr.strip() or merge_res.stdout.strip()}

    # Best-effort sync back to clean base_branch locally.
    runner(["git", "checkout", base_branch], cwd=repo, timeout=15)
    runner(["git", "pull", "--ff-only", "origin", base_branch], cwd=repo, timeout=30)

    rcpt = store.record_receipt(
        task_id=task_id,
        action_kind="git_pr_merged",
        input_data=json.dumps({"pr_number": pr_number, "expected_head_sha": expected_head_sha, "method": method}),
        output_data=json.dumps({"pr_url": info.get("url", ""), "merged_head_sha": actual_sha}),
        command_or_operation=f"gh pr merge {pr_number} {merge_flag} --delete-branch",
        exit_code=0,
        stdout_text=f"merged PR #{pr_number}",
        verified_by="ace-git-ops",
        passed=True,
    )
    store.emit_event(
        task_id=task_id,
        kind="git_pr_merged",
        status="COMPLETED",
        summary_code="git_pr_merged",
        verification_passed=True,
        technical_detail={"pr_number": pr_number, "head_sha": actual_sha, "receipt_id": rcpt["receipt_id"]},
    )
    return {
        "ok": True,
        "verdict": "MERGED",
        "pr_number": info.get("number", pr_number),
        "pr_url": info.get("url", ""),
        "head_sha": actual_sha,
        "receipt": rcpt,
    }
