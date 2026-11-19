#!/usr/bin/env python3
"""Periksa naskah utuh sebelum staging dan deteksi kerusakan paket unggah KBM.

Untuk satu berkas naskah, validasi tepat 30 bab berurutan dengan setidaknya
1.000 kata isi per bab. Laporan menunjukkan jumlah kata dan temuan per bab.

Memeriksa direktori paket unggah KBM agar bebas dari:
- sampul hilang atau header byte bukan JPEG/PNG asli;
- berkas bab di bawah ambang ukuran byte argumen (`--min-bytes`);
- penomoran bab yang melompat (ada celah) atau duplikat.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any

if __package__ in (None, ""):
    from cover_check import CoverCheckInputError, check_cover
    from kbm_split import KbmSplitError, split_manuscript
else:
    from .cover_check import CoverCheckInputError, check_cover
    from .kbm_split import KbmSplitError, split_manuscript

PACK_CHECK_SCHEMA = "ace.kbm-pack-check.v1"
MANUSCRIPT_CHECK_SCHEMA = "ace.kbm-manuscript-check.v1"
REQUIRED_CHAPTER_COUNT = 30
REQUIRED_CHAPTER_WORDS = 1000
DEFAULT_MIN_BYTES = 1000

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_CHAPTER_NUM_RE = re.compile(r"(\d+)")
_CHAPTER_EXTS = frozenset({".md", ".txt"})


class KbmPackCheckError(ValueError):
    """Kesalahan direktori paket atau argumen pemeriksaan tidak sah."""


def check_manuscript_chapters(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    """Terapkan aturan naskah utuh pada laporan bab dari kbm_split."""
    required_numbers = set(range(1, REQUIRED_CHAPTER_COUNT + 1))
    counts = Counter(chapter["chapter_number"] for chapter in chapters)
    missing = sorted(required_numbers - counts.keys())
    duplicates = sorted(number for number, count in counts.items() if count > 1)
    errors = []
    if len(chapters) != REQUIRED_CHAPTER_COUNT:
        errors.append(f"Jumlah bab harus tepat {REQUIRED_CHAPTER_COUNT}.")
    if missing:
        errors.append(f"Nomor bab hilang: {', '.join(map(str, missing))}.")
    if duplicates:
        errors.append(f"Nomor bab ganda: {', '.join(map(str, duplicates))}.")

    chapter_reports = []
    for position, chapter in enumerate(chapters, start=1):
        number = chapter["chapter_number"]
        words = chapter["word_count"]
        chapter_errors = []
        if words < REQUIRED_CHAPTER_WORDS:
            chapter_errors.append(f"Isi bab kurang dari {REQUIRED_CHAPTER_WORDS} kata.")
        if number not in required_numbers:
            chapter_errors.append(f"Nomor di luar rentang 1–{REQUIRED_CHAPTER_COUNT}.")
        if counts[number] > 1:
            chapter_errors.append("Nomor bab ganda.")
        if number != position:
            chapter_errors.append(f"Pada posisi ini seharusnya bab {position}.")
        chapter_reports.append({
            "position": position,
            "chapter_number": number,
            "word_count": words,
            "valid": not chapter_errors,
            "errors": chapter_errors,
        })
    return {
        "schema": MANUSCRIPT_CHECK_SCHEMA,
        "valid": not errors and all(chapter["valid"] for chapter in chapter_reports),
        "required_chapter_count": REQUIRED_CHAPTER_COUNT,
        "min_words": REQUIRED_CHAPTER_WORDS,
        "chapter_count": len(chapters),
        "missing_numbers": missing,
        "duplicate_numbers": duplicates,
        "errors": errors,
        "chapters": chapter_reports,
    }


def check_manuscript(manuscript_path: Path) -> dict[str, Any]:
    """Periksa satu naskah utuh tanpa menulis berkas bab."""
    split = split_manuscript(manuscript_path, None)
    return {**check_manuscript_chapters(split["chapters"]), "source": split["source"]}


def _print_manuscript_report(report: dict[str, Any]) -> None:
    verdict = "LULUS" if report["valid"] else "GAGAL"
    print(f"{verdict} — {report['chapter_count']}/{report['required_chapter_count']} bab")
    for error in report["errors"]:
        print(f"- {error}")
    for chapter in report["chapters"]:
        status = "LULUS" if chapter["valid"] else "GAGAL"
        details = " ".join(chapter["errors"])
        line = f"Bab {chapter['chapter_number']}: {chapter['word_count']} kata — {status}"
        print(f"{line}. {details}" if details else line)


def detect_image_format(path: Path) -> str | None:
    """Deteksi format JPEG/PNG asli dari magic bytes awal berkas."""
    try:
        with path.open("rb") as fp:
            header = fp.read(8)
    except OSError:
        return None
    if header.startswith(PNG_MAGIC):
        return "png"
    if header.startswith(JPEG_MAGIC):
        return "jpeg"
    return None


def _find_cover(package_dir: Path, cover_name: str | None) -> Path | None:
    if cover_name is not None:
        candidate = package_dir / cover_name
        return candidate if candidate.is_file() else None
    for candidate in sorted(package_dir.iterdir(), key=lambda p: p.name.lower()):
        if candidate.is_file() and candidate.stem.lower() == "cover":
            return candidate
    return None


def check_package(
    package_dir: Path,
    *,
    min_bytes: int = DEFAULT_MIN_BYTES,
    cover_name: str | None = None,
    strict_cover: bool = False,
) -> dict[str, Any]:
    """Periksa integritas paket unggah KBM di `package_dir`."""
    if min_bytes < 0:
        raise KbmPackCheckError("Nilai --min-bytes tidak boleh negatif.")
    if cover_name is not None and (not isinstance(cover_name, str) or "\x00" in cover_name):
        raise KbmPackCheckError(f"Nama berkas sampul tidak sah: {cover_name!r}")
    if not package_dir.is_dir():
        raise KbmPackCheckError(f"Direktori paket tidak ditemukan: {package_dir}")
    if strict_cover and cover_name is not None and (
        not cover_name or cover_name in {".", ".."} or "/" in cover_name or "\\" in cover_name
    ):
        raise KbmPackCheckError("Mode sampul ketat memerlukan nama berkas lokal.")

    root = package_dir.resolve()
    errors: list[dict[str, Any]] = []

    # 1. Periksa sampul dan header JPEG/PNG
    cover_path = _find_cover(root, cover_name)
    cover_info: dict[str, Any]
    if cover_path is None:
        cover_info = {"found": False, "file": None, "format": None, "valid": False}
        errors.append({"code": "missing_cover", "message": "Berkas sampul (cover.*) tidak ditemukan."})
    else:
        unsafe_cover = strict_cover and cover_path.is_symlink()
        img_fmt = None if unsafe_cover else detect_image_format(cover_path)
        valid_img = img_fmt in ("jpeg", "png")
        cover_info = {
            "found": True,
            "file": cover_path.name,
            "size_bytes": cover_path.stat().st_size,
            "format": img_fmt,
            "valid": valid_img,
        }
        if not valid_img:
            errors.append(
                {
                    "code": "invalid_cover_header",
                    "file": cover_path.name,
                    "message": "Header berkas sampul bukan JPEG atau PNG yang sah.",
                }
            )
        elif strict_cover:
            try:
                cover_report = check_cover(cover_path)
            except CoverCheckInputError:
                cover_report = {"valid": False, "failed_rules": ["unreadable_cover"]}
            cover_info["validation"] = cover_report
            cover_info["valid"] = cover_report["valid"]
            if not cover_report["valid"]:
                errors.append({"code": "cover_rules_failed", "file": cover_path.name,
                               "failed_rules": cover_report["failed_rules"]})

    # 2. Pindai berkas teks bab dan ekstrak nomor bab
    chapter_files = sorted(
        (
            p
            for p in root.iterdir()
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in _CHAPTER_EXTS
        ),
        key=lambda p: p.name.lower(),
    )

    chapters: list[dict[str, Any]] = []
    short_chapters: list[str] = []
    unnumbered_chapters: list[str] = []
    seen_numbers: dict[int, list[str]] = {}

    for p in chapter_files:
        size_bytes = p.stat().st_size
        m = _CHAPTER_NUM_RE.search(p.stem)
        chap_num = int(m.group(1)) if m else None
        is_short = size_bytes < min_bytes
        if is_short:
            short_chapters.append(p.name)
            errors.append(
                {
                    "code": "chapter_too_short",
                    "file": p.name,
                    "size_bytes": size_bytes,
                    "min_bytes": min_bytes,
                    "message": f"Ukuran bab '{p.name}' ({size_bytes} B) di bawah ambang {min_bytes} B.",
                }
            )
        if chap_num is None:
            unnumbered_chapters.append(p.name)
            errors.append(
                {
                    "code": "unnumbered_chapter",
                    "file": p.name,
                    "message": f"Berkas bab '{p.name}' tidak memuat nomor urut.",
                }
            )
        else:
            seen_numbers.setdefault(chap_num, []).append(p.name)

        chapters.append(
            {
                "file": p.name,
                "chapter_number": chap_num,
                "size_bytes": size_bytes,
                "below_min_bytes": is_short,
            }
        )

    if not chapter_files:
        errors.append({"code": "no_chapters", "message": "Tidak ada berkas teks bab (.md/.txt)."})

    # 3. Validasi urutan nomor bab tanpa celah (1..max) maupun duplikat
    duplicates = sorted(num for num, files in seen_numbers.items() if len(files) > 1)
    for num in duplicates:
        errors.append(
            {
                "code": "duplicate_chapter_number",
                "chapter_number": num,
                "files": seen_numbers[num],
                "message": f"Nomor bab {num} muncul ganda pada {seen_numbers[num]}.",
            }
        )

    missing_numbers: list[int] = []
    if seen_numbers:
        max_num = max(seen_numbers)
        missing_numbers = [n for n in range(1, max_num + 1) if n not in seen_numbers]
        if missing_numbers:
            errors.append(
                {
                    "code": "chapter_numbering_gap",
                    "missing_numbers": missing_numbers,
                    "message": f"Nomor bab melompat; nomor yang hilang: {missing_numbers}.",
                }
            )

    valid = len(errors) == 0
    return {
        "schema": PACK_CHECK_SCHEMA,
        "package_dir": str(root),
        "valid": valid,
        "min_bytes": min_bytes,
        "cover": cover_info,
        "chapter_count": len(chapters),
        "short_chapters": short_chapters,
        "unnumbered_chapters": unnumbered_chapters,
        "duplicate_numbers": duplicates,
        "missing_numbers": missing_numbers,
        "error_count": len(errors),
        "errors": errors,
        "chapters": chapters,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Periksa satu berkas naskah utuh atau direktori paket unggah KBM."
    )
    parser.add_argument("input_path", type=Path, help="Berkas naskah utuh atau direktori paket unggah.")
    parser.add_argument("--json", action="store_true", help="Cetak laporan berkas naskah dalam JSON.")
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=DEFAULT_MIN_BYTES,
        help=f"Ukuran minimum tiap berkas teks bab dalam byte (default: {DEFAULT_MIN_BYTES}).",
    )
    parser.add_argument(
        "--cover",
        default=None,
        help="Nama berkas sampul spesifik (default: otomatis cari cover.*).",
    )
    parser.add_argument("--strict-cover", action="store_true",
                        help="Periksa juga dimensi, rasio, dan ukuran berkas sampul.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.input_path.is_file():
            report = check_manuscript(args.input_path)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                _print_manuscript_report(report)
        else:
            report = check_package(
                args.input_path,
                min_bytes=args.min_bytes,
                cover_name=args.cover,
                strict_cover=args.strict_cover,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, KbmPackCheckError, KbmSplitError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
