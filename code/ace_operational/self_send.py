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
  audit chain is committed with the send in two phases — a
  `prepared` row in the content commit and a FINAL row
  (outcome + PR number) in a follow-up commit on the same
  branch — so the repo record never sits at a pending status;
- fail-closed: any failed step stops the send and is recorded;
  a pushed branch whose PR step failed is reported by name
  for operator cleanup, never force-touched.

Hardening (2026-11-16, after an external static review of the
first version; the review's points, in the order fixed):

1. repo + basis lock: the configured origin must be exactly
   EXPECTED_REPO; the branch is created FROM the verified
   local `main` ref, never from whatever HEAD is active; a
   non-clean index/worktree refuses the send; the commit is
   restricted to the allowlisted paths — staged, then the
   staged set is verified name-for-name before committing.
2. symlink closure: every destination (payload files and the
   audit file) must RESOLVE inside the repo root; a path that
   escapes through a symlink is refused before any write.
3. marker + audit completeness: the marker is checked before
   ANY staging is written (flush exports nothing while the
   marker is absent); the local audit also records empty
   flushes and exceptions/timeouts; the committed audit ends
   at a final status (see the two-phase note above).
4. batch bounds: ratification exports exclude record ids a
   persistent ack file marks as already sent (acked only
   once a PR number exists); a second flush on the same day
   takes a suffixed slug instead of colliding.
5. real-git tests cover the index, a non-main HEAD, a wrong
   origin, symlinks, and a markerless flush — see
   test_self_send.py (TestRealGit).

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
EXPECTED_REPO = "dianzherdiana25-hash/ACE"
BASE_BRANCH = "main"
BRANCH_PREFIX = "ace-auto/"
ALLOWED_PATH_PREFIXES = ("handover/", "evidence/")
AUDIT_REPO_PATH = "handover/self_send_audit.jsonl"
ACK_NAME = "self_send_acked.json"
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
_ORIGIN_RES = (
    re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$"),
    re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$"),
    re.compile(r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?$"),
)

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


def parse_origin_repo(url: str) -> Optional[str]:
    """'owner/repo' from a git remote URL, or None."""
    url = (url or "").strip()
    for pattern in _ORIGIN_RES:
        match = pattern.match(url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return None


def path_allowed(rel: str) -> bool:
    """Allowlist + denylist for one repo-relative path.

    Deny wins: a denied fragment anywhere in the lowered path
    refuses it even under an allowed prefix. This check is
    lexical; the resolved-path check is separate
    (resolve_within_root) and both must pass.
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


def resolve_within_root(repo: Path, rel: str) -> Optional[Path]:
    """The absolute path `rel` resolves to, iff it stays
    inside the (resolved) repo root — symlink escapes and
    dangling-link tricks resolve outside and return None."""
    root = Path(repo).resolve()
    dest = (root / rel).resolve()
    if dest == root or root in dest.parents:
        return dest
    return None


def validate_paths(paths: Iterable[str]) -> list:
    paths = list(paths)
    if not paths:
        raise SelfSendRefused("no files to send")
    bad = [p for p in paths if not path_allowed(p)]
    if bad:
        raise SelfSendRefused(f"paths outside allowlist: {bad}")
    return paths


def validate_resolved_paths(repo: Path, paths: Iterable[str]) -> list:
    """Every path must also resolve inside the repo root."""
    bad = [p for p in paths
           if resolve_within_root(repo, p) is None]
    if bad:
        raise SelfSendRefused(f"paths escape repo root: {bad}")
    return list(paths)


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


def _append_repo_audit(repo: Path, row: dict) -> None:
    dest = resolve_within_root(repo, AUDIT_REPO_PATH)
    if dest is None:
        raise SelfSendRefused("audit path escapes repo root")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _write_payload_file(repo: Path, rel: str, data: bytes) -> None:
    dest = resolve_within_root(repo, rel)
    if dest is None:
        raise SelfSendRefused(f"path escapes repo root: {rel}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Re-resolve after mkdir: a parent created through a
    # symlinked directory must not smuggle the write outside.
    dest = resolve_within_root(repo, rel)
    if dest is None:
        raise SelfSendRefused(f"path escapes repo root: {rel}")
    dest.write_bytes(data)


def _staged_names(repo: Path, runner: Runner) -> list:
    rc, out, _e = runner(
        ["git", "diff", "--cached", "--name-only"], repo)
    if rc != 0:
        return []
    return sorted(l.strip() for l in out.splitlines() if l.strip())


def _commit_staged(repo: Path, runner: Runner, paths: list,
                   message: str) -> tuple:
    """Stage exactly `paths`, verify the staged set matches
    name-for-name, then commit. Returns (rc, err)."""
    rc, _o, err = runner(["git", "add", "--", *paths], repo)
    if rc != 0:
        return rc, err
    if _staged_names(repo, runner) != sorted(paths):
        return 1, "staged set differs from the allowlisted paths"
    rc, _o, err = runner(
        ["git", "-c", "user.name=ACE Autonomous Researcher",
         "-c", "user.email=ace-autonomous@local",
         "commit", "-m", message], repo)
    return rc, err


def send(repo_root: Path, home: Path, *,
         files: Mapping[str, bytes], slug: str, trigger: str,
         today: Optional[date] = None,
         runner: Runner = _default_runner,
         title: str = "", body: str = "") -> SendResult:
    """Ship `files` (repo-relative path -> bytes) as one draft PR.

    Fail-closed at every gate; the refusal reasons are stable
    strings the caller can record. The marker is checked
    before the runner is invoked at all; nothing is written
    to the repo before the marker, origin, auth, basis,
    cleanliness, allowlist (lexical + resolved), and
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
        validate_resolved_paths(repo, list(files) + [AUDIT_REPO_PATH])
    except SelfSendRefused as exc:
        return refuse(f"governance:{exc}")

    def run(argv: list) -> tuple:
        return runner(argv, repo)

    restore_branch = BASE_BRANCH
    try:
        rc, out, _e = run(["git", "config", "--get",
                           "remote.origin.url"])
        if rc != 0 or parse_origin_repo(out) != EXPECTED_REPO:
            return refuse("origin_mismatch", branch)
        if not check_gh_auth(repo, runner):
            return refuse("gh_auth_unhealthy", branch)
        rc, _o, _e = run(["git", "rev-parse", "--verify", "--quiet",
                          f"refs/heads/{BASE_BRANCH}"])
        if rc != 0:
            return refuse("base_main_missing", branch)
        rc, out, _e = run(["git", "status", "--porcelain"])
        if rc != 0 or out.strip():
            return refuse("worktree_dirty", branch)
        if _branch_exists(repo, branch, runner):
            return refuse("duplicate_branch", branch)
        rc, current, _e = run(["git", "branch", "--show-current"])
        if rc == 0 and current.strip():
            restore_branch = current.strip()

        rc, _o, err = run(["git", "checkout", "-b", branch,
                           BASE_BRANCH])
        if rc != 0:
            return refuse(f"branch_create_failed:{err.strip()[:120]}",
                          branch)
        commit_title = title or f"ACE self-send: {slug}"
        for rel, data in files.items():
            _write_payload_file(repo, rel, data)
        prepared = _audit_row(
            when=today.isoformat(), trigger=trigger, branch=branch,
            digest=digest, files=sorted(files), pr_number=None,
            outcome="prepared")
        _append_repo_audit(repo, prepared)
        rc, err = _commit_staged(
            repo, runner, sorted(files) + [AUDIT_REPO_PATH],
            commit_title)
        if rc != 0:
            return refuse(f"commit_failed:{err.strip()[:120]}", branch)
        rc, _o, err = run(["git", "push", "-u", "origin", branch])
        if rc != 0:
            return refuse(f"push_failed:{err.strip()[:120]}", branch)
        rc, out, err = run(
            ["gh", "pr", "create", "--draft", "--base", BASE_BRANCH,
             "--head", branch, "--title", commit_title,
             "--body", body or commit_title])
        if rc != 0:
            # The branch is on the remote; never force-touch it.
            # Land the final audit row on it so the repo record
            # closes truthfully, and name it for the operator.
            final = _audit_row(
                when=today.isoformat(), trigger=trigger,
                branch=branch, digest=digest, files=sorted(files),
                pr_number=None, outcome="pushed_pr_failed")
            try:
                _append_repo_audit(repo, final)
                _commit_staged(repo, runner, [AUDIT_REPO_PATH],
                               f"ACE self-send audit: {branch}")
                run(["git", "push", "origin", branch])
            except Exception:
                pass
            _append_local_audit(home, final)
            return SendResult(
                False, f"pr_create_failed:{err.strip()[:120]}",
                branch=branch, content_digest=digest,
                files=sorted(files))
        url = out.strip()
        match = re.search(r"/pull/(\d+)", url)
        pr_number = int(match.group(1)) if match else None
        verified = False
        rc, out, _e = run(
            ["gh", "pr", "view", branch, "--json",
             "number,url,state,isDraft"])
        if rc == 0 and out.strip():
            try:
                data = json.loads(out.strip())
                verified = (data.get("state", "").upper() == "OPEN"
                            and data.get("isDraft") is True)
                pr_number = int(data.get("number", pr_number))
                url = str(data.get("url", url))
            except Exception:
                verified = False
        final = _audit_row(
            when=today.isoformat(), trigger=trigger, branch=branch,
            digest=digest, files=sorted(files),
            pr_number=pr_number,
            outcome="sent" if verified else "sent_unverified")
        finalize_ok = True
        try:
            _append_repo_audit(repo, final)
            rc, err = _commit_staged(
                repo, runner, [AUDIT_REPO_PATH],
                f"ACE self-send audit: {branch}")
            if rc != 0:
                finalize_ok = False
            else:
                rc, _o, err = run(["git", "push", "origin", branch])
                finalize_ok = rc == 0
        except Exception:
            finalize_ok = False
        _append_local_audit(home, final)
        return SendResult(
            verified,
            "sent" if (verified and finalize_ok) else
            "sent_unverified" if not verified else
            "sent_audit_finalize_failed",
            branch=branch, pr_number=pr_number, pr_url=url,
            content_digest=digest, files=sorted(files))
    except Exception as exc:  # incl. runner timeouts: audited
        row = _audit_row(when=today.isoformat(), trigger=trigger,
                         branch=branch, digest=digest,
                         files=sorted(files), pr_number=None,
                         outcome=f"error:{type(exc).__name__}")
        _append_local_audit(home, row)
        return SendResult(
            False, f"error:{type(exc).__name__}:{str(exc)[:120]}",
            branch=branch, content_digest=digest,
            files=sorted(files))
    finally:
        runner(["git", "checkout", restore_branch], repo)


def _load_acked(home: Path) -> dict:
    path = Path(home) / ACK_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_acked(home: Path, acked: dict) -> None:
    path = Path(home) / ACK_NAME
    path.write_text(json.dumps(acked, indent=1, sort_keys=True),
                    encoding="utf-8")


def export_ratification_batch(memory_root: Path,
                              out_path: Path,
                              exclude_ids: Iterable[str] = (),
                              ) -> tuple:
    """Export the ratification-class records of a cognitive
    memory store as one deterministic JSONL artifact.

    Returns (count, digest, ids). Records whose content.class
    is in RATIFICATION_CLASSES and whose id is not in
    `exclude_ids` (the persistent ack set) are sorted by id so
    the export — and therefore the send digest — is stable
    across runs.
    """
    excluded = set(exclude_ids)
    store = Path(memory_root) / "memory.jsonl"
    records = []
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            content = rec.get("content") or {}
            if content.get("class") in RATIFICATION_CLASSES \
                    and rec.get("id") not in excluded:
                records.append(rec)
    records.sort(key=lambda r: r.get("id", ""))
    payload = "".join(
        json.dumps(r, sort_keys=True) + "\n" for r in records
    ).encode("utf-8")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    return (len(records), hashlib.sha256(payload).hexdigest(),
            [r.get("id") for r in records])


def _next_flush_slug(repo: Path, home: Path, today: date,
                     runner: Runner) -> str:
    """'memory-writeback', or '-2', '-3', ... when a same-day
    flush already landed (ack file) or its branch exists."""
    acked = _load_acked(home)
    sent_today = sum(1 for v in acked.values()
                     if isinstance(v, dict)
                     and v.get("ts") == today.isoformat())
    n = sent_today + 1
    while True:
        slug = "memory-writeback" if n == 1 \
            else f"memory-writeback-{n}"
        if not _branch_exists(repo, branch_name_for(today, slug),
                              runner):
            return slug
        n += 1


def flush(memory_root: Path, repo_root: Path, home: Path, *,
          today: Optional[date] = None,
          runner: Runner = _default_runner) -> SendResult:
    """The ratified v1 trigger: export the ratification-class
    batch (minus already-acked records) and send it as one
    draft PR. The marker gates EVERYTHING: while it is absent,
    no staging is written and the refusal is audited. An empty
    batch is an audited no-op, never an empty send."""
    today = today or date.today()
    home = Path(home)
    repo = Path(repo_root)
    if not marker_present(home):
        row = _audit_row(when=today.isoformat(),
                         trigger="ratification_batch_flush",
                         branch="", digest="", files=[],
                         pr_number=None,
                         outcome="refused:marker_absent")
        _append_local_audit(home, row)
        return SendResult(False, "marker_absent")
    acked = _load_acked(home)
    rel = (f"handover/memory_writeback/"
           f"{today.strftime('%Y%m%d')}-ratification-batch.jsonl")
    staging = home / "self_send_staging" / Path(rel).name
    count, digest, ids = export_ratification_batch(
        memory_root, staging, exclude_ids=acked.keys())
    if count == 0:
        row = _audit_row(when=today.isoformat(),
                         trigger="ratification_batch_flush",
                         branch="", digest=digest, files=[],
                         pr_number=None,
                         outcome="no_ratification_records")
        _append_local_audit(home, row)
        return SendResult(False, "no_ratification_records")
    slug = _next_flush_slug(repo, home, today, runner)
    result = send(
        repo, home,
        files={rel: staging.read_bytes()},
        slug=slug,
        trigger="ratification_batch_flush",
        today=today, runner=runner,
        title="ACE self-send: memory write-back ratification batch",
        body=("Ratification-class memory records "
              "(verdict_sealed / mission_ratified / skill_verified) "
              "exported from the cognitive memory store and shipped "
              "by ace_operational.self_send under the ratified "
              "governance (draft only, marker-gated)."))
    if result.pr_number is not None:
        for rid in ids:
            acked[rid] = {"branch": result.branch,
                          "pr_number": result.pr_number,
                          "ts": today.isoformat()}
        _save_acked(home, acked)
    return result


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
