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

    def run(self, *args: str, allowed_codes: tuple[int, ...] = (0,), input_bytes: bytes | None = None):
        result = subprocess.run(
            ["git", "--no-replace-objects", "--literal-pathspecs", "-C", str(self.path), *args],
            env=self.env, input=input_bytes, capture_output=True, check=False,
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


PREREVIEW_SCHEMA = "ace.self-dev-branch-prereview.v1"


def _commit_parents_and_subject(repo: GitRepository, oid: str) -> tuple[list[str], str]:
    raw = repo.run("show", "-s", "--no-show-signature", "--format=%P%n%s", "--end-of-options", oid).stdout
    lines = raw.decode("utf-8", errors="replace").splitlines()
    parents = lines[0].split() if lines and lines[0].strip() else []
    subject = lines[1] if len(lines) > 1 else ""
    return parents, subject


def _commit_patch_id(repo: GitRepository, oid: str) -> str | None:
    patch_bytes = repo.run("diff-tree", "--root", "--no-commit-id", "-p", "--binary", "--end-of-options", oid).stdout
    if not patch_bytes.strip():
        return None
    out = repo.run("patch-id", "--stable", input_bytes=patch_bytes).stdout.decode("ascii", errors="replace").strip()
    if not out:
        return None
    return out.split()[0]


def pre_review_report(
    repo: GitRepository,
    base: str,
    tip: str,
    pinned_commits: Iterable[str],
    *,
    checkpoint_paths: Iterable[str] = (),
) -> dict:
    """Buat laporan pra-review branch dari commit terpin operator, cherry-pick, merge, dan diff checkpoint."""
    pinned_ids = list(pinned_commits)
    if any(not _OBJECT_ID.fullmatch(oid) for oid in pinned_ids):
        raise AuditError("Setiap commit terpin operator wajib berupa ID objek Git penuh.")
    if len(set(pinned_ids)) != len(pinned_ids):
        raise AuditError("Daftar commit terpin memuat ID ganda.")
    if repo.run("rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        raise AuditError("Riwayat Git dangkal tidak cukup untuk laporan pra-review branch.")

    base_commit, tip_commit = repo.commit(base), repo.commit(tip)
    # Pastikan setiap commit terpin memang ada pada objek Git lokal
    for pid in pinned_ids:
        if repo.commit(pid) != pid:
            raise AuditError(f"Commit terpin tidak menunjuk commit valid: {pid}.")

    base_is_ancestor = repo.run(
        "merge-base", "--is-ancestor", base_commit, tip_commit, allowed_codes=(0, 1),
    ).returncode == 0
    actual_commits = repo.run(
        "rev-list", "--topo-order", "--reverse", f"{base_commit}..{tip_commit}",
    ).stdout.decode("ascii").splitlines()

    pinned_set = set(pinned_ids)
    actual_set = set(actual_commits)

    matched_pinned = [c for c in actual_commits if c in pinned_set]
    unmatched_actual = [c for c in actual_commits if c not in pinned_set]
    unmatched_pinned = [c for c in pinned_ids if c not in actual_set]

    # Indeks patch-id untuk mencocokkan cherry-pick pada commit non-merge
    pinned_by_patch: dict[str, list[str]] = {}
    for pid in unmatched_pinned:
        p_parents, _ = _commit_parents_and_subject(repo, pid)
        if len(p_parents) <= 1:
            patch_id = _commit_patch_id(repo, pid)
            if patch_id is not None:
                pinned_by_patch.setdefault(patch_id, []).append(pid)

    merge_commits = []
    cherry_picked_equivalents = []
    unexpected_commits = []
    matched_via_patch = set()

    for oid in actual_commits:
        parents, subject = _commit_parents_and_subject(repo, oid)
        is_merge = len(parents) > 1
        if is_merge:
            merge_commits.append({
                "commit": oid,
                "parents": parents,
                "pinned_exact": oid in pinned_set,
                "subject": subject,
            })
        if oid in pinned_set:
            continue
        if not is_merge:
            patch_id = _commit_patch_id(repo, oid)
            candidates = [p for p in pinned_by_patch.get(patch_id, []) if p not in matched_via_patch] if patch_id else []
            if candidates:
                matched_pid = candidates[0]
                matched_via_patch.add(matched_pid)
                cherry_picked_equivalents.append({
                    "actual_commit": oid,
                    "matched_pinned_commit": matched_pid,
                    "patch_id": patch_id,
                    "subject": subject,
                })
                continue
        unexpected_commits.append({"commit": oid, "is_merge": is_merge, "parents": parents, "subject": subject})

    missing_pinned_commits = sorted(set(unmatched_pinned) - matched_via_patch)

    changed_raw = repo.run(
        "diff-tree", "--no-commit-id", "--name-status", "-r", "--end-of-options", base_commit, tip_commit,
    ).stdout.decode("utf-8", errors="replace").splitlines()
    changed_files = []
    for row in changed_raw:
        if "\t" in row:
            status_code, rel_path = row.split("\t", 1)
            changed_files.append({"status": status_code, "path": rel_path})
    changed_files.sort(key=lambda item: item["path"])

    checkpoint_diffs = [
        diff_checkpoints(repo, base_commit, tip_commit, cp_path)
        for cp_path in checkpoint_paths
    ]

    strict_oid_clean = base_is_ancestor and not unmatched_actual and not unmatched_pinned
    unexpected_non_merge = [item for item in unexpected_commits if not item["is_merge"]]
    patch_equivalent_clean = (
        base_is_ancestor
        and not unexpected_non_merge
        and not missing_pinned_commits
    )
    if strict_oid_clean:
        history_shape = "merge_clean" if merge_commits else "linear_exact"
    elif cherry_picked_equivalents and patch_equivalent_clean:
        history_shape = "cherry_pick_with_merge" if merge_commits else "cherry_pick_equivalent"
    elif merge_commits:
        history_shape = "merge_diverged"
    else:
        history_shape = "diverged"

    return {
        "schema": PREREVIEW_SCHEMA,
        "base": base_commit,
        "tip": tip_commit,
        "base_is_ancestor": base_is_ancestor,
        "history_shape": history_shape,
        "pinned_count": len(pinned_ids),
        "actual_commit_count": len(actual_commits),
        "matched_pinned": matched_pinned,
        "cherry_picked_equivalents": cherry_picked_equivalents,
        "merge_commits": merge_commits,
        "unexpected_commits": unexpected_commits,
        "missing_pinned_commits": missing_pinned_commits,
        "changed_files": changed_files,
        "checkpoint_diffs": checkpoint_diffs,
        "strict_oid_clean": strict_oid_clean,
        "patch_equivalent_clean": patch_equivalent_clean,
        "clean": strict_oid_clean,
    }


def _load_pinned_commits(spec_path: Path) -> list[str]:
    try:
        raw = json.loads(spec_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise AuditError(f"Berkas daftar commit terpin tidak dapat dibaca: {exc}") from exc
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("pinned_commits"), list):
        return raw["pinned_commits"]
    raise AuditError("Berkas pin harus berupa array JSON atau objek berisi 'pinned_commits'.")


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

    prereview = commands.add_parser("prereview", help="Buat laporan pra-review branch dari commit terpin.")
    prereview.add_argument("--base", required=True)
    prereview.add_argument("--tip", required=True)
    prereview.add_argument("--expect", action="append", default=[], help="ID penuh commit yang dipin operator.")
    prereview.add_argument("--pin-file", type=Path, help="Berkas JSON berisi array atau pinned_commits.")
    prereview.add_argument("--checkpoint", action="append", default=[], help="Jalur checkpoint JSON untuk diringkas.")

    args = parser.parse_args(argv)
    repo = GitRepository(args.repo)
    try:
        if args.command == "diff":
            result = diff_checkpoints(repo, args.before, args.after, args.path)
        elif args.command == "history":
            result = field_history(repo, args.base, args.tip, args.path, args.field)
        elif args.command == "guard":
            result = guard_branch(repo, args.base, args.tip, args.expect)
        else:
            pinned = list(args.expect)
            if args.pin_file is not None:
                pinned.extend(_load_pinned_commits(args.pin_file))
            result = pre_review_report(
                repo, args.base, args.tip, pinned, checkpoint_paths=args.checkpoint,
            )
    except AuditError as exc:
        parser.exit(2, f"Error: {exc}\n")
    except (OSError, UnicodeError, RecursionError):
        parser.exit(2, "Error membaca checkpoint atau objek Git lokal.\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get("clean", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
