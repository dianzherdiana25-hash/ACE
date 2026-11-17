#!/usr/bin/env python3
"""Pipeline terpadu KBM: pecah manuskrip (`kbm_split`) lalu periksa paket (`kbm_pack_check`).

Menjalankan satu perintah dari berkas manuskrip Markdown masuk -> memecah
per bab ke direktori paket tujuan melalui `tools.kbm_split.split_manuscript`
-> memverifikasi kelengkapan sampul, ukuran bab, dan urutan bab melalui
`tools.kbm_pack_check.check_package` -> mencetak laporan JSON gabungan dan
mengembalikan exit code gabungan (0 hanya bila pemecahan bersih dan paket
lolos seluruh pemeriksaan).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.kbm_pack_check import (
    DEFAULT_MIN_BYTES,
    KbmPackCheckError,
    check_package,
)
from tools.kbm_split import (
    DEFAULT_MIN_WORDS,
    KbmSplitError,
    split_manuscript,
)

KBM_PIPELINE_SCHEMA = "ace.kbm-pipeline.v1"
KBM_UPLOAD_MANIFEST_SCHEMA = "ace.kbm-upload-manifest.v1"


class KbmPipelineError(ValueError):
    """Kesalahan masukan CLI atau berkas pendukung pada pipeline KBM."""


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "bab"


def _sha256_file(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def _stage_upload_bundle(
    *,
    manuscript_path: Path,
    output_dir: Path,
    bundle_dir: Path,
    split_report: dict[str, Any],
    pack_report: dict[str, Any],
) -> dict[str, Any]:
    bundle_dir.mkdir(parents=True, exist_ok=True)

    cover_info = pack_report.get("cover") or {}
    cover_file_name = cover_info.get("file")
    if not cover_file_name:
        raise KbmPipelineError("Informasi berkas sampul hilang dari laporan pack_check.")
    cover_src = output_dir / str(cover_file_name)
    cover_dst = bundle_dir / str(cover_file_name)
    shutil.copy2(cover_src, cover_dst)
    cover_size, cover_sha = _sha256_file(cover_dst)

    manifest_chapters: list[dict[str, Any]] = []
    total_words = 0
    for order, ch in enumerate(split_report.get("chapters", []), start=1):
        src_name = str(ch["output_file"])
        src_path = output_dir / src_name
        slug = _slugify(str(ch.get("title") or src_path.stem))
        bundle_file = f"ch_{order:03d}_{slug}.md"
        dst_path = bundle_dir / bundle_file
        shutil.copy2(src_path, dst_path)
        size_bytes, sha256 = _sha256_file(dst_path)
        word_count = int(ch["word_count"])
        total_words += word_count
        manifest_chapters.append(
            {
                "order": order,
                "chapter_number": ch["chapter_number"],
                "title": ch["title"],
                "source_file": src_name,
                "bundle_file": bundle_file,
                "word_count": word_count,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
        )

    manifest = {
        "schema": KBM_UPLOAD_MANIFEST_SCHEMA,
        "source_manuscript": str(manuscript_path),
        "cover": {
            "file": str(cover_file_name),
            "format": cover_info.get("format"),
            "size_bytes": cover_size,
            "sha256": cover_sha,
        },
        "chapter_count": len(manifest_chapters),
        "total_words": total_words,
        "chapters": manifest_chapters,
    }
    manifest_path = bundle_dir / "upload_manifest.json"
    tmp_path = manifest_path.with_name(f".{manifest_path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, manifest_path)
    return {
        "staged": True,
        "bundle_dir": str(bundle_dir.resolve()),
        "manifest_file": str(manifest_path.resolve()),
        "manifest": manifest,
    }


def run_pipeline(
    manuscript_path: Path,
    output_dir: Path,
    *,
    min_words: int = DEFAULT_MIN_WORDS,
    min_bytes: int = DEFAULT_MIN_BYTES,
    cover_name: str | None = None,
    cover_source: Path | None = None,
    bundle_dir: Path | None = None,
) -> dict[str, Any]:
    """Jalankan `kbm_split` diikuti `kbm_pack_check` dan opsional staging bundel unggah."""
    if min_words < 0:
        raise KbmPipelineError("Nilai --min-words tidak boleh negatif.")
    if min_bytes < 0:
        raise KbmPipelineError("Nilai --min-bytes tidak boleh negatif.")
    if cover_name is not None and (
        not cover_name or "/" in cover_name or "\\" in cover_name or cover_name in (".", "..")
    ):
        raise KbmPipelineError(f"Nama berkas sampul tidak sah: {cover_name!r}")
    if cover_source is not None and not cover_source.is_file():
        raise KbmPipelineError(f"Berkas sampul sumber tidak ditemukan: {cover_source}")
    if bundle_dir is not None and bundle_dir.resolve() == output_dir.resolve():
        raise KbmPipelineError("--bundle-dir harus berbeda dari --output-dir.")

    split_report = split_manuscript(
        manuscript_path,
        output_dir,
        min_words=min_words,
    )

    effective_cover = cover_name
    if cover_source is not None:
        dest_name = cover_name or f"cover{cover_source.suffix.lower() or '.img'}"
        dest_path = output_dir / dest_name
        shutil.copy2(cover_source, dest_path)
        effective_cover = dest_name

    pack_report = check_package(
        output_dir,
        min_bytes=min_bytes,
        cover_name=effective_cover,
    )

    split_clean = split_report["below_threshold_count"] == 0
    pack_valid = bool(pack_report["valid"])
    passed = split_clean and pack_valid

    if passed:
        failed_stage = None
    elif not pack_valid:
        failed_stage = "check"
    else:
        failed_stage = "split"

    short_chapters = sorted(
        set(split_report.get("below_threshold_files", []))
        | set(pack_report.get("short_chapters", []))
    )

    bundle_result: dict[str, Any] | None = None
    if bundle_dir is not None:
        if passed:
            bundle_result = _stage_upload_bundle(
                manuscript_path=manuscript_path,
                output_dir=output_dir,
                bundle_dir=bundle_dir,
                split_report=split_report,
                pack_report=pack_report,
            )
        else:
            bundle_result = {
                "staged": False,
                "bundle_dir": str(bundle_dir.resolve()),
                "reason": "pipeline_failed",
            }

    result: dict[str, Any] = {
        "schema": KBM_PIPELINE_SCHEMA,
        "manuscript": str(manuscript_path),
        "output_dir": str(output_dir.resolve()),
        "passed": passed,
        "split_clean": split_clean,
        "pack_valid": pack_valid,
        "failed_stage": failed_stage,
        "short_chapters": short_chapters,
        "split": split_report,
        "pack_check": pack_report,
    }
    if bundle_result is not None:
        result["bundle"] = bundle_result
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline terpadu pemecahan manuskrip KBM, pemeriksaan paket, dan staging bundel unggah."
    )
    parser.add_argument("manuscript", type=Path, help="Path berkas manuskrip Markdown.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Direktori paket tujuan untuk berkas bab hasil pecah dan sampul.",
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=None,
        help="Opsional direktori staging bundel unggah standar (`ch_001_*.md`, sampul, dan `upload_manifest.json`).",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=DEFAULT_MIN_WORDS,
        help=f"Ambang minimal jumlah kata per bab untuk kbm_split (default: {DEFAULT_MIN_WORDS}).",
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=DEFAULT_MIN_BYTES,
        help=f"Ambang minimal ukuran berkas bab (byte) untuk kbm_pack_check (default: {DEFAULT_MIN_BYTES}).",
    )
    parser.add_argument(
        "--cover",
        default=None,
        help="Nama berkas sampul di dalam --output-dir (default: otomatis cari cover.*).",
    )
    parser.add_argument(
        "--cover-file",
        type=Path,
        default=None,
        help="Opsional path gambar sampul eksternal untuk disalin ke --output-dir sebelum pengecekan.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI pipeline KBM."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = run_pipeline(
            args.manuscript,
            args.output_dir,
            min_words=args.min_words,
            min_bytes=args.min_bytes,
            cover_name=args.cover,
            cover_source=args.cover_file,
            bundle_dir=args.bundle_dir,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] else 1
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, KbmPipelineError, KbmSplitError, KbmPackCheckError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
