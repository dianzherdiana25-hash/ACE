#!/usr/bin/env python3
"""Perakit & pemverifikasi paket evidence run/stage berparameter ketat (`ace.run-evidence-pack.v1`).

Menggabungkan:
1. Pemeriksaan keutuhan staging opsional (`tools.stage_verify`).
2. Pemindaian kebocoran rahasia fail-closed sebelum perakitan (tolak kunci API / token nyata).
3. Pembuatan `manifest.json` (`tools.pack_evidence`) serta arsip `.tar.gz` deterministik opsional.
4. Mode `--verify` untuk mengecek integritas berkas run dan isi arsip tar terhadap path traversal/symlink.

Kontrak keamanan: tidak pernah memakai direktori staging default apa pun (pemanggil wajib
menyediakan `--run-dir` secara eksplisit).
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import pack_evidence as _pack
from tools import stage_verify as _stage_verify

RUN_PACK_SCHEMA = "ace.run-evidence-pack.v1"

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
    ("groq_api_key", re.compile(r"gsk_[0-9A-Za-z_]{16,}")),
    ("github_classic_pat", re.compile(r"ghp_[0-9A-Za-z]{20,}")),
    ("github_fine_pat", re.compile(r"github_pat_[0-9A-Za-z_]{20,}")),
    ("openai_like_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    (
        "bearer_or_token_assignment",
        re.compile(
            r"(?i)(?:api[_-]?key|auth[_-]?token|secret[_-]?key)\s*[:=]\s*['\"]([A-Za-z0-9._-]{24,})['\"]"
        ),
    ),
)

MAX_SECRET_SCAN_BYTES = 4 * 1024 * 1024


class RunEvidencePackError(ValueError):
    """Kesalahan validasi, kebocoran rahasia, arsip, atau verifikasi evidence run."""


def _categorize_artifact(rel_posix: str) -> str:
    ext = Path(rel_posix).suffix.lower()
    if ext == ".jsonl":
        return "jsonl"
    if ext == ".json":
        return "json"
    if ext in (".md", ".markdown", ".rst"):
        return "markdown"
    if ext in (".log", ".txt"):
        return "logs"
    return "other"


def scan_run_secrets(run_dir: Path, *, manifest_rel: str = "manifest.json") -> list[dict[str, Any]]:
    """Pindai berkas teks di `run_dir` terhadap pola kunci/rahasia tanpa membocorkan nilai mentah."""
    if not run_dir.is_dir():
        raise RunEvidencePackError(f"Direktori run tidak ditemukan: {run_dir}")
    root = run_dir.resolve()
    findings: list[dict[str, Any]] = []

    for cur_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur = Path(cur_dir)
        for fname in filenames:
            fpath = cur / fname
            if fpath.is_symlink():
                raise RunEvidencePackError(f"Symlink tidak diizinkan dalam direktori run: {fpath}")
            rel = fpath.relative_to(root).as_posix()
            if rel == manifest_rel:
                continue
            size = fpath.stat().st_size
            if size > MAX_SECRET_SCAN_BYTES:
                continue
            try:
                text = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                for rule_name, pattern in SECRET_PATTERNS:
                    m = pattern.search(line)
                    if m:
                        token = m.group(1) if m.lastindex else m.group(0)
                        masked = f"{token[:4]}***({len(token)}ch)"
                        findings.append(
                            {
                                "path": rel,
                                "line": line_no,
                                "rule": rule_name,
                                "redacted_preview": masked,
                            }
                        )
    return findings


def _sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while chunk := fp.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _create_deterministic_targz(source_dir: Path, archive_path: Path, *, extra_files: list[Path] | None = None) -> dict[str, Any]:
    root = source_dir.resolve()
    files: list[tuple[str, Path]] = []
    for cur_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur = Path(cur_dir)
        for fname in filenames:
            fp = cur / fname
            if fp.is_symlink():
                raise RunEvidencePackError(f"Symlink tidak boleh masuk arsip: {fp}")
            if fp.resolve() == archive_path.resolve():
                continue
            files.append((fp.relative_to(root).as_posix(), fp))

    if extra_files:
        for ef in extra_files:
            ef_res = ef.resolve()
            if ef_res.is_symlink():
                raise RunEvidencePackError(f"Symlink tidak boleh masuk arsip: {ef}")
            if not ef_res.is_relative_to(root):
                files.append((ef_res.name, ef_res))

    files.sort(key=lambda item: item[0])
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_archive = archive_path.with_name(f".{archive_path.name}.tmp.{os.getpid()}")

    try:
        with tmp_archive.open("wb") as raw_fp:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_fp, mtime=0) as gz_fp:
                with tarfile.open(fileobj=gz_fp, mode="w", format=tarfile.USTAR_FORMAT) as tf:
                    for arc_rel, disk_path in files:
                        data = disk_path.read_bytes()
                        ti = tarfile.TarInfo(name=arc_rel)
                        ti.size = len(data)
                        ti.mode = 0o644
                        ti.mtime = 0
                        ti.uid = 0
                        ti.gid = 0
                        ti.uname = ""
                        ti.gname = ""
                        tf.addfile(ti, io.BytesIO(data))
        os.replace(tmp_archive, archive_path)
    except (OSError, tarfile.TarError) as exc:
        if tmp_archive.exists():
            tmp_archive.unlink(missing_ok=True)
        raise RunEvidencePackError(f"Gagal menulis arsip '{archive_path}': {exc}") from exc

    return {
        "archive": str(archive_path.resolve()),
        "member_count": len(files),
        "sha256": _sha256_bytes(archive_path),
        "size_bytes": archive_path.stat().st_size,
    }


def _verify_archive_against_manifest(archive_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if not archive_path.is_file():
        raise RunEvidencePackError(f"Berkas arsip tidak ditemukan: {archive_path}")

    expected_map = {
        entry["path"]: (entry["size_bytes"], entry["sha256"])
        for entry in manifest.get("files", [])
    }
    member_digests: dict[str, tuple[int, str]] = {}
    manifest_in_tar: dict[str, Any] | None = None

    try:
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                raw_name = member.name
                if raw_name.startswith("/") or ".." in PurePosixPath(raw_name).parts:
                    raise RunEvidencePackError(f"Path member arsip tidak aman: {raw_name!r}")
                if member.issym() or member.islnk():
                    raise RunEvidencePackError(f"Member symlink/hardlink dilarang di arsip: {raw_name!r}")
                if not member.isfile():
                    continue
                fp = tf.extractfile(member)
                if fp is None:
                    raise RunEvidencePackError(f"Gagal mengekstrak member arsip: {raw_name}")
                payload = fp.read()
                if raw_name == "manifest.json":
                    manifest_in_tar = json.loads(payload.decode("utf-8"))
                else:
                    member_digests[raw_name] = (len(payload), hashlib.sha256(payload).hexdigest())
    except (OSError, tarfile.TarError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunEvidencePackError(f"Arsip rusak atau tidak valid '{archive_path}': {exc}") from exc

    missing_in_tar = sorted(p for p in expected_map if p not in member_digests)
    extra_in_tar = sorted(p for p in member_digests if p not in expected_map)
    modified_in_tar = [
        p
        for p in sorted(set(expected_map) & set(member_digests))
        if expected_map[p] != member_digests[p]
    ]
    manifest_match = manifest_in_tar == manifest
    tar_valid = not (missing_in_tar or extra_in_tar or modified_in_tar) and manifest_match
    return {
        "archive": str(archive_path.resolve()),
        "valid": tar_valid,
        "member_count": len(member_digests),
        "missing": missing_in_tar,
        "extra": extra_in_tar,
        "modified": modified_in_tar,
        "manifest_match": manifest_match,
    }


def pack_run_evidence(
    run_dir: Path,
    *,
    manifest_path: Path | None = None,
    archive_path: Path | None = None,
    meta_out: Path | None = None,
    stage_dir: Path | None = None,
    stage_manifest: Path | None = None,
    allow_unredacted: bool = False,
) -> dict[str, Any]:
    """Validasi stage opsional, pindai rahasia, segel `manifest.json`, dan buat arsip opsional."""
    if not run_dir.is_dir():
        raise RunEvidencePackError(f"Direktori run tidak ditemukan: {run_dir}")

    root = run_dir.resolve()
    target_manifest = (manifest_path or (root / _pack.DEFAULT_MANIFEST_NAME)).resolve()
    try:
        manifest_rel = target_manifest.relative_to(root).as_posix()
    except ValueError:
        manifest_rel = _pack.DEFAULT_MANIFEST_NAME

    stage_report: dict[str, Any] | None = None
    if stage_manifest is not None:
        target_stage = (stage_dir or root).resolve()
        try:
            stage_report = _stage_verify.verify_stage(target_stage, stage_manifest)
        except _stage_verify.StageVerifyError as exc:
            raise RunEvidencePackError(f"Verifikasi staging gagal: {exc}") from exc
        if not stage_report["valid"]:
            raise RunEvidencePackError(
                f"Direktori staging tidak cocok dengan manifest ({len(stage_report['missing'])} missing, "
                f"{len(stage_report['extra'])} extra, {len(stage_report['modified'])} modified)."
            )

    secret_findings = scan_run_secrets(root, manifest_rel=manifest_rel)
    if secret_findings and not allow_unredacted:
        raise RunEvidencePackError(
            f"Terdeteksi {len(secret_findings)} potensi kebocoran token/rahasia (pakai redaksi sebelum pack; lokasi pertama: {secret_findings[0]['path']}:{secret_findings[0]['line']})."
        )

    try:
        pack_res = _pack.pack_evidence(root, manifest_path=target_manifest)
    except _pack.EvidencePackError as exc:
        raise RunEvidencePackError(str(exc)) from exc

    manifest_obj = json.loads(target_manifest.read_text(encoding="utf-8"))
    category_counts = Counter(_categorize_artifact(e["path"]) for e in manifest_obj["files"])

    archive_info: dict[str, Any] | None = None
    if archive_path is not None:
        extra = [target_manifest] if not target_manifest.is_relative_to(root) else None
        archive_info = _create_deterministic_targz(root, archive_path, extra_files=extra)

    report = {
        "schema": RUN_PACK_SCHEMA,
        "action": "pack",
        "run_dir": str(root),
        "manifest": pack_res["manifest"],
        "file_count": pack_res["file_count"],
        "total_bytes": pack_res["total_bytes"],
        "categories": dict(sorted(category_counts.items())),
        "secret_scan": {
            "status": "WARN_UNREDACTED" if secret_findings else "CLEAN",
            "finding_count": len(secret_findings),
            "findings": secret_findings,
        },
        "stage_verify": stage_report,
        "archive": archive_info,
    }
    if meta_out is not None:
        meta_out.parent.mkdir(parents=True, exist_ok=True)
        meta_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def verify_run_evidence(
    run_dir: Path,
    *,
    manifest_path: Path | None = None,
    archive_path: Path | None = None,
) -> dict[str, Any]:
    """Verifikasi direktori run terhadap `manifest.json` dan arsip `.tar.gz` opsional."""
    if not run_dir.is_dir():
        raise RunEvidencePackError(f"Direktori run tidak ditemukan: {run_dir}")

    root = run_dir.resolve()
    target_manifest = (manifest_path or (root / _pack.DEFAULT_MANIFEST_NAME)).resolve()
    try:
        dir_res = _pack.verify_evidence(root, manifest_path=target_manifest)
    except _pack.EvidencePackError as exc:
        raise RunEvidencePackError(str(exc)) from exc

    manifest_obj = json.loads(target_manifest.read_text(encoding="utf-8"))
    archive_res: dict[str, Any] | None = None
    if archive_path is not None:
        archive_res = _verify_archive_against_manifest(archive_path, manifest_obj)

    secret_findings = scan_run_secrets(
        root,
        manifest_rel=target_manifest.relative_to(root).as_posix()
        if target_manifest.is_relative_to(root)
        else _pack.DEFAULT_MANIFEST_NAME,
    )
    overall_valid = bool(dir_res["valid"]) and (archive_res["valid"] if archive_res is not None else True)
    return {
        "schema": RUN_PACK_SCHEMA,
        "action": "verify",
        "valid": overall_valid,
        "run_dir": str(root),
        "directory_verify": dir_res,
        "archive_verify": archive_res,
        "secret_scan": {
            "status": "FINDINGS_PRESENT" if secret_findings else "CLEAN",
            "finding_count": len(secret_findings),
            "findings": secret_findings,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Perakit & pemverifikasi bundel evidence run ACE (berparameter ketat)."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Wajib: jalur eksplisit direktori evidence run/stage (tidak pernah ada path default).",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Path manifest.json kustom.")
    parser.add_argument("--archive", type=Path, default=None, help="Path arsip .tar.gz deterministik opsional.")
    parser.add_argument("--meta-out", type=Path, default=None, help="Tulis laporan metadata pack ke JSON terpisah.")
    parser.add_argument("--stage-dir", type=Path, default=None, help="Direktori staging opsional untuk pra-verifikasi.")
    parser.add_argument("--stage-manifest", type=Path, default=None, help="Manifest staging JSON opsional.")
    parser.add_argument("--allow-unredacted", action="store_true", help="Izinkan pack walau pemindai rahasia memberi peringatan.")
    parser.add_argument("--verify", action="store_true", help="Verifikasi bundel run (dan arsip bila diberi --archive).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.verify:
            res = verify_run_evidence(
                args.run_dir,
                manifest_path=args.manifest,
                archive_path=args.archive,
            )
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0 if res["valid"] else 2

        res = pack_run_evidence(
            args.run_dir,
            manifest_path=args.manifest,
            archive_path=args.archive,
            meta_out=args.meta_out,
            stage_dir=args.stage_dir,
            stage_manifest=args.stage_manifest,
            allow_unredacted=args.allow_unredacted,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, RunEvidencePackError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
