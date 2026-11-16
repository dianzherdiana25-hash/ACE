"""Governed self-send: ACE ships its own records to GitHub.

Owner principle (2026-11-16 01:35): ACE itself must be able to
send to GitHub. Design: `handover/DESAIN_KIRIM_SENDIRI_ACE_20261116.md`
(draft PR), hub-ratified section 6 (2026-11-16):

- marker file alone enables v1 (no time-window gate);
- flush fires only on ratification-class memory batches
  (verdict_sealed / mission_ratified / skill_verified, the
  write-set of `memory_writeback`) at the end of the producing
  work cycle, plus a manual CLI;
- gh credential provisioning in the execution home is an
  operator act; this module never receives, stores, or logs
  credential values — it only gates on `gh auth status`;
- the first live send is a supervised test send; the marker
  stays ABSENT until that test passes.

Governance added over the raw mechanics:

- branch namespace is hard: `ace-auto/<yyyymmdd>-<slug>` only,
  always a NEW branch (non-force push; an existing branch —
  local or remote — refuses the send as a duplicate);
- pull requests are created `--draft` only; this module has
  no merge code at all (merging is never the machine's
  authority);
- a path allowlist (handover/, evidence/, and the audit file)
  plus an explicit denylist (private ledger, secrets) is
  enforced before anything is written or committed;
- every send appends one JSONL audit row locally, and the
  same row (minus the PR number, unknowable pre-commit) is
  committed with the send, so the proof chain lives in the
  repo itself;
- fail-closed: any failed step stops the send and is recorded;
  a pushed branch whose PR step failed is reported by name
  for operator cleanup, never force-touched.

Why this module does not call AutonomousPRManager's pipeline:
on current main the manager's commit step is evaluation-gated
shut (it returns BLOCKED: candidate-bound independent
evaluation unavailable), its push uses --force, and its PR
creation is not draft. The wrapper therefore implements the
governed mechanics directly, following the manager's patterns
(namespace discipline, gh CLI, authoritative verify step).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional

MARKER_NAME = "ACE_SELF_SEND_ENABLED"
BRANCH_PREFIX = "ace-auto/"
ALLOWED_PATH_PREFIXES = ("handover/", "evidence/")
AUDIT_REPO_PATH = "handover/self_send_audit.jsonl"
DENYLIST_FRAGMENTS = (
    "ledger_penghasilan",
    "utang_awal",
    "secret",
    "credential",
    ".env",
    ".ace-llm-token",
    "id_rsa",
    ".pem",
    ".key",
)
RATIFICATION_CLASSES = ("verdict_sealed", "mission_ratified",
                        "skill_verified")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
_BRANCH_RE = re.compile(r"^ace-auto/(\d{8})-([a-z0-9][a-z0-9-]{0,40})$")

# A runner executes one external command and returns
# (returncode, stdout, stderr). Injectable for tests.
Runner = Callable[[list, Path], tuple]


def _default_runner(argv: list, cwd: Path) -> tuple:
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True,
                          text=True, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class SendResult:
    sent: bool
    reason: str
    branch: str = ""
    pr_number: Optional[int] = None
    pr_url: str = ""
    content_digest: str = ""
    files: list = field(default_factory=list)


class SelfSendRefused(Exception):
    """A governance gate refused the send before any effect."""


def marker_present(home: Path) -> bool:
    return (Path(home) / MARKER_NAME).is_file()


def branch_name_for(today: date, slug: str) -> str:
    if not _SLUG_RE.match(slug or ""):
        raise SelfSendRefused(f"invalid slug {slug!r}")
    return f"{BRANCH_PREFIX}{today.strftime('%Y%m%d')}-{slug}"


def validate_branch_name(name: str) -> bool:
    return bool(_BRANCH_RE.match(name or ""))


def path_allowed(rel: str) -> bool:
    """Allowlist + denylist for one repo-relative path.

    Deny wins: a denied fragment anywhere in the lowered path
    refuses it even under an allowed prefix.
    """
    if not rel or rel.startswith("/") or ".." in Path(rel).parts:
        return False
    lowered = rel.lower()
    if any(fragment in lowered for fragment in DENYLIST_FRAGMENTS):
        return False
    if rel == AUDIT_REPO_PATH:
        return True
    return any(rel.startswith(prefix)
               for prefix in ALLOWED_PATH_PREFIXES)


def validate_paths(paths: Iterable[str]) -> list:
    paths = list(paths)
    if not paths:
        raise SelfSendRefused("no files to send")
    bad = [p for p in paths if not path_allowed(p)]
    if bad:
        raise SelfSendRefused(f"paths outside allowlist: {bad}")
    return paths


def content_digest(files: Mapping[str, bytes]) -> str:
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(files[rel])
        h.update(b"\0")
    return h.hexdigest()


def check_gh_auth(repo: Path, runner: Runner) -> bool:
    rc, _out, _err = runner(["gh", "auth", "status"], repo)
    return rc == 0


def _branch_exists(repo: Path, branch: str, runner: Runner) -> bool:
    rc, _o, _e = runner(
        ["git", "rev-parse", "--verify", "--quiet",
         f"refs/heads/{branch}"], repo)
    if rc == 0:
        return True
    rc, out, _e = runner(
        ["git", "ls-remote", "--heads", "origin", branch], repo)
    return rc == 0 and branch in out


def _audit_row(*, when: str, trigger: str, branch: str,
               digest: str, files: list, pr_number,
               outcome: str) -> dict:
    return {"ts": when, "trigger": trigger, "branch": branch,
            "content_digest": digest, "files": files,
            "pr_number": pr_number, "outcome": outcome}


def _append_local_audit(home: Path, row: dict) -> None:
    path = Path(home) / "self_send_audit.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def send(repo_root: Path, home: Path, *,
         files: Mapping[str, bytes], slug: str, trigger: str,
         today: Optional[date] = None,
         runner: Runner = _default_runner,
         title: str = "", body: str = "") -> SendResult:
    """Ship `files` (repo-relative path -> bytes) as one draft PR.

    Fail-closed at every gate; the refusal reasons are stable
    strings the caller can record. Nothing is written to the
    repo before the marker, auth, namespace, allowlist, and
    duplicate gates have all passed.
    """
    repo = Path(repo_root)
    home = Path(home)
    today = today or date.today()
    files = dict(files)
    digest = content_digest(files)

    def refuse(reason: str, branch: str = "") -> SendResult:
        row = _audit_row(when=today.isoformat(), trigger=trigger,
                         branch=branch, digest=digest,
                         files=sorted(files), pr_number=None,
                         outcome=f"refused:{reason}")
        _append_local_audit(home, row)
        return SendResult(False, reason, branch=branch,
                          content_digest=digest,
                          files=sorted(files))

    if not marker_present(home):
        return refuse("marker_absent")
    try:
        branch = branch_name_for(today, slug)
        validate_paths(list(files) + [AUDIT_REPO_PATH])
    except SelfSendRefused as exc:
        return refuse(f"governance:{exc}")
    if not check_gh_auth(repo, runner):
        return refuse("gh_auth_unhealthy", branch)
    if _branch_exists(repo, branch, runner):
        return refuse("duplicate_branch", branch)

    rc, current, _e = runner(
        ["git", "branch", "--show-current"], repo)
    base_branch = current.strip() if rc == 0 and current.strip() \
        else "main"

    def run(argv: list) -> tuple:
        return runner(argv, repo)

    try:
        rc, _o, err = run(["git", "checkout", "-b", branch])
        if rc != 0:
            return refuse(f"branch_create_failed:{err.strip()[:120]}",
                          branch)
        audit_path = repo / AUDIT_REPO_PATH
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        prior = audit_path.read_bytes() if audit_path.exists() \
            else b""
        row = _audit_row(when=today.isoformat(), trigger=trigger,
                         branch=branch, digest=digest,
                         files=sorted(files), pr_number=None,
                         outcome="sent_pending_pr_number")
        committed_audit = prior + (
            json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        for rel, data in files.items():
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        audit_path.write_bytes(committed_audit)
        rc, _o, err = run(["git", "add", "--",
                           *sorted(files), AUDIT_REPO_PATH])
        if rc != 0:
            return refuse(f"stage_failed:{err.strip()[:120]}", branch)
        commit_title = title or f"ACE self-send: {slug}"
        rc, _o, err = run(
            ["git", "-c", "user.name=ACE Autonomous Researcher",
             "-c", "user.email=ace-autonomous@local",
             "commit", "-m", commit_title])
        if rc != 0:
            return refuse(f"commit_failed:{err.strip()[:120]}", branch)
        rc, _o, err = run(["git", "push", "-u", "origin", branch])
        if rc != 0:
            return refuse(f"push_failed:{err.strip()[:120]}", branch)
        rc, out, err = run(
            ["gh", "pr", "create", "--draft", "--base", "main",
             "--head", branch, "--title", commit_title,
             "--body", body or commit_title])
        if rc != 0:
            # The branch is on the remote; never force-touch it.
            # The audit row names it for operator cleanup.
            row["outcome"] = "pushed_pr_failed"
            _append_local_audit(home, row)
            return SendResult(
                False, f"pr_create_failed:{err.strip()[:120]}",
                branch=branch, content_digest=digest,
                files=sorted(files))
        url = out.strip()
        match = re.search(r"/pull/(\d+)", url)
        pr_number = int(match.group(1)) if match else None
        rc, out, _e = run(
            ["gh", "pr", "view", branch, "--json",
             "number,url,state,isDraft"])
        verified = False
        if rc == 0 and out.strip():
            try:
                data = json.loads(out.strip())
                verified = (data.get("state", "").upper() == "OPEN"
                            and data.get("isDraft") is True)
                pr_number = int(data.get("number", pr_number))
                url = str(data.get("url", url))
            except Exception:
                verified = False
        row["pr_number"] = pr_number
        row["outcome"] = "sent" if verified else "sent_unverified"
        _append_local_audit(home, row)
        return SendResult(verified, row["outcome"], branch=branch,
                          pr_number=pr_number, pr_url=url,
                          content_digest=digest,
                          files=sorted(files))
    finally:
        runner(["git", "checkout", base_branch], repo)


def export_ratification_batch(memory_root: Path,
                              out_path: Path) -> tuple:
    """Export the ratification-class records of a cognitive
    memory store as one deterministic JSONL artifact.

    Returns (count, digest). The store file is read directly
    (memory.jsonl); records whose content.class is in
    RATIFICATION_CLASSES are sorted by record id so the export
    — and therefore the send digest — is stable across runs.
    """
    store = Path(memory_root) / "memory.jsonl"
    records = []
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            content = rec.get("content") or {}
            if content.get("class") in RATIFICATION_CLASSES:
                records.append(rec)
    records.sort(key=lambda r: r.get("id", ""))
    payload = "".join(
        json.dumps(r, sort_keys=True) + "\n" for r in records
    ).encode("utf-8")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    return len(records), hashlib.sha256(payload).hexdigest()


def flush(memory_root: Path, repo_root: Path, home: Path, *,
          today: Optional[date] = None,
          runner: Runner = _default_runner) -> SendResult:
    """The ratified v1 trigger: export the ratification-class
    batch and send it as one draft PR. An empty batch is a
    recorded no-op, never an empty send."""
    today = today or date.today()
    rel = (f"handover/memory_writeback/"
           f"{today.strftime('%Y%m%d')}-ratification-batch.jsonl")
    staging = Path(home) / "self_send_staging" / Path(rel).name
    count, _digest = export_ratification_batch(memory_root, staging)
    if count == 0:
        return SendResult(False, "no_ratification_records")
    return send(
        repo_root, home,
        files={rel: staging.read_bytes()},
        slug="memory-writeback",
        trigger="ratification_batch_flush",
        today=today, runner=runner,
        title="ACE self-send: memory write-back ratification batch",
        body=("Ratification-class memory records "
              "(verdict_sealed / mission_ratified / skill_verified) "
              "exported from the cognitive memory store and shipped "
              "by ace_operational.self_send under the ratified "
              "governance (draft only, marker-gated)."))


def _main(argv: Optional[list] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="ace_operational.self_send")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--repo", required=True)
    p_status.add_argument("--home", required=True)
    p_flush = sub.add_parser("flush")
    p_flush.add_argument("--memory-root", required=True)
    p_flush.add_argument("--repo", required=True)
    p_flush.add_argument("--home", required=True)
    args = parser.parse_args(argv)
    home = Path(args.home)
    if args.cmd == "status":
        print(json.dumps({
            "marker_present": marker_present(home),
            "gh_auth_healthy": check_gh_auth(Path(args.repo),
                                             _default_runner),
        }, indent=1))
        return 0
    result = flush(Path(args.memory_root), Path(args.repo), home)
    print(json.dumps({
        "sent": result.sent, "reason": result.reason,
        "branch": result.branch, "pr_number": result.pr_number,
        "pr_url": result.pr_url,
        "content_digest": result.content_digest,
        "files": result.files,
    }, indent=1))
    return 0 if result.sent or result.reason in (
        "no_ratification_records", "marker_absent") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
