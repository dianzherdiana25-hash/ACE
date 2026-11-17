#!/usr/bin/env python3
"""Pemindai utang penyimpanan / artefak belum tersinkron ke Git (WS-E #14).

Membandingkan berkas pada `--workspace` terhadap daftar terlacak Git (`git ls-files -s`)
dan blob Git SHA-1 (`git hash-object`) untuk mendeteksi berkas `untracked` maupun
`modified`, serta menghitung ukuran & SHA-256 lalu mengelompokkannya menurut
program/area (`ace.storage-debt.v1`, kompatibel langsung dengan Dashboard v2 WS-E #13).
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

STORAGE_DEBT_SCHEMA = "ace.storage-debt.v1"
DEFAULT_SKIP_DIRS = frozenset({".git", "__pycache__", ".venv", "venv", ".pytest_cache"})


class StorageDebtError(ValueError):
    """Kesalahan repositori Git, path workspace, atau konfigurasi CLI storage debt."""


def _git_blob_id(content: bytes) -> str:
    header = b"blob " + str(len(content)).encode("ascii") + b"\0"
    return hashlib.sha1(header + content).hexdigest()


def _infer_program(rel_posix: str, program_map: dict[str, str] | None = None) -> str:
    parts = rel_posix.split("/")
    if program_map:
        for prefix, prog in sorted(program_map.items(), key=lambda kv: len(kv[0]), reverse=True):
            if rel_posix.startswith(prefix):
                return prog
    if len(parts) == 1:
        return "root"
    head = parts[0]
    if head == "code" and len(parts) >= 2:
        return f"code/{parts[1]}"
    return head


def _read_git_tracked_blobs(repo_root: Path) -> dict[str, str]:
    """Baca peta `{rel_posix: git_blob_sha1}` dari `git ls-files -s`."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-s", "-z"],
            cwd=str(repo_root),
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StorageDebtError(f"Gagal membaca indeks Git pada '{repo_root}': {exc}") from exc

    tracked: dict[str, str] = {}
    for entry in proc.stdout.split(b"\0"):
        if not entry:
            continue
        meta, _, path_bytes = entry.partition(b"\t")
        if not path_bytes:
            continue
        meta_parts = meta.decode("ascii", errors="replace").split()
        if len(meta_parts) >= 2:
            rel_path = path_bytes.decode("utf-8", errors="surrogateescape")
            tracked[rel_path] = meta_parts[1]
    return tracked


def _read_unpushed_commits(repo_root: Path) -> list[str]:
    """Opsional cek commit lokal yang belum di-push ke upstream (read-only)."""
    try:
        proc = subprocess.run(
            ["git", "log", "--oneline", "@{u}..HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except OSError:
        return []


def scan_storage_debt(
    workspace: Path,
    *,
    repo_root: Path | None = None,
    program_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Pindai berkas workspace dan laporkan utang artefak belum di-commit/tersinkron."""
    ws = workspace.resolve()
    if not ws.is_dir():
        raise StorageDebtError(f"Direktori workspace tidak ditemukan: {workspace}")
    git_root = (repo_root or workspace).resolve()
    if not (git_root / ".git").exists():
        raise StorageDebtError(f"Direktori bukan repositori Git (.git tidak ditemukan): {git_root}")

    tracked_blobs = _read_git_tracked_blobs(git_root)
    unpushed_commits = _read_unpushed_commits(git_root)

    program_files: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_debt_files = 0
    total_debt_bytes = 0
    untracked_count = 0
    modified_count = 0
    tracked_clean_count = 0

    for cur_dir, dirnames, filenames in os.walk(ws, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in DEFAULT_SKIP_DIRS)
        filenames.sort()
        cur = Path(cur_dir)
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            full_path = cur / name
            if full_path.is_symlink():
                continue
            rel = full_path.relative_to(ws).as_posix()
            raw = full_path.read_bytes()
            disk_blob = _git_blob_id(raw)
            expected_blob = tracked_blobs.get(rel)

            if expected_blob is None:
                status = "untracked"
                untracked_count += 1
            elif disk_blob != expected_blob:
                status = "modified"
                modified_count += 1
            else:
                tracked_clean_count += 1
                continue

            total_debt_files += 1
            total_debt_bytes += len(raw)
            prog = _infer_program(rel, program_map=program_map)
            program_files[prog].append(
                {
                    "path": rel,
                    "status": status,
                    "size_bytes": len(raw),
                    "git_blob": disk_blob,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )

    programs_out: dict[str, Any] = {}
    for prog in sorted(program_files):
        entries = sorted(program_files[prog], key=lambda item: item["path"])
        programs_out[prog] = {
            "file_count": len(entries),
            "total_bytes": sum(item["size_bytes"] for item in entries),
            "files": entries,
        }

    return {
        "schema": STORAGE_DEBT_SCHEMA,
        "workspace": str(ws),
        "repo_root": str(git_root),
        "summary": {
            "total_debt_files": total_debt_files,
            "total_debt_bytes": total_debt_bytes,
            "untracked_count": untracked_count,
            "modified_count": modified_count,
            "tracked_clean_count": tracked_clean_count,
            "unpushed_commit_count": len(unpushed_commits),
        },
        "unpushed_commits": unpushed_commits,
        "programs": programs_out,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def _load_program_map(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    if not path.is_file():
        raise StorageDebtError(f"Berkas --program-map tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageDebtError(f"Gagal membaca --program-map '{path}': {exc}") from exc
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise StorageDebtError("--program-map wajib objek JSON {prefix_path: nama_program}.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pemindai storage debt (berkas untracked/modified vs indeks Git) dikelompokkan per program."
    )
    parser.add_argument("--workspace", type=Path, required=True, help="Direktori workspace target pemindaian.")
    parser.add_argument("--repo", type=Path, default=None, help="Opsional direktori repo Git rujukan (default: --workspace).")
    parser.add_argument("--program-map", type=Path, default=None, help="Opsional JSON pemetaan prefix path -> nama program.")
    parser.add_argument("--out", type=Path, default=None, help="Path opsional berkas JSON keluaran.")
    args = parser.parse_args(argv)

    try:
        pmap = _load_program_map(args.program_map)
        report = scan_storage_debt(args.workspace, repo_root=args.repo, program_map=pmap)
    except StorageDebtError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        _atomic_write_text(args.out, rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
