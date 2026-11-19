#!/usr/bin/env python3
"""Pipeline digest perubahan harian otomatis (WS-E #15).

Merangkum git log + status workspace + berkas status opsional (stage,
heartbeat, royalty, schedule, storage-debt, dashboard) menjadi bahan
posting perubahan harian yang eksplisit berstatus NON-OTORITATIF.

Hanya menggunakan pustaka standar Python dan bersifat baca-saja terhadap
repositori sumber.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


SCHEMA_VERSION = "ace.daily-digest.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import (
    kbm_schedule as _kbm_schedule,
    repo_index as _repo_index,
    repo_status_dashboard as _repo_status_dashboard,
    royalty_track as _royalty_track,
    ruleset_readiness as _ruleset_readiness,
    self_send_audit_view as _self_send_audit_view,
    stage_verify as _stage_verify,
    storage_debt as _storage_debt,
)

NON_AUTHORITATIVE_NOTICE = (
    "Non-authoritative daily change digest material only; "
    "not an official verdict, merge gate, or release attestation."
)


class DailyDigestError(RuntimeError):
    """Error saat membaca repositori Git atau menyusun digest harian."""


def _run_git(repo_dir: Path, args: Sequence[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}"
        raise DailyDigestError(f"git {' '.join(args)} gagal: {detail}")
    return proc


def _ensure_git_repo(repo_dir: Path) -> Path:
    if not repo_dir.exists() or not repo_dir.is_dir():
        raise DailyDigestError(f"Direktori repo tidak ditemukan: {repo_dir}")
    probe = _run_git(repo_dir, ["rev-parse", "--show-toplevel"], check=False)
    if probe.returncode != 0:
        raise DailyDigestError(f"Bukan repositori Git yang valid: {repo_dir}")
    return Path(probe.stdout.strip()).resolve()


def collect_git_log(
    repo_root: Path,
    ref: str = "HEAD",
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_commits: int = 25,
) -> List[Dict[str, Any]]:
    """Ambil daftar commit beserta berkas yang disentuh secara deterministik."""
    if max_commits < 1:
        raise DailyDigestError("max_commits harus >= 1")

    has_head = _run_git(repo_root, ["rev-parse", "--verify", ref], check=False)
    if has_head.returncode != 0:
        return []

    record_sep = "\x1e"
    field_sep = "\x1f"
    fmt = f"{record_sep}%H{field_sep}%h{field_sep}%an{field_sep}%aI{field_sep}%s"
    cmd = ["log", ref, f"--max-count={max_commits}", f"--format={fmt}", "--name-only"]
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")

    res = _run_git(repo_root, cmd)
    commits: List[Dict[str, Any]] = []
    for raw_rec in res.stdout.split(record_sep):
        rec = raw_rec.strip("\r\n")
        if not rec.strip():
            continue
        lines = rec.splitlines()
        header = lines[0]
        parts = header.split(field_sep, 4)
        if len(parts) != 5:
            continue
        sha, short_sha, author, committed_at, subject = parts
        files = [ln.strip() for ln in lines[1:] if ln.strip()]
        commits.append(
            {
                "sha": sha,
                "short_sha": short_sha,
                "author": author,
                "committed_at": committed_at,
                "subject": subject,
                "files": files,
                "file_count": len(files),
            }
        )
    return commits


def collect_workspace_status(repo_root: Path) -> Dict[str, Any]:
    """Kumpulkan ringkasan status working tree saat ini tanpa mengubah file apa pun."""
    branch_res = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "UNKNOWN"

    head_res = _run_git(repo_root, ["rev-parse", "--short", "HEAD"], check=False)
    head_short = head_res.stdout.strip() if head_res.returncode == 0 else None

    porcelain = _run_git(repo_root, ["status", "--porcelain=v1", "--untracked-files=all"])
    staged: List[str] = []
    modified: List[str] = []
    untracked: List[str] = []

    for line in porcelain.stdout.splitlines():
        if len(line) < 4:
            continue
        xy = line[:2]
        path_part = line[3:].strip()
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        if xy == "??":
            untracked.append(path_part)
        else:
            if xy[0] not in (" ", "?"):
                staged.append(path_part)
            if xy[1] not in (" ", "?"):
                modified.append(path_part)

    total_dirty = len(set(staged) | set(modified) | set(untracked))
    return {
        "branch": branch,
        "head_short": head_short,
        "clean": total_dirty == 0,
        "staged_count": len(staged),
        "modified_count": len(modified),
        "untracked_count": len(untracked),
        "dirty_total_paths": total_dirty,
        "staged_paths": sorted(staged),
        "modified_paths": sorted(modified),
        "untracked_paths": sorted(untracked),
    }


def _load_optional_json(path_str: Optional[str], label: str, warnings: List[str]) -> Optional[Dict[str, Any]]:
    if not path_str:
        return None
    p = Path(path_str)
    if not p.exists():
        warnings.append(f"{label}: berkas tidak ditemukan ({p})")
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"{label}: gagal membaca JSON ({exc})")
        return None
    if not isinstance(data, dict):
        warnings.append(f"{label}: akar JSON harus objek")
        return None
    return data


def _summarize_signals(
    *,
    stage_data: Optional[Dict[str, Any]],
    heartbeat_data: Optional[Dict[str, Any]],
    royalty_data: Optional[Dict[str, Any]],
    schedule_data: Optional[Dict[str, Any]],
    storage_debt_data: Optional[Dict[str, Any]],
    dashboard_data: Optional[Dict[str, Any]],
    repo_index_data: Optional[Dict[str, Any]] = None,
    ruleset_data: Optional[Dict[str, Any]] = None,
    audit_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    signals: Dict[str, Any] = {}

    if stage_data is not None:
        ok_val = stage_data.get("ok")
        if ok_val is None and "valid" in stage_data:
            ok_val = stage_data.get("valid")
        verified_count = (
            len(stage_data.get("verified_files", []))
            if isinstance(stage_data.get("verified_files"), list)
            else stage_data.get("verified_count", stage_data.get("actual_count"))
        )
        signals["stage"] = {
            "schema": stage_data.get("schema"),
            "stage": stage_data.get("stage") or stage_data.get("current_stage") or stage_data.get("stage_dir"),
            "ok": ok_val,
            "verified_count": verified_count,
            "missing_count": len(stage_data["missing"]) if isinstance(stage_data.get("missing"), list) else None,
            "extra_count": len(stage_data["extra"]) if isinstance(stage_data.get("extra"), list) else None,
            "modified_count": len(stage_data["modified"]) if isinstance(stage_data.get("modified"), list) else None,
        }

    if heartbeat_data is not None:
        signals["heartbeat"] = {
            "status": heartbeat_data.get("status"),
            "timestamp": heartbeat_data.get("timestamp") or heartbeat_data.get("last_seen"),
            "host": heartbeat_data.get("host"),
        }

    if royalty_data is not None:
        totals = royalty_data.get("totals") if isinstance(royalty_data.get("totals"), dict) else {}
        signals["royalty"] = {
            "schema": royalty_data.get("schema"),
            "currency": royalty_data.get("currency") or totals.get("currency"),
            "total_royalty": totals.get("total_royalty") or royalty_data.get("total_royalty"),
            "totals_by_currency": royalty_data.get("totals_by_currency"),
            "row_count": royalty_data.get("row_count") or totals.get("row_count") or royalty_data.get("valid_rows"),
        }

    if schedule_data is not None:
        summary = schedule_data.get("summary") if isinstance(schedule_data.get("summary"), dict) else {}
        signals["schedule"] = {
            "schema": schedule_data.get("schema"),
            "completed": summary.get("completed"),
            "overdue": summary.get("overdue"),
            "scheduled": summary.get("scheduled"),
        }

    if storage_debt_data is not None:
        summary = storage_debt_data.get("summary") if isinstance(storage_debt_data.get("summary"), dict) else {}
        signals["storage_debt"] = {
            "schema": storage_debt_data.get("schema"),
            "total_debt_files": summary.get("total_debt_files"),
            "total_debt_bytes": summary.get("total_debt_bytes"),
            "unpushed_commit_count": summary.get("unpushed_commit_count"),
        }

    if dashboard_data is not None:
        corpora = dashboard_data.get("frozen_corpora") if isinstance(dashboard_data.get("frozen_corpora"), dict) else {}
        signals["dashboard"] = {
            "schema": dashboard_data.get("schema"),
            "generated_at": dashboard_data.get("generated_at"),
            "gate_count": dashboard_data.get("gate_count"),
            "corpus_count": corpora.get("corpus_count") if corpora else None,
            "timeline_count": dashboard_data.get("timeline_count"),
        }

    if repo_index_data is not None:
        signals["repo_index"] = {
            "schema": repo_index_data.get("schema"),
            "directory_count": repo_index_data.get("directory_count"),
            "file_count": repo_index_data.get("file_count"),
            "module_count": repo_index_data.get("module_count"),
        }

    if ruleset_data is not None:
        rs = ruleset_data.get("summary") if isinstance(ruleset_data.get("summary"), dict) else {}
        signals["ruleset_readiness"] = {
            "schema": ruleset_data.get("schema"),
            "repo": ruleset_data.get("repo"),
            "branch": ruleset_data.get("branch"),
            "ready": ruleset_data.get("ready"),
            "required_passed": rs.get("required_passed"),
            "required_total": rs.get("required_total"),
        }

    if audit_data is not None:
        aus = audit_data.get("summary") if isinstance(audit_data.get("summary"), dict) else {}
        signals["self_send_audit"] = {
            "schema": audit_data.get("schema"),
            "total_rows": aus.get("total_rows"),
            "delivered_count": aus.get("delivered_count"),
            "anomaly_count": aus.get("anomaly_count"),
        }

    return signals


def build_daily_digest(
    repo_dir: Path,
    *,
    ref: str = "HEAD",
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_commits: int = 25,
    digest_date: Optional[str] = None,
    stage_file: Optional[str] = None,
    stage_dir: Optional[str] = None,
    stage_manifest: Optional[str] = None,
    heartbeat_file: Optional[str] = None,
    royalty_file: Optional[str] = None,
    royalty_csvs: Optional[Sequence[str]] = None,
    royalty_map: Optional[str] = None,
    schedule_file: Optional[str] = None,
    schedule_catalog: Optional[str] = None,
    schedule_as_of: Optional[str] = None,
    storage_debt_file: Optional[str] = None,
    auto_storage_debt: bool = False,
    dashboard_file: Optional[str] = None,
    auto_dashboard: bool = False,
    auto_repo_index: bool = False,
    ruleset_snapshot: Optional[str] = None,
    ruleset_repo: str = "dianzherdiana25-hash/ACE",
    ruleset_branch: str = "main",
    audit_files: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Susun payload digest harian (skema ace.daily-digest.v1)."""
    repo_root = _ensure_git_repo(Path(repo_dir))
    commits = collect_git_log(
        repo_root,
        ref=ref,
        since=since,
        until=until,
        max_commits=max_commits,
    )
    workspace = collect_workspace_status(repo_root)

    warnings: List[str] = []
    stage_data = _load_optional_json(stage_file, "stage", warnings)
    if stage_data is None and stage_dir:
        try:
            stage_data = _stage_verify.verify_stage(
                Path(stage_dir),
                manifest_path=Path(stage_manifest) if stage_manifest else None,
            )
        except _stage_verify.StageVerifyError as exc:
            raise DailyDigestError(f"Verifikasi stage gagal: {exc}") from exc

    heartbeat_data = _load_optional_json(heartbeat_file, "heartbeat", warnings)

    royalty_data = _load_optional_json(royalty_file, "royalty", warnings)
    if royalty_data is None and royalty_csvs:
        try:
            col_map = _royalty_track.load_column_map(Path(royalty_map) if royalty_map else None)
            royalty_data = _royalty_track.summarize_royalties(
                [Path(p) for p in royalty_csvs],
                column_map=col_map,
            )
        except _royalty_track.RoyaltyTrackError as exc:
            raise DailyDigestError(f"Ringkasan royalti gagal: {exc}") from exc

    schedule_data = _load_optional_json(schedule_file, "schedule", warnings)
    if schedule_data is None and schedule_catalog:
        try:
            schedule_data = _kbm_schedule.build_schedule(
                Path(schedule_catalog),
                as_of_date=schedule_as_of,
            )
        except _kbm_schedule.KbmScheduleError as exc:
            raise DailyDigestError(f"Jadwal KBM gagal: {exc}") from exc

    storage_debt_data = _load_optional_json(storage_debt_file, "storage_debt", warnings)
    if storage_debt_data is None and auto_storage_debt:
        try:
            storage_debt_data = _storage_debt.scan_storage_debt(repo_root)
        except _storage_debt.StorageDebtError as exc:
            raise DailyDigestError(f"Pemindaian storage debt gagal: {exc}") from exc

    dashboard_data = _load_optional_json(dashboard_file, "dashboard", warnings)
    if dashboard_data is None and auto_dashboard:
        dashboard_data = _repo_status_dashboard.collect_repo_status(repo_root)

    repo_index_data: Optional[Dict[str, Any]] = None
    if auto_repo_index:
        repo_index_data = _repo_index.build_repo_index(repo_root)

    ruleset_data: Optional[Dict[str, Any]] = None
    if ruleset_snapshot:
        try:
            ruleset_data = _ruleset_readiness.check_repo_readiness(
                repo=ruleset_repo,
                branch=ruleset_branch,
                snapshot_path=Path(ruleset_snapshot),
            )
        except _ruleset_readiness.RulesetReadinessError as exc:
            raise DailyDigestError(f"Pemeriksaan ruleset snapshot gagal: {exc}") from exc

    audit_data: Optional[Dict[str, Any]] = None
    if audit_files:
        try:
            audit_data = _self_send_audit_view.inspect_audit_files(
                [Path(p) for p in audit_files],
                allow_missing_extra=True,
            )
        except _self_send_audit_view.AuditViewError as exc:
            raise DailyDigestError(f"Pembacaan audit self-send gagal: {exc}") from exc

    signals = _summarize_signals(
        stage_data=stage_data,
        heartbeat_data=heartbeat_data,
        royalty_data=royalty_data,
        schedule_data=schedule_data,
        storage_debt_data=storage_debt_data,
        dashboard_data=dashboard_data,
        repo_index_data=repo_index_data,
        ruleset_data=ruleset_data,
        audit_data=audit_data,
    )

    touched_files = sorted({f for c in commits for f in c["files"]})
    authors = sorted({c["author"] for c in commits})

    if digest_date is None:
        digest_date = _dt.date.today().isoformat()

    return {
        "schema": SCHEMA_VERSION,
        "authoritative": False,
        "notice": NON_AUTHORITATIVE_NOTICE,
        "digest_date": digest_date,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "window": {
            "ref": ref,
            "since": since,
            "until": until,
            "max_commits": max_commits,
        },
        "summary": {
            "commit_count": len(commits),
            "author_count": len(authors),
            "authors": authors,
            "touched_file_count": len(touched_files),
            "workspace_clean": workspace["clean"],
            "workspace_dirty_paths": workspace["dirty_total_paths"],
            "warning_count": len(warnings),
        },
        "commits": commits,
        "touched_files": touched_files,
        "workspace": workspace,
        "signals": signals,
        "warnings": warnings,
    }


def render_markdown(digest: Dict[str, Any]) -> str:
    """Render payload ace.daily-digest.v1 menjadi bahan posting Markdown non-otoritatif."""
    ws = digest["workspace"]
    summary = digest["summary"]
    lines: List[str] = [
        f"# Digest Perubahan Harian ACE — {digest['digest_date']}",
        "",
        "> **Status: NON-OTORITATIF** — Bahan draf ringkasan perubahan harian otomatis; bukan vonis ukur, bukan gerbang rilis.",
        "",
        "## Ringkasan",
        f"- Branch aktif: `{ws['branch']}` (HEAD `{ws['head_short'] or '-'}`)",
        f"- Commit pada jendela: **{summary['commit_count']}** oleh {summary['author_count']} kontributor ({summary['touched_file_count']} berkas tersentuh)",
        f"- Status working tree: {'bersih' if ws['clean'] else 'kotor'} "
        f"(staged={ws['staged_count']}, modified={ws['modified_count']}, untracked={ws['untracked_count']})",
    ]

    if digest["commits"]:
        lines.extend(["", "## Commit Terbaru"])
        for c in digest["commits"]:
            lines.append(
                f"- `{c['short_sha']}` {c['subject']} — _{c['author']}_ ({c['committed_at']}, {c['file_count']} berkas)"
            )
    else:
        lines.extend(["", "## Commit Terbaru", "- Tidak ada commit pada rentang filter ini."])

    if not ws["clean"]:
        lines.extend(["", "## Utang Workspace Lokal (Belum di-commit)"])
        if ws["staged_paths"]:
            lines.append(f"- Staged: {', '.join(f'`{p}`' for p in ws['staged_paths'])}")
        if ws["modified_paths"]:
            lines.append(f"- Modified: {', '.join(f'`{p}`' for p in ws['modified_paths'])}")
        if ws["untracked_paths"]:
            lines.append(f"- Untracked: {', '.join(f'`{p}`' for p in ws['untracked_paths'])}")

    if digest["signals"]:
        lines.extend(["", "## Sinyal Operasional Tambahan"])
        for key, val in sorted(digest["signals"].items()):
            compact = ", ".join(f"{k}={v}" for k, v in val.items() if v is not None)
            lines.append(f"- **{key}**: {compact or '-'}")

    if digest["warnings"]:
        lines.extend(["", "## Peringatan Input"])
        for w in digest["warnings"]:
            lines.append(f"- {w}")

    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Buat digest perubahan harian ACE (non-otoritatif) dari git log + status workspace."
    )
    parser.add_argument("--repo-dir", default=".", help="Direktori repositori Git target (default: .)")
    parser.add_argument("--ref", default="HEAD", help="Git ref dasar log (default: HEAD)")
    parser.add_argument("--since", default=None, help="Filter tanggal awal git log (mis. 2026-11-16)")
    parser.add_argument("--until", default=None, help="Filter tanggal akhir git log")
    parser.add_argument("--max-commits", type=int, default=25, help="Batas maksimum commit (default: 25)")
    parser.add_argument("--date", default=None, help="Label tanggal digest YYYY-MM-DD (default: hari ini)")
    parser.add_argument("--stage-file", default=None, help="Berkas JSON stage_verify opsional")
    parser.add_argument("--stage-dir", default=None, help="Direktori stage terisolasi opsional untuk stage_verify")
    parser.add_argument("--stage-manifest", default=None, help="Manifest stage khusus untuk --stage-dir")
    parser.add_argument("--heartbeat-file", default=None, help="Berkas JSON heartbeat opsional")
    parser.add_argument("--royalty-file", default=None, help="Berkas JSON royalty_track opsional")
    parser.add_argument("--royalty-csv", nargs="+", default=None, help="Berkas CSV royalti untuk dihitung langsung")
    parser.add_argument("--royalty-map", default=None, help="JSON pemetaan kolom untuk --royalty-csv")
    parser.add_argument("--schedule-file", default=None, help="Berkas JSON kbm_schedule opsional")
    parser.add_argument("--schedule-catalog", default=None, help="JSON katalog jadwal untuk dihitung langsung")
    parser.add_argument("--schedule-as-of", default=None, help="Tanggal acuan YYYY-MM-DD untuk --schedule-catalog")
    parser.add_argument("--storage-debt-file", default=None, help="Berkas JSON storage_debt opsional")
    parser.add_argument("--auto-storage-debt", action="store_true", help="Hitung storage debt langsung dari repo target")
    parser.add_argument("--dashboard-file", default=None, help="Berkas JSON repo_status_dashboard opsional")
    parser.add_argument("--auto-dashboard", action="store_true", help="Kumpulkan sinyal repo_status_dashboard langsung")
    parser.add_argument("--auto-repo-index", action="store_true", help="Kumpulkan ringkasan repo_index langsung")
    parser.add_argument("--auto-all", action="store_true", help="Aktifkan --auto-storage-debt, --auto-dashboard, dan --auto-repo-index")
    parser.add_argument("--ruleset-snapshot", default=None, help="Snapshot JSON ruleset_readiness (offline)")
    parser.add_argument("--ruleset-repo", default="dianzherdiana25-hash/ACE", help="Nama owner/repo untuk --ruleset-snapshot")
    parser.add_argument("--ruleset-branch", default="main", help="Branch untuk --ruleset-snapshot")
    parser.add_argument("--audit-file", action="append", default=None, help="Berkas JSONL self_send_audit_view opsional")
    parser.add_argument("--out-json", default=None, help="Tulis output JSON ke berkas ini")
    parser.add_argument("--out-md", default=None, help="Tulis output Markdown ke berkas ini")
    parser.add_argument(
        "--format",
        choices=("json", "md", "both"),
        default="json",
        help="Format keluaran stdout jika tidak hanya menulis berkas (default: json)",
    )

    args = parser.parse_args(argv)
    try:
        digest = build_daily_digest(
            Path(args.repo_dir),
            ref=args.ref,
            since=args.since,
            until=args.until,
            max_commits=args.max_commits,
            digest_date=args.date,
            stage_file=args.stage_file,
            stage_dir=args.stage_dir,
            stage_manifest=args.stage_manifest,
            heartbeat_file=args.heartbeat_file,
            royalty_file=args.royalty_file,
            royalty_csvs=args.royalty_csv,
            royalty_map=args.royalty_map,
            schedule_file=args.schedule_file,
            schedule_catalog=args.schedule_catalog,
            schedule_as_of=args.schedule_as_of,
            storage_debt_file=args.storage_debt_file,
            auto_storage_debt=bool(args.auto_storage_debt or args.auto_all),
            dashboard_file=args.dashboard_file,
            auto_dashboard=bool(args.auto_dashboard or args.auto_all),
            auto_repo_index=bool(args.auto_repo_index or args.auto_all),
            ruleset_snapshot=args.ruleset_snapshot,
            ruleset_repo=args.ruleset_repo,
            ruleset_branch=args.ruleset_branch,
            audit_files=args.audit_file,
        )
    except DailyDigestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    md_text = render_markdown(digest)
    json_text = json.dumps(digest, indent=2, ensure_ascii=False)

    if args.out_json:
        Path(args.out_json).write_text(json_text + "\n", encoding="utf-8")
    if args.out_md:
        Path(args.out_md).write_text(md_text, encoding="utf-8")

    if args.format == "json":
        print(json_text)
    elif args.format == "md":
        print(md_text)
    else:
        print(json_text)
        print("\n---\n")
        print(md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
