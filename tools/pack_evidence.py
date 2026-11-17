#!/usr/bin/env python3
"""Perakit dan pemverifikasi bundel evidence satu run ACE (`manifest.json`).

Mode dasar merakit daftar seluruh berkas pada direktori run (jalur relatif POSIX,
ukuran byte, dan digest SHA-256) ke dalam `manifest.json`. Mode `--verify`
memverifikasi ulang bundel terhadap `manifest.json` dan keluar dengan kode 2
apabila ada berkas yang berubah atau hilang.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

BUNDLE_SCHEMA = "ace.evidence-bundle.v1"
DEFAULT_MANIFEST_NAME = "manifest.json"


class EvidencePackError(ValueError):
    """Kesalahan masukan, path, atau manifest bundel evidence tidak sah."""


def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while chunk := fp.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _iter_bundle_files(root: Path, manifest_rel: str) -> list[Path]:
    """Kumpulkan semua berkas reguler secara deterministik, tolak symlink keluar."""
    root_resolved = root.resolve()
    collected: list[Path] = []
    for current_dir, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur_path = Path(current_dir)
        for name in filenames:
            candidate = cur_path / name
            if candidate.is_symlink():
                raise EvidencePackError(f"Symlink tidak diizinkan dalam bundel evidence: {candidate}")
            rel = candidate.relative_to(root_resolved).as_posix()
            if rel == manifest_rel:
                continue
            collected.append(candidate)
    collected.sort(key=lambda p: p.relative_to(root_resolved).as_posix())
    return collected


def _atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
    tmp_path = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        tmp_path.write_text(raw, encoding="utf-8")
        os.replace(tmp_path, target)
    except OSError as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise EvidencePackError(f"Gagal menulis manifest '{target}': {exc}") from exc


def pack_evidence(run_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Rakit bundel evidence pada `run_dir` dan tulis `manifest.json`."""
    if not run_dir.is_dir():
        raise EvidencePackError(f"Direktori run tidak ditemukan: {run_dir}")

    root_resolved = run_dir.resolve()
    target_manifest = (manifest_path or (root_resolved / DEFAULT_MANIFEST_NAME)).resolve()
    try:
        manifest_rel = target_manifest.relative_to(root_resolved).as_posix()
    except ValueError:
        manifest_rel = ""

    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for file_path in _iter_bundle_files(root_resolved, manifest_rel):
        rel_posix = file_path.relative_to(root_resolved).as_posix()
        size_bytes = file_path.stat().st_size
        digest = _sha256_file(file_path)
        total_bytes += size_bytes
        entries.append(
            {
                "path": rel_posix,
                "size_bytes": size_bytes,
                "sha256": digest,
            }
        )

    manifest = {
        "schema": BUNDLE_SCHEMA,
        "bundle_name": root_resolved.name,
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "files": entries,
    }
    _atomic_write_json(target_manifest, manifest)
    return {
        "action": "pack",
        "manifest": str(target_manifest),
        "file_count": len(entries),
        "total_bytes": total_bytes,
    }


def verify_evidence(run_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Verifikasi bundel evidence terhadap `manifest.json` secara ketat."""
    if not run_dir.is_dir():
        raise EvidencePackError(f"Direktori run tidak ditemukan: {run_dir}")

    root_resolved = run_dir.resolve()
    source_manifest = (manifest_path or (root_resolved / DEFAULT_MANIFEST_NAME)).resolve()
    if not source_manifest.is_file():
        raise EvidencePackError(f"Manifest tidak ditemukan: {source_manifest}")

    try:
        manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidencePackError(f"Gagal membaca manifest '{source_manifest}': {exc}") from exc

    if not isinstance(manifest, dict) or manifest.get("schema") != BUNDLE_SCHEMA:
        raise EvidencePackError(f"Schema manifest tidak valid: {manifest.get('schema') if isinstance(manifest, dict) else type(manifest).__name__}")

    listed = manifest.get("files")
    if not isinstance(listed, list):
        raise EvidencePackError("Field 'files' pada manifest harus berupa daftar.")

    missing: list[str] = []
    modified: list[dict[str, Any]] = []
    expected_paths: set[str] = set()

    for idx, entry in enumerate(listed):
        if not isinstance(entry, dict):
            raise EvidencePackError(f"Entri manifest index {idx} bukan objek.")
        rel = entry.get("path")
        exp_size = entry.get("size_bytes")
        exp_sha = entry.get("sha256")
        if (
            not isinstance(rel, str)
            or not rel
            or isinstance(exp_size, bool)
            or not isinstance(exp_size, int)
            or not isinstance(exp_sha, str)
        ):
            raise EvidencePackError(f"Entri manifest index {idx} memiliki field tidak sah.")

        candidate = (root_resolved / rel).resolve()
        if not candidate.is_relative_to(root_resolved):
            raise EvidencePackError(f"Path manifest keluar dari direktori run: {rel}")

        expected_paths.add(rel)
        if not candidate.is_file():
            missing.append(rel)
            continue

        actual_size = candidate.stat().st_size
        actual_sha = _sha256_file(candidate)
        if actual_size != exp_size or actual_sha != exp_sha:
            modified.append(
                {
                    "path": rel,
                    "expected_size": exp_size,
                    "actual_size": actual_size,
                    "expected_sha256": exp_sha,
                    "actual_sha256": actual_sha,
                }
            )

    try:
        manifest_rel = source_manifest.relative_to(root_resolved).as_posix()
    except ValueError:
        manifest_rel = ""

    extra_files = [
        p.relative_to(root_resolved).as_posix()
        for p in _iter_bundle_files(root_resolved, manifest_rel)
        if p.relative_to(root_resolved).as_posix() not in expected_paths
    ]

    valid = len(missing) == 0 and len(modified) == 0
    return {
        "action": "verify",
        "manifest": str(source_manifest),
        "valid": valid,
        "checked_files": len(listed),
        "missing": missing,
        "modified": modified,
        "extra_files": extra_files,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Perakit dan pemverifikasi bundel evidence satu run ACE."
    )
    parser.add_argument("run_dir", type=Path, help="Direktori bundel evidence run")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path manifest.json kustom (default: <run_dir>/manifest.json)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verifikasi bundel terhadap manifest.json (exit 2 bila berubah/hilang)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI perakit/pemverifikasi bundel evidence."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.verify:
            result = verify_evidence(args.run_dir, manifest_path=args.manifest)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        result = pack_evidence(args.run_dir, manifest_path=args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except EvidencePackError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
