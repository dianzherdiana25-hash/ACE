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
- pull requests are created `--draft` only, pinned with an
  explicit `--repo`; this module has no merge code at all
  (merging is never the machine's authority);
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

Hardening round 2 (2026-11-16, external static review):
origin lock, branch from verified local main, dirty-tree
refusal, staged-set verification, resolved-path (symlink
escape) checks, marker before any staging, audited empty
flushes and exceptions, persistent ack/dedup, same-day slug
suffixes. See the design doc section 8.

Hardening round 3 (2026-11-16, the same reviewer's real-git
probes against round 2 — each point is a regression test
first, in test_self_send.py):

1. the push TARGET is pinned, not just the fetch URL: every
   effective push URL (remote.origin.pushurl when present,
   with url.*.insteadOf / pushInsteadOf rewrites applied)
   must identify EXPECTED_REPO, and every gh call carries an
   explicit --repo (a GH_REPO env redirect cannot move it);
2. the basis is the FETCHED origin/main commit, never the
   local main (a synthetic local commit carrying an
   outside-allowlist file used to ride along); before the
   push, the ENTIRE outgoing diff (basis..branch) is
   validated against the allowlist and the branch's
   merge-base must be exactly the pinned basis;
3. symlinks are refused in EVERY component of every
   destination path (payload + audit) — an in-repo symlink
   used to pass the resolved-path check and clobber its
   target before the staged-set check could refuse — and
   the validation runs again AFTER checkout, on the basis
   tree, before any write;
4. flush()'s export lives inside the same audited path as
   send(): a corrupt memory store is an audited error, not
   an escaping exception;
5. partial success is explicit: if the final audit commit
   or its push fails, the result is NOT sent (reason
   audit_finalize_failed, PR number still reported); the
   ack file is written atomically, a corrupt ack file is a
   refusal (never silently read as empty), and records are
   acked only after a fully verified send.

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
import os
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


class AckStoreCorrupt(Exception):
    """The persistent ack file exists but cannot be trusted."""


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
    lexical; the resolved-path and symlink checks are separate
    (resolve_within_root, symlink_components) and all must
    pass.
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


def symlink_components(repo: Path, rel: str) -> list:
    """Components of `rel` (walking from the repo root) that
    ARE symlinks in the current worktree. Any one of them —
    directory or final component — makes the path unsafe to
    write through, wherever the link points."""
    bad = []
    current = Path(repo)
    for part in Path(rel).parts:
        current = current / part
        if current.is_symlink():
            bad.append(part)
            break
    return bad


def validate_paths(paths: Iterable[str]) -> list:
    paths = list(paths)
    if not paths:
        raise SelfSendRefused("no files to send")
    bad = [p for p in paths if not path_allowed(p)]
    if bad:
        raise SelfSendRefused(f"paths outside allowlist: {bad}")
    return paths


def validate_resolved_paths(repo: Path, paths: Iterable[str]) -> list:
    """Every path must resolve inside the repo root AND have
    no symlink in any of its components."""
    paths = list(paths)
    bad = [p for p in paths
           if resolve_within_root(repo, p) is None]
    if bad:
        raise SelfSendRefused(f"paths escape repo root: {bad}")
    linked = [p for p in paths if symlink_components(repo, p)]
    if linked:
        raise SelfSendRefused(f"symlink in path components: {linked}")
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


def _config_get_all(repo: Path, runner: Runner, key: str) -> list:
    rc, out, _e = runner(["git", "config", "--get-all", key], repo)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _rewrite_rules(repo: Path, runner: Runner) -> tuple:
    """(insteadOf, pushInsteadOf) rewrite rules as
    (replacement_base, url_prefix) pairs, from url.* config."""
    rc, out, _e = runner(
        ["git", "config", "--get-regexp", r"^url\."], repo)
    plain: list = []
    push: list = []
    if rc != 0:
        return plain, push
    for line in out.splitlines():
        if " " not in line:
            continue
        key, value = line.split(" ", 1)
        lowered = key.lower()
        if not lowered.startswith("url."):
            continue
        for suffix, target in ((".pushinsteadof", push),
                               (".insteadof", plain)):
            if lowered.endswith(suffix):
                base = key[len("url."):len(key) - len(suffix)]
                target.append((base, value.strip()))
                break
    return plain, push


def _apply_rewrites(url: str, plain: list, push: list) -> str:
    """Git's rewrite semantics: a matching pushInsteadOf rule
    (longest prefix) wins; insteadOf applies only when no
    pushInsteadOf rule matches."""
    for rules in (push, plain):
        best = None
        for base, prefix in rules:
            if url.startswith(prefix) and (
                    best is None or len(prefix) > len(best[1])):
                best = (base, prefix)
        if best is not None:
            return best[0] + url[len(best[1]):]
    return url


def effective_push_urls(repo: Path, runner: Runner) -> list:
    """Every URL a push to origin could actually reach: the
    pushurl set when configured, else the fetch URL — each
    with the configured rewrites applied."""
    urls = _config_get_all(repo, runner, "remote.origin.url")
    pushurls = _config_get_all(repo, runner,
                                "remote.origin.pushurl")
    sources = pushurls if pushurls else urls[:1]
    plain, push = _rewrite_rules(repo, runner)
    return [_apply_rewrites(u, plain, push) for u in sources]


def _audit_row(*, when: str, trigger: str, branch: str,
               digest: str, files: list, pr_number,
               outcome: str, basis: str = "") -> dict:
    return {"ts": when, "trigger": trigger, "branch": branch,
            "basis": basis, "content_digest": digest,
            "files": files, "pr_number": pr_number,
            "outcome": outcome}


def _append_local_audit(home: Path, row: dict) -> None:
    path = Path(home) / "self_send_audit.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _append_repo_audit(repo: Path, row: dict) -> None:
    if symlink_components(repo, AUDIT_REPO_PATH):
        raise SelfSendRefused("symlink in audit path components")
    dest = resolve_within_root(repo, AUDIT_REPO_PATH)
    if dest is None:
        raise SelfSendRefused("audit path escapes repo root")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if symlink_components(repo, AUDIT_REPO_PATH):
        raise SelfSendRefused("symlink in audit path components")
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _write_payload_file(repo: Path, rel: str, data: bytes) -> None:
    if symlink_components(repo, rel):
        raise SelfSendRefused(f"symlink in path components: {rel}")
    dest = resolve_within_root(repo, rel)
    if dest is None:
        raise SelfSendRefused(f"path escapes repo root: {rel}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Re-validate after mkdir: nothing about the path may have
    # become a symlink or an escape in between.
    if symlink_components(repo, rel):
        raise SelfSendRefused(f"symlink in path components: {rel}")
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


def _validate_outgoing(repo: Path, runner: Runner, basis: str,
                       branch: str) -> bool:
    """The whole outgoing history must be exactly: the pinned
    basis, plus commits whose combined diff touches only
    allowlisted paths."""
    rc, out, _e = runner(["git", "merge-base", basis, branch], repo)
    if rc != 0 or out.strip() != basis:
        return False
    rc, out, _e = runner(
        ["git", "diff", "--name-only", f"{basis}..{branch}"], repo)
    if rc != 0:
        return False
    names = [l.strip() for l in out.splitlines() if l.strip()]
    return all(path_allowed(n) for n in names)


def send(repo_root: Path, home: Path, *,
         files: Mapping[str, bytes], slug: str, trigger: str,
         today: Optional[date] = None,
         runner: Runner = _default_runner,
         title: str = "", body: str = "") -> SendResult:
    """Ship `files` (repo-relative path -> bytes) as one draft PR.

    Fail-closed at every gate; the refusal reasons are stable
    strings the caller can record. The marker is checked
    before the runner is invoked at all; nothing is written
    to the repo before the marker, origin, push-target, auth,
    fetched-basis, cleanliness, allowlist (lexical + resolved
    + symlink), and duplicate gates have all passed — and the
    path validation runs once more on the basis tree after
    checkout, before the first write.
    """
    repo = Path(repo_root)
    home = Path(home)
    today = today or date.today()
    files = dict(files)
    digest = content_digest(files)
    basis = ""
    branch = ""

    def refuse(reason: str) -> SendResult:
        row = _audit_row(when=today.isoformat(), trigger=trigger,
                         branch=branch, digest=digest,
                         files=sorted(files), pr_number=None,
                         outcome=f"refused:{reason}", basis=basis)
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
    created_branch = False
    pushed = False
    try:
        rc, out, _e = run(["git", "config", "--get",
                           "remote.origin.url"])
        if rc != 0 or parse_origin_repo(out) != EXPECTED_REPO:
            return refuse("origin_mismatch")
        targets = effective_push_urls(repo, runner)
        if not targets or any(
                parse_origin_repo(u) != EXPECTED_REPO
                for u in targets):
            return refuse("push_target_mismatch")
        if not check_gh_auth(repo, runner):
            return refuse("gh_auth_unhealthy")
        rc, _o, err = run(["git", "fetch", "origin", BASE_BRANCH])
        if rc != 0:
            return refuse(f"fetch_failed:{err.strip()[:120]}")
        rc, out, _e = run(["git", "rev-parse", "--verify", "--quiet",
                           f"refs/remotes/origin/{BASE_BRANCH}"])
        if rc != 0 or not out.strip():
            return refuse("base_main_missing")
        basis = out.strip()
        rc, out, _e = run(["git", "status", "--porcelain"])
        if rc != 0 or out.strip():
            return refuse("worktree_dirty")
        if _branch_exists(repo, branch, runner):
            return refuse("duplicate_branch")
        rc, current, _e = run(["git", "branch", "--show-current"])
        if rc == 0 and current.strip():
            restore_branch = current.strip()

        rc, _o, err = run(["git", "checkout", "-b", branch, basis])
        if rc != 0:
            return refuse(f"branch_create_failed:{err.strip()[:120]}")
        created_branch = True
        # Binding re-validation on the basis tree itself: a
        # symlink planted in the fetched history is visible
        # only now, and no write may precede this check.
        try:
            validate_resolved_paths(
                repo, list(files) + [AUDIT_REPO_PATH])
        except SelfSendRefused as exc:
            return refuse(f"governance:{exc}")
        commit_title = title or f"ACE self-send: {slug}"
        for rel, data in files.items():
            _write_payload_file(repo, rel, data)
        prepared = _audit_row(
            when=today.isoformat(), trigger=trigger, branch=branch,
            digest=digest, files=sorted(files), pr_number=None,
            outcome="prepared", basis=basis)
        _append_repo_audit(repo, prepared)
        rc, err = _commit_staged(
            repo, runner, sorted(files) + [AUDIT_REPO_PATH],
            commit_title)
        if rc != 0:
            return refuse(f"commit_failed:{err.strip()[:120]}")
        if not _validate_outgoing(repo, runner, basis, branch):
            return refuse("outgoing_validation_failed")
        rc, _o, err = run(["git", "push", "-u", "origin", branch])
        if rc != 0:
            return refuse(f"push_failed:{err.strip()[:120]}")
        pushed = True
        rc, out, err = run(
            ["gh", "pr", "create", "--repo", EXPECTED_REPO,
             "--draft", "--base", BASE_BRANCH,
             "--head", branch, "--title", commit_title,
             "--body", body or commit_title])
        if rc != 0:
            # The branch is on the remote; never force-touch it.
            # Land the final audit row on it so the repo record
            # closes truthfully, and name it for the operator.
            final = _audit_row(
                when=today.isoformat(), trigger=trigger,
                branch=branch, digest=digest, files=sorted(files),
                pr_number=None, outcome="pushed_pr_failed",
                basis=basis)
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
            ["gh", "pr", "view", branch, "--repo", EXPECTED_REPO,
             "--json", "number,url,state,isDraft"])
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
            outcome="sent" if verified else "sent_unverified",
            basis=basis)
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
        if not finalize_ok:
            final["outcome"] = "sent_audit_finalize_failed"
        _append_local_audit(home, final)
        if not finalize_ok:
            # Partial success gets its own explicit status:
            # the PR exists, the committed audit chain does
            # not — this is not a sent send.
            return SendResult(
                False, "audit_finalize_failed",
                branch=branch, pr_number=pr_number, pr_url=url,
                content_digest=digest, files=sorted(files))
        return SendResult(
            verified,
            "sent" if verified else "sent_unverified",
            branch=branch, pr_number=pr_number, pr_url=url,
            content_digest=digest, files=sorted(files))
    except Exception as exc:  # incl. runner timeouts: audited
        row = _audit_row(when=today.isoformat(), trigger=trigger,
                         branch=branch, digest=digest,
                         files=sorted(files), pr_number=None,
                         outcome=f"error:{type(exc).__name__}",
                         basis=basis)
        _append_local_audit(home, row)
        return SendResult(
            False, f"error:{type(exc).__name__}:{str(exc)[:120]}",
            branch=branch, content_digest=digest,
            files=sorted(files))
    finally:
        if created_branch and not pushed:
            # Our own unpushed branch: leave the home exactly
            # as we found it — discard the send's writes, go
            # back, drop the branch. A pushed branch is never
            # touched here.
            runner(["git", "reset", "--hard"], repo)
        runner(["git", "checkout", restore_branch], repo)
        if created_branch and not pushed:
            runner(["git", "branch", "-D", branch], repo)


def _load_acked(home: Path) -> dict:
    path = Path(home) / ACK_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AckStoreCorrupt(f"ack file unreadable: {exc}")
    if not isinstance(data, dict):
        raise AckStoreCorrupt("ack file is not a JSON object")
    return data


def _save_acked(home: Path, acked: dict) -> None:
    path = Path(home) / ACK_NAME
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(acked, indent=1, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, path)


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
    batch is an audited no-op, never an empty send. The whole
    post-marker path — ack load, export, send, ack save —
    lives inside one audited envelope: any exception becomes
    an audited error result, never an escaping raise."""
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
    try:
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
                  "(verdict_sealed / mission_ratified / "
                  "skill_verified) exported from the cognitive "
                  "memory store and shipped by "
                  "ace_operational.self_send under the ratified "
                  "governance (draft only, marker-gated)."))
        if result.sent:
            # Ack only a fully verified send (PR verified AND
            # the final audit row landed); anything less is
            # retried by a later flush, never silently dropped.
            for rid in ids:
                acked[rid] = {"branch": result.branch,
                              "pr_number": result.pr_number,
                              "ts": today.isoformat()}
            _save_acked(home, acked)
        return result
    except Exception as exc:
        row = _audit_row(when=today.isoformat(),
                         trigger="ratification_batch_flush",
                         branch="", digest="", files=[],
                         pr_number=None,
                         outcome=f"error:{type(exc).__name__}")
        _append_local_audit(home, row)
        return SendResult(
            False, f"error:{type(exc).__name__}:{str(exc)[:120]}")


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
