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
import json
from pathlib import Path
import shutil
import sys
from typing import Any

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


class KbmPipelineError(ValueError):
    """Kesalahan masukan CLI atau berkas pendukung pada pipeline KBM."""


def run_pipeline(
    manuscript_path: Path,
    output_dir: Path,
    *,
    min_words: int = DEFAULT_MIN_WORDS,
    min_bytes: int = DEFAULT_MIN_BYTES,
    cover_name: str | None = None,
    cover_source: Path | None = None,
) -> dict[str, Any]:
    """Jalankan `kbm_split` diikuti `kbm_pack_check` dan kembalikan laporan gabungan."""
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

    return {
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline terpadu pemecahan manuskrip KBM dan pemeriksaan paket unggah."
    )
    parser.add_argument("manuscript", type=Path, help="Path berkas manuskrip Markdown.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Direktori paket tujuan untuk berkas bab hasil pecah dan sampul.",
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
