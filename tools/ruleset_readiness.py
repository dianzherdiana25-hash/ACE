#!/usr/bin/env python3
"""Read-only checker kesiapan ruleset / branch protection GitHub (WS-F #18).

Memeriksa status proteksi branch (mis. `main`) melalui `gh api` secara
baca-saja ATAU dari berkas `--snapshot <json>` untuk pengujian offline/air-gapped.
Tidak pernah mengubah pengaturan GitHub apa pun.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


SCHEMA_VERSION = "ace.ruleset-readiness.v1"


class RulesetReadinessError(RuntimeError):
    """Error masukan parameter, snapshot, atau pemanggilan gh api."""


Runner = Callable[[Sequence[str]], tuple[int, str, str]]


def _default_runner(argv: Sequence[str]) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def _gh_api_get(endpoint: str, runner: Runner) -> tuple[Optional[Any], Optional[str]]:
    rc, out, err = runner(["gh", "api", "-X", "GET", endpoint])
    if rc != 0:
        msg = err.strip() or out.strip() or f"exit={rc}"
        return None, msg
    if not out.strip():
        return None, "empty response"
    try:
        return json.loads(out), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"


def load_snapshot(snapshot_path: Path) -> Dict[str, Any]:
    if not snapshot_path.is_file():
        raise RulesetReadinessError(f"Berkas snapshot tidak ditemukan: {snapshot_path}")
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RulesetReadinessError(f"Gagal membaca snapshot JSON '{snapshot_path}': {exc}") from exc
    if not isinstance(data, dict):
        raise RulesetReadinessError("Snapshot JSON harus berupa objek.")
    return data


def _extract_rules_from_list(rules: Any) -> Dict[str, Dict[str, Any]]:
    mapped: Dict[str, Dict[str, Any]] = {}
    if not isinstance(rules, list):
        return mapped
    for item in rules:
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            mapped[item["type"]] = item
    return mapped


def evaluate_readiness(
    *,
    repo: str,
    branch: str = "main",
    protection: Optional[Dict[str, Any]] = None,
    branch_rules: Optional[List[Dict[str, Any]]] = None,
    repo_meta: Optional[Dict[str, Any]] = None,
    api_notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Evaluasi kesiapan branch protection / ruleset menjadi checklist terstruktur."""
    if "/" not in repo or repo.startswith("/") or repo.endswith("/"):
        raise RulesetReadinessError(f"Format repo harus 'owner/name': {repo!r}")

    notes = list(api_notes or [])
    rules_map = _extract_rules_from_list(branch_rules)

    prot_present = isinstance(protection, dict) and (
        "required_pull_request_reviews" in protection
        or "enforce_admins" in protection
        or "allow_force_pushes" in protection
        or "allow_deletions" in protection
        or "required_status_checks" in protection
    )
    ruleset_present = len(rules_map) > 0

    pr_reviews = (
        protection.get("required_pull_request_reviews")
        if isinstance(protection, dict)
        else None
    )
    pr_rule = rules_map.get("pull_request")
    pr_rule_params = pr_rule.get("parameters", {}) if isinstance(pr_rule, dict) else {}

    def _safe_nonneg_int(raw: Any, default: int = 0) -> int:
        if raw is None or isinstance(raw, bool):
            return default
        try:
            parsed = int(raw)
        except (ValueError, TypeError, OverflowError):
            return default
        return parsed if parsed >= 0 else default

    required_approvals = 0
    if isinstance(pr_reviews, dict):
        required_approvals = _safe_nonneg_int(pr_reviews.get("required_approving_review_count"))
    elif isinstance(pr_rule_params, dict) and "required_approving_review_count" in pr_rule_params:
        required_approvals = _safe_nonneg_int(pr_rule_params.get("required_approving_review_count"))

    pr_required_ok = bool(isinstance(pr_reviews, dict) or pr_rule is not None)
    approvals_ok = required_approvals >= 1

    allow_force = (
        protection.get("allow_force_pushes")
        if isinstance(protection, dict)
        else None
    )
    force_blocked_by_prot = isinstance(allow_force, dict) and allow_force.get("enabled") is False
    force_blocked_by_rule = "non_fast_forward" in rules_map
    no_force_push_ok = force_blocked_by_prot or force_blocked_by_rule

    allow_del = (
        protection.get("allow_deletions")
        if isinstance(protection, dict)
        else None
    )
    del_blocked_by_prot = isinstance(allow_del, dict) and allow_del.get("enabled") is False
    del_blocked_by_rule = "deletion" in rules_map
    no_deletion_ok = del_blocked_by_prot or del_blocked_by_rule

    enforce_admins = (
        protection.get("enforce_admins")
        if isinstance(protection, dict)
        else None
    )
    enforce_admins_ok = isinstance(enforce_admins, dict) and enforce_admins.get("enabled") is True

    status_checks = (
        protection.get("required_status_checks")
        if isinstance(protection, dict)
        else None
    )
    status_rule = rules_map.get("required_status_checks")
    status_checks_configured = isinstance(status_checks, dict) or status_rule is not None

    default_branch = repo_meta.get("default_branch") if isinstance(repo_meta, dict) else None
    default_branch_ok = (default_branch == branch) if default_branch is not None else None

    checks: List[Dict[str, Any]] = [
        {
            "id": "protection_or_ruleset_active",
            "title": f"Proteksi branch atau ruleset aktif pada '{branch}'",
            "passed": prot_present or ruleset_present,
            "severity": "required",
            "detail": (
                f"classic_protection={prot_present}, ruleset_rules={len(rules_map)}"
            ),
        },
        {
            "id": "pull_request_required",
            "title": "Semua perubahan ke main melalui Pull Request",
            "passed": pr_required_ok,
            "severity": "required",
            "detail": "required_pull_request_reviews atau aturan pull_request aktif"
            if pr_required_ok
            else "Belum ada kewajiban PR sebelum merge/push ke branch target",
        },
        {
            "id": "approving_review_minimum",
            "title": "Minimal 1 review persetujuan sebelum merge",
            "passed": approvals_ok,
            "severity": "required",
            "detail": f"required_approving_review_count={required_approvals}",
        },
        {
            "id": "disallow_force_pushes",
            "title": "Force push ke branch utama diblokir",
            "passed": no_force_push_ok,
            "severity": "required",
            "detail": (
                "non_fast_forward / allow_force_pushes=false"
                if no_force_push_ok
                else "Force push belum diblokir secara eksplisit"
            ),
        },
        {
            "id": "disallow_branch_deletion",
            "title": "Penghapusan branch utama diblokir",
            "passed": no_deletion_ok,
            "severity": "required",
            "detail": (
                "deletion / allow_deletions=false"
                if no_deletion_ok
                else "Penghapusan branch belum diblokir secara eksplisit"
            ),
        },
        {
            "id": "enforce_admins",
            "title": "Aturan berlaku juga untuk admin (tanpa bypass diam-diam)",
            "passed": enforce_admins_ok,
            "severity": "recommended",
            "detail": f"enforce_admins.enabled={enforce_admins.get('enabled') if isinstance(enforce_admins, dict) else None}",
        },
        {
            "id": "required_status_checks",
            "title": "Status checks CI/tes diwajibkan sebelum merge",
            "passed": status_checks_configured,
            "severity": "recommended",
            "detail": "required_status_checks terkonfigurasi"
            if status_checks_configured
            else "Belum ada status check wajib yang terkonfigurasi",
        },
    ]

    if default_branch_ok is not None:
        checks.append(
            {
                "id": "default_branch_match",
                "title": f"Default branch repo adalah '{branch}'",
                "passed": default_branch_ok,
                "severity": "required",
                "detail": f"default_branch={default_branch}",
            }
        )

    required_checks = [c for c in checks if c["severity"] == "required"]
    recommended_checks = [c for c in checks if c["severity"] == "recommended"]
    required_passed = sum(1 for c in required_checks if c["passed"])
    recommended_passed = sum(1 for c in recommended_checks if c["passed"])
    ready = required_passed == len(required_checks)

    return {
        "schema": SCHEMA_VERSION,
        "read_only": True,
        "mutated_github_settings": False,
        "repo": repo,
        "branch": branch,
        "ready": ready,
        "summary": {
            "required_passed": required_passed,
            "required_total": len(required_checks),
            "recommended_passed": recommended_passed,
            "recommended_total": len(recommended_checks),
            "classic_protection_present": prot_present,
            "ruleset_rules_count": len(rules_map),
        },
        "checks": checks,
        "notes": notes,
    }


def check_repo_readiness(
    *,
    repo: str,
    branch: str = "main",
    snapshot_path: Optional[Path] = None,
    runner: Runner = _default_runner,
) -> Dict[str, Any]:
    """Jalankan pemeriksaan kesiapan dari snapshot offline atau gh api GET."""
    if snapshot_path is not None:
        snap = load_snapshot(snapshot_path)
        protection = snap.get("protection") if isinstance(snap.get("protection"), dict) else None
        branch_rules = snap.get("branch_rules") if isinstance(snap.get("branch_rules"), list) else None
        repo_meta = snap.get("repo") if isinstance(snap.get("repo"), dict) else None
        notes = list(snap.get("notes", [])) if isinstance(snap.get("notes"), list) else []
        target_repo = str(snap.get("repo_full_name") or repo)
        target_branch = str(snap.get("branch") or branch)
        return evaluate_readiness(
            repo=target_repo,
            branch=target_branch,
            protection=protection,
            branch_rules=branch_rules,
            repo_meta=repo_meta,
            api_notes=notes,
        )

    notes: List[str] = []
    repo_meta_raw, err_repo = _gh_api_get(f"repos/{repo}", runner)
    if err_repo:
        notes.append(f"repos/{repo}: {err_repo}")
    repo_meta = repo_meta_raw if isinstance(repo_meta_raw, dict) else None

    prot_raw, err_prot = _gh_api_get(f"repos/{repo}/branches/{branch}/protection", runner)
    if err_prot:
        notes.append(f"branches/{branch}/protection: {err_prot}")
    protection = prot_raw if isinstance(prot_raw, dict) else None

    rules_raw, err_rules = _gh_api_get(f"repos/{repo}/rules/branches/{branch}", runner)
    if err_rules:
        notes.append(f"rules/branches/{branch}: {err_rules}")
    branch_rules = rules_raw if isinstance(rules_raw, list) else None

    return evaluate_readiness(
        repo=repo,
        branch=branch,
        protection=protection,
        branch_rules=branch_rules,
        repo_meta=repo_meta,
        api_notes=notes,
    )


def render_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    status_label = "SIAP" if report["ready"] else "BELUM_SIAP"
    lines: List[str] = [
        f"# Checklist Kesiapan Ruleset — `{report['repo']}` (`{report['branch']}`)",
        "",
        f"- Status kesiapan wajib: **{status_label}** ({s['required_passed']}/{s['required_total']} wajib, "
        f"{s['recommended_passed']}/{s['recommended_total']} rekomendasi)",
        "- Mode: **baca-saja** (`mutated_github_settings=false`)",
        "",
        "## Checklist",
    ]
    for chk in report["checks"]:
        mark = "x" if chk["passed"] else " "
        lines.append(
            f"- [{mark}] **[{chk['severity']}] {chk['title']}** — {chk['detail']}"
        )
    if report["notes"]:
        lines.extend(["", "## Catatan API / Snapshot"])
        for n in report["notes"]:
            lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only checker kesiapan ruleset / branch protection GitHub."
    )
    parser.add_argument("--repo", default="dianzherdiana25-hash/ACE", help="Target owner/repo")
    parser.add_argument("--branch", default="main", help="Nama branch target (default: main)")
    parser.add_argument("--snapshot", default=None, help="Berkas JSON snapshot offline (opsional)")
    parser.add_argument("--format", choices=("json", "md"), default="json", help="Format stdout")
    parser.add_argument("--out-json", default=None, help="Tulis output JSON ke berkas")
    parser.add_argument("--out-md", default=None, help="Tulis output Markdown ke berkas")
    parser.add_argument(
        "--fail-if-unready",
        action="store_true",
        help="Kembalikan exit code 1 apabila syarat wajib belum terpenuhi",
    )

    args = parser.parse_args(argv)
    try:
        report = check_repo_readiness(
            repo=args.repo,
            branch=args.branch,
            snapshot_path=Path(args.snapshot) if args.snapshot else None,
        )
    except RulesetReadinessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    md_text = render_markdown(report)
    if args.out_json:
        Path(args.out_json).write_text(json_text + "\n", encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    print(json_text if args.format == "json" else md_text)
    if args.fail_if_unready and not report["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
