"""Prepare and validate an offline envelope for a human-reviewed draft PR."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path, PurePosixPath
import re
import subprocess

SCHEMA = "ace.draft-preflight.v1"
COMMIT = re.compile(r"[a-f0-9]{40}")
BRANCH = re.compile(r"ace-auto/(\d{8})-([a-z0-9][a-z0-9-]{0,40})")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
DENIED = ("ledger", "utang", "secret", "credential", ".env", "token", "id_rsa",
          ".pem", ".key", "prereg", "sealed", "evo_0007", "evo-0007")


def _git(root, *args):
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True, timeout=30, check=False,
    )
    if result.returncode:
        raise ValueError(f"local git check failed: {args[0]}")
    return result.stdout


def _check_identity(repository, branch, base, head):
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise ValueError("invalid repository identity")
    match = BRANCH.fullmatch(branch) if isinstance(branch, str) else None
    if not match:
        raise ValueError("invalid draft branch")
    stamp = match.group(1)
    date.fromisoformat(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}")
    if any(not isinstance(value, str) or not COMMIT.fullmatch(value) for value in (base, head)):
        raise ValueError("base and head must be full commit hashes")
    if base == head:
        raise ValueError("empty draft")


def _files(root, base, head):
    for commit in (base, head):
        if _git(root, "cat-file", "-t", commit) != b"commit\n":
            raise ValueError("pin is not a commit")
    _git(root, "merge-base", "--is-ancestor", base, head)
    fields = _git(root, "diff", "--no-renames", "--name-status", "-z", base, head).split(b"\0")
    if fields.pop() != b"" or not fields or len(fields) % 2:
        raise ValueError("no eligible changed paths")
    entries = []
    for status, raw_path in zip(fields[::2], fields[1::2]):
        path = raw_path.decode("utf-8")
        lower = path.lower()
        if (status not in (b"A", b"M") or not path.startswith(("handover/", "evidence/"))
                or any(word in lower for word in DENIED)
                or any(part.startswith(".") for part in PurePosixPath(path).parts)
                or any(ord(character) < 32 for character in path) or "\\" in path):
            raise ValueError("changed path or operation outside offline preflight scope")
        spec = f"{head}:{path}"
        tree = _git(root, "ls-tree", "-z", head, "--", path)
        if not tree.startswith((b"100644 blob ", b"100755 blob ")):
            raise ValueError("changed path is not an ordinary file")
        size = int(_git(root, "cat-file", "-s", spec))
        if size > 1024 * 1024:
            raise ValueError("changed blob exceeds preflight size limit")
        payload = _git(root, "cat-file", "blob", spec)
        entries.append({"path": path, "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest()})
    return sorted(entries, key=lambda item: item["path"])


def prepare(root, *, repository, branch, base, head):
    _check_identity(repository, branch, base, head)
    return {
        "schema": SCHEMA, "repository": repository, "branch": branch, "base_branch": "main",
        "base_sha": base, "head_sha": head, "draft": True,
        "human_approval_required": True, "files": _files(root, base, head),
    }


def validate(root, envelope, *, repository, base):
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be an object")
    if envelope.get("repository") != repository or envelope.get("base_sha") != base:
        raise ValueError("envelope target or pinned base differs from trusted input")
    if envelope.get("draft") is not True or envelope.get("human_approval_required") is not True:
        raise ValueError("draft and human review flags must be boolean true")
    expected = prepare(root, repository=repository, branch=envelope.get("branch"),
                       base=base, head=envelope.get("head_sha"))
    # Compare serialized values to keep booleans and integers distinct.
    if json.dumps(envelope, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("envelope differs from the pinned local diff")
    return {"ready_for_human_review": True, "send_authorized": False,
            "envelope_sha256": hashlib.sha256(
                json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()}


def _unique_keys(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("duplicate envelope key")
        values[key] = value
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--repository", required=True)
    parser.add_argument("--base", required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    build = sub.add_parser("prepare")
    build.add_argument("--head", required=True)
    build.add_argument("--branch", required=True)
    check = sub.add_parser("validate")
    check.add_argument("envelope", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "prepare":
            report = prepare(args.root, repository=args.repository, branch=args.branch,
                             base=args.base, head=args.head)
        else:
            data = json.loads(args.envelope.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
            report = validate(args.root, data, repository=args.repository, base=args.base)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"preflight: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
