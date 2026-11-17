#!/usr/bin/env python3
"""Verifikator direktori staging terhadap manifest berkas (sha256 + ukuran).

Memeriksa sebuah direktori staging terhadap manifest JSON dan melaporkan
berkas yang hilang (`missing`), berlebih (`extra`), atau berubah (`modified`)
beserta status keluar yang jelas untuk dipakai pada alur staging ACE.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
from typing import Any

STAGE_SCHEMA = "ace.stage-verify.v1"


class StageVerifyError(ValueError):
    """Kesalahan direktori staging, berkas manifest, atau entri tidak sah."""


@dataclass(frozen=True)
class ManifestEntry:
    """Satu entri berkas yang diharapkan pada direktori staging."""

    path: str
    sha256: str
    size: int | None


def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while chunk := fp.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _normalize_rel_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise StageVerifyError("Path entri manifest harus berupa string tidak kosong yang sah.")
    cleaned = raw.replace("\\", "/").strip()
    if cleaned.startswith("/") or (len(cleaned) >= 2 and cleaned[1] == ":"):
        raise StageVerifyError(f"Path manifest tidak boleh absolut: {raw!r}")
    posix = PurePosixPath(cleaned)
    if ".." in posix.parts or "." in posix.parts:
        raise StageVerifyError(f"Path manifest mengandung segmen tidak sah: {raw!r}")
    return posix.as_posix()


def _parse_manifest(manifest_path: Path) -> list[ManifestEntry]:
    if not manifest_path.is_file():
        raise StageVerifyError(f"Berkas manifest tidak ditemukan: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise StageVerifyError(f"Gagal membaca manifest '{manifest_path}': {exc}") from exc

    if not isinstance(payload, dict):
        raise StageVerifyError("Manifest harus berupa objek JSON.")

    entries: list[ManifestEntry] = []
    seen: set[str] = set()

    raw_files = payload.get("files")
    if isinstance(raw_files, list):
        items: list[tuple[str, Any]] = []
        for idx, item in enumerate(raw_files):
            if not isinstance(item, dict):
                raise StageVerifyError(f"Entri manifest pada indeks {idx} wajib berupa objek.")
            raw_path = item.get("path") if "path" in item else item.get("name")
            if not isinstance(raw_path, str):
                raise StageVerifyError(f"Entri manifest indeks {idx} tidak memiliki 'path'.")
            items.append((raw_path, item))
    elif isinstance(raw_files, dict):
        items = list(raw_files.items())
    else:
        raise StageVerifyError("Manifest harus memiliki field 'files' berupa daftar atau objek.")

    for raw_path, meta in items:
        rel_path = _normalize_rel_path(raw_path)
        if rel_path in seen:
            raise StageVerifyError(f"Duplikat path pada manifest: {rel_path}")
        seen.add(rel_path)

        if isinstance(meta, str):
            sha = meta.strip().lower()
            size = None
        elif isinstance(meta, dict):
            raw_sha = meta.get("sha256")
            if not isinstance(raw_sha, str) or len(raw_sha.strip()) != 64:
                raise StageVerifyError(f"Nilai sha256 tidak sah untuk '{rel_path}'.")
            sha = raw_sha.strip().lower()
            try:
                int(sha, 16)
            except ValueError as exc:
                raise StageVerifyError(f"Nilai sha256 bukan heksadesimal untuk '{rel_path}'.") from exc

            raw_size = meta.get("size") if "size" in meta else meta.get("size_bytes")
            if raw_size is None:
                size = None
            elif isinstance(raw_size, int) and not isinstance(raw_size, bool) and raw_size >= 0:
                size = raw_size
            else:
                raise StageVerifyError(f"Nilai ukuran tidak sah untuk '{rel_path}'.")
        else:
            raise StageVerifyError(f"Metadata manifest tidak sah untuk '{rel_path}'.")

        entries.append(ManifestEntry(path=rel_path, sha256=sha, size=size))

    entries.sort(key=lambda e: e.path)
    return entries


def _scan_stage_files(stage_dir: Path, manifest_resolved: Path) -> dict[str, Path]:
    root = stage_dir.resolve()
    actual: dict[str, Path] = {}
    for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur = Path(current_dir)
        for name in filenames:
            p = cur / name
            if p.is_symlink():
                raise StageVerifyError(f"Symlink tidak diizinkan dalam direktori staging: {p}")
            if p.resolve() == manifest_resolved:
                continue
            rel = p.relative_to(root).as_posix()
            actual[rel] = p
    return actual


def verify_stage(stage_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Verifikasi `stage_dir` terhadap `manifest_path` dan kembalikan laporan ringkas."""
    if not stage_dir.is_dir():
        raise StageVerifyError(f"Direktori staging tidak ditemukan: {stage_dir}")

    resolved_stage = stage_dir.resolve()
    target_manifest = (
        manifest_path if manifest_path is not None else resolved_stage / "manifest.json"
    )
    manifest_resolved = target_manifest.resolve()

    expected_entries = _parse_manifest(target_manifest)
    expected_map = {entry.path: entry for entry in expected_entries}
    actual_map = _scan_stage_files(resolved_stage, manifest_resolved)

    missing = sorted(p for p in expected_map if p not in actual_map)
    extra = sorted(p for p in actual_map if p not in expected_map)
    modified: list[dict[str, Any]] = []

    for rel_path in sorted(set(expected_map) & set(actual_map)):
        exp = expected_map[rel_path]
        disk_path = actual_map[rel_path]
        actual_size = disk_path.stat().st_size
        actual_sha = _sha256_file(disk_path)
        size_mismatch = exp.size is not None and actual_size != exp.size
        sha_mismatch = actual_sha != exp.sha256
        if size_mismatch or sha_mismatch:
            modified.append(
                {
                    "path": rel_path,
                    "expected_sha256": exp.sha256,
                    "actual_sha256": actual_sha,
                    "expected_size": exp.size,
                    "actual_size": actual_size,
                    "reasons": [
                        r
                        for r, flag in (("sha256_mismatch", sha_mismatch), ("size_mismatch", size_mismatch))
                        if flag
                    ],
                }
            )

    valid = not (missing or extra or modified)
    return {
        "schema": STAGE_SCHEMA,
        "valid": valid,
        "stage_dir": str(resolved_stage),
        "manifest": str(manifest_resolved),
        "expected_count": len(expected_entries),
        "actual_count": len(actual_map),
        "missing": missing,
        "extra": extra,
        "modified": modified,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verifikasi direktori staging ACE terhadap manifest (filename + sha256 + size)."
    )
    parser.add_argument("stage_dir", type=Path, help="Direktori staging yang akan diverifikasi.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path berkas manifest JSON (default: <stage_dir>/manifest.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI verifikator staging."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = verify_stage(args.stage_dir, args.manifest)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, StageVerifyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
