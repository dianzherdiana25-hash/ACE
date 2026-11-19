#!/usr/bin/env python3
"""Audit checkpoint JSON dan riwayat branch dari objek Git lokal."""
from __future__ import annotations

import argparse
from collections.abc import Iterable
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import subprocess


_MISSING = object()
_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_ARRAY_INDEX = re.compile(r"0|[1-9][0-9]*")
_JSON_TYPES = {
    dict: "object",
    list: "array",
    str: "string",
    bool: "boolean",
    int: "number",
    Decimal: "number",
    type(None): "null",
}


class AuditError(ValueError):
    """Masukan audit atau objek Git lokal tidak dapat diperiksa."""


class GitRepository:
    def __init__(self, path: Path):
        self.path = path
        self.env = {
            **os.environ,
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_LAZY_FETCH": "1",
        }
        # Opsi --repo menentukan sumber audit walau dipanggil dari dalam hook Git.
        for name in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        ):
            self.env.pop(name, None)

    def run(self, *args: str, allowed_codes: tuple[int, ...] = (0,)):
        result = subprocess.run(
            ["git", "--no-replace-objects", "--literal-pathspecs", "-C", str(self.path), *args],
            env=self.env, capture_output=True, check=False,
        )
        if result.returncode not in allowed_codes:
            raise AuditError(f"Git {args[0]} gagal pada objek lokal.")
        return result

    def commit(self, revision: str) -> str:
        result = self.run("rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")
        return result.stdout.decode("ascii").strip()

    def blob_id(self, commit: str, path: str) -> str | None:
        entry = self.run("ls-tree", "-z", "--full-tree", commit, "--", path).stdout
        if not entry:
            return None
        metadata, name = entry[:-1].split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        if kind != "blob" or mode not in {"100644", "100755"} or os.fsdecode(name) != path:
            raise AuditError("Checkpoint wajib berupa berkas JSON reguler pada revisi tersebut.")
        return oid

    def checkpoint(self, oid: str | None):
        if oid is None:
            return _MISSING
        data = self.run("cat-file", "blob", oid).stdout
        try:
            return json.loads(data, parse_float=Decimal, parse_constant=_invalid_constant,
                              object_pairs_hook=_unique_object)
        except (ValueError, ArithmeticError, RecursionError) as exc:
            raise AuditError("Isi checkpoint bukan JSON yang dapat diaudit.") from exc


def _invalid_constant(_value: str):
    raise ValueError("Konstanta JSON nonfinit.")


def _unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("Field JSON ganda.")
    return value


def _checkpoint_path(path: str) -> str:
    if not path.endswith(".json") or any(part in ("", ".", "..") for part in path.split("/")):
        raise AuditError("Gunakan jalur checkpoint .json relatif terhadap akar repo.")
    if "\\" in path or any(ord(char) < 32 for char in path):
        raise AuditError("Jalur checkpoint mengandung karakter yang tidak sah.")
    return path


def _type_name(value) -> str:
    return "missing" if value is _MISSING else _JSON_TYPES[type(value)]


def _equal(left, right) -> bool:
    kind = _type_name(left)
    if kind != _type_name(right):
        return False
    if kind == "object":
        return left.keys() == right.keys() and all(_equal(value, right[key]) for key, value in left.items())
    if kind == "array":
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _change(pointer: str, before, after) -> dict:
    if before is _MISSING:
        status = "added"
    elif after is _MISSING:
        status = "removed"
    else:
        status = "modified"
    return {"field": pointer, "status": status, "before_type": _type_name(before),
            "after_type": _type_name(after)}


def _diff_fields(before, after, pointer: str = "") -> Iterable[dict]:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            token = key.replace("~", "~0").replace("/", "~1")
            yield from _diff_fields(before.get(key, _MISSING), after.get(key, _MISSING),
                                    f"{pointer}/{token}")
    elif not _equal(before, after):
        yield _change(pointer, before, after)


def diff_checkpoints(repo: GitRepository, before: str, after: str, path: str) -> dict:
    """Bandingkan isi checkpoint pada dua commit dan ringkas perubahan per field."""
    path = _checkpoint_path(path)
    left, right = repo.commit(before), repo.commit(after)
    left_blob, right_blob = repo.blob_id(left, path), repo.blob_id(right, path)
    old = repo.checkpoint(left_blob)
    new = old if left_blob == right_blob else repo.checkpoint(right_blob)
    changes = list(_diff_fields(old, new))
    counts = {"added": 0, "removed": 0, "modified": 0}
    for item in changes:
        counts[item["status"]] += 1
    return {
        "schema": "ace.self-dev-checkpoint-diff.v1",
        "path": path,
        "before": left,
        "after": right,
        "present_before": left_blob is not None,
        "present_after": right_blob is not None,
        "counts": counts,
        "changes": changes,
    }


def _pointer_tokens(pointer: str) -> list[str]:
    if not pointer:
        return []
    if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        raise AuditError("Field wajib berupa JSON Pointer yang sah.")
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]


def _field_value(value, tokens: list[str]):
    for token in tokens:
        if isinstance(value, dict):
            value = value.get(token, _MISSING)
        elif isinstance(value, list) and _ARRAY_INDEX.fullmatch(token):
            if not value or len(token) > len(str(len(value) - 1)):
                return _MISSING
            index = int(token)
            value = value[index] if index < len(value) else _MISSING
        else:
            return _MISSING
    return value


def field_history(repo: GitRepository, base: str, tip: str, path: str, pointer: str) -> dict:
    """Telusuri perubahan field setelah base melalui jalur induk pertama tip."""
    path = _checkpoint_path(path)
    tokens = _pointer_tokens(pointer)
    base_commit, tip_commit = repo.commit(base), repo.commit(tip)
    rows = repo.run(
        "log", "--no-show-signature", "--first-parent", "--reverse", "--format=%H%x09%cI",
        f"{base_commit}..{tip_commit}", "--",
    ).stdout.decode("ascii").splitlines()
    if base_commit != tip_commit:
        first_commit = rows[0].split("\t")[0] if rows else None
        parent = repo.commit(f"{first_commit}^1") if first_commit else None
        if parent != base_commit:
            raise AuditError("Base harus berada pada jalur induk pertama tip.")

    previous_blob = repo.blob_id(base_commit, path)
    previous = _field_value(repo.checkpoint(previous_blob), tokens)
    changes = []
    for row in rows:
        commit, committed_at = row.split("\t")
        blob = repo.blob_id(commit, path)
        if blob == previous_blob:
            continue
        current = _field_value(repo.checkpoint(blob), tokens)
        if not _equal(previous, current):
            changes.append({"commit": commit, "committed_at": committed_at,
                            **_change(pointer, previous, current)})
        previous_blob, previous = blob, current

    return {
        "schema": "ace.self-dev-field-history.v1",
        "path": path,
        "field": pointer,
        "base": base_commit,
        "tip": tip_commit,
        "commits_examined": len(rows),
        "changes": changes,
    }


def guard_branch(repo: GitRepository, base: str, tip: str, expected: Iterable[str]) -> dict:
    """Bandingkan seluruh commit di luar base dengan daftar ID commit kerja."""
    expected_ids = list(expected)
    if any(not _OBJECT_ID.fullmatch(oid) for oid in expected_ids):
        raise AuditError("Setiap commit ekspektasi wajib berupa ID objek Git penuh.")
    expected_set = set(expected_ids)
    if len(expected_set) != len(expected_ids):
        raise AuditError("Daftar ekspektasi memuat commit ganda.")
    if repo.run("rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        raise AuditError("Riwayat Git dangkal tidak cukup untuk memeriksa seluruh leluhur branch.")
    base_commit, tip_commit = repo.commit(base), repo.commit(tip)
    base_is_ancestor = repo.run(
        "merge-base", "--is-ancestor", base_commit, tip_commit, allowed_codes=(0, 1),
    ).returncode == 0
    actual = repo.run("rev-list", "--topo-order", "--reverse",
                      f"{base_commit}..{tip_commit}").stdout.decode("ascii").splitlines()
    unexpected = [commit for commit in actual if commit not in expected_set]
    missing = sorted(expected_set - set(actual))
    return {
        "schema": "ace.self-dev-branch-guard.v1",
        "base": base_commit,
        "tip": tip_commit,
        "base_is_ancestor": base_is_ancestor,
        "commit_count": len(actual),
        "unexpected": unexpected,
        "missing_expected": missing,
        "clean": base_is_ancestor and not unexpected and not missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Akar checkout Git lokal.")
    commands = parser.add_subparsers(dest="command", required=True)

    diff = commands.add_parser("diff", help="Ringkas perbedaan dua checkpoint.")
    diff.add_argument("path", help="Jalur checkpoint JSON relatif terhadap akar repo.")
    diff.add_argument("--before", required=True)
    diff.add_argument("--after", required=True)

    history = commands.add_parser("history", help="Telusuri perubahan sebuah field.")
    history.add_argument("path", help="Jalur checkpoint JSON relatif terhadap akar repo.")
    history.add_argument("--field", required=True, help="JSON Pointer, misalnya /cycle/status.")
    history.add_argument("--base", required=True)
    history.add_argument("--tip", required=True)

    guard = commands.add_parser("guard", help="Periksa seluruh commit di luar base.")
    guard.add_argument("--base", required=True)
    guard.add_argument("--tip", required=True)
    guard.add_argument("--expect", action="append", default=[], help="ID penuh commit yang diharapkan.")

    args = parser.parse_args(argv)
    repo = GitRepository(args.repo)
    try:
        if args.command == "diff":
            result = diff_checkpoints(repo, args.before, args.after, args.path)
        elif args.command == "history":
            result = field_history(repo, args.base, args.tip, args.path, args.field)
        else:
            result = guard_branch(repo, args.base, args.tip, args.expect)
    except AuditError as exc:
        parser.exit(2, f"Error: {exc}\n")
    except (OSError, UnicodeError, RecursionError):
        parser.exit(2, "Error membaca checkpoint atau objek Git lokal.\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("clean", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
