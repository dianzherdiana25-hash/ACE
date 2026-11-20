#!/usr/bin/env python3
"""Buat inventaris successor dari path Git dan snapshot JSON yang ditunjuk."""

import argparse
import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess


PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:successor-0006|successor_6|s0006)(?![A-Za-z0-9])", re.I)


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"})


def _allowed(path):
    return not any(part in {".git", "secrets", "__pycache__"} or part.startswith(".env")
                   for part in path.parts)


def _record_entries(data, suffix):
    if suffix == ".jsonl":
        return [(number, json.loads(line)) for number, line in enumerate(data.splitlines(), 1)
                if line.strip()]
    payload = json.loads(data)
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        payload = payload["records"]
    return enumerate(payload if isinstance(payload, list) else [payload], 1)


def inventory(repo: Path, snapshot: Path) -> dict:
    if not snapshot.is_dir():
        raise ValueError("Snapshot harus berupa direktori.")
    branches = sorted(line for line in _git(repo, "branch", "-a", "--format=%(refname:short)")
                      .decode().splitlines() if PATTERN.search(line))
    files = []
    paths = _git(repo, "ls-files", "-z").decode().split("\0")
    for name in sorted(set(paths)):
        rel = Path(name)
        path = repo / rel
        if (PATTERN.search(name) and _allowed(rel) and path.is_file()
                and path.resolve() == repo.resolve() / rel):
            files.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    records = []
    for path in sorted(snapshot.rglob("*")):
        rel = path.relative_to(snapshot)
        if (not _allowed(rel) or not path.is_file() or path.suffix not in {".json", ".jsonl"}
                or path.resolve() != snapshot.resolve() / rel):
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        for number, record in _record_entries(data, path.suffix):
            if PATTERN.search(rel.as_posix()) or PATTERN.search(json.dumps(record, ensure_ascii=False)):
                records.append({"path": rel.as_posix(), "entry": number, "sha256": digest})
    return {"schema": "ace.successor-inventory.v1",
            "counts": {"branches": len(branches), "files": len(files), "records": len(records)},
            "branches": branches, "files": files, "records": records}


def markdown(result):
    lines = ["# Inventaris successor-0006", ""]
    for key in ("branches", "files", "records"):
        lines.extend([f"## {key} ({result['counts'][key]})", ""])
        for item in result[key]:
            if isinstance(item, str):
                lines.append(f"- {escape(item)}")
            else:
                suffix = f" · entri {item['entry']}" if "entry" in item else ""
                lines.append(f"- {escape(item['path'])}{suffix} · `{item['sha256']}`")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        target = args.output_dir.resolve()
        for source in (args.repo.resolve(), args.snapshot.resolve()):
            if target.is_relative_to(source) or source.is_relative_to(target):
                raise ValueError("Direktori keluaran harus terpisah dari masukan.")
        result = inventory(args.repo, args.snapshot)
        args.output_dir.mkdir()
        (args.output_dir / "inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "inventory.md").write_text(markdown(result), encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
