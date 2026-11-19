#!/usr/bin/env python3
"""Pemecah manuskrip Markdown KBM menjadi berkas per-bab dengan audit jumlah kata.

Memecah berkas manuskrip Markdown panjang berdasarkan penanda bab (mis.
`# Bab 1: Judul` atau `## Chapter 2 - Title`), menulis berkas per-bab secara
terurut ke direktori tujuan, menghitung kata per bab, menandai bab di bawah
ambang `--min-words`, dan mencetak laporan JSON ke stdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

KBM_SPLIT_SCHEMA = "ace.kbm-split.v1"
DEFAULT_MIN_WORDS = 800

_CHAPTER_HEADING_RE = re.compile(
    r"^\s*(?:#{1,3}\s+)?(?:Bab|Chapter)\s+(\d+)\b(?:\s*[:.\-—–]\s*(.+?)|\s+(.+?))?\s*$",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)


class KbmSplitError(ValueError):
    """Kesalahan masukan manuskrip, pola bab, atau argumen kbm_split."""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "bab"


def count_words(text: str) -> int:
    """Hitung jumlah kata bermakna dalam teks Markdown."""
    return len(_WORD_RE.findall(text))


def split_manuscript(
    manuscript_path: Path,
    output_dir: Path | None,
    *,
    min_words: int = DEFAULT_MIN_WORDS,
) -> dict[str, Any]:
    """Pecah naskah per bab atau periksa isinya tanpa menulis jika output_dir None."""
    if min_words < 0:
        raise KbmSplitError("Nilai --min-words tidak boleh negatif.")
    if not manuscript_path.is_file():
        raise KbmSplitError(f"Berkas manuskrip tidak ditemukan: {manuscript_path}")

    try:
        raw_text = manuscript_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise KbmSplitError(f"Gagal membaca '{manuscript_path}': {exc}") from exc

    sections: list[dict[str, Any]] = []
    current_lines: list[str] = []
    current_meta: dict[str, Any] | None = None
    in_code_fence = False

    for line in raw_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
        if not in_code_fence:
            match = _CHAPTER_HEADING_RE.match(line)
            if match:
                if current_meta is not None:
                    current_meta["body_lines"] = current_lines
                    sections.append(current_meta)
                chap_num = int(match.group(1))
                raw_title = (match.group(2) or match.group(3) or "").strip()
                current_meta = {
                    "chapter_number": chap_num,
                    "heading": line.strip(),
                    "title": raw_title or f"Bab {chap_num}",
                }
                current_lines = [line]
                continue
        if current_meta is not None:
            current_lines.append(line)

    if current_meta is not None:
        current_meta["body_lines"] = current_lines
        sections.append(current_meta)

    if not sections:
        raise KbmSplitError(
            f"Tidak ditemukan penanda bab (mis. '# Bab 1 ...' atau '# Chapter 1 ...') pada '{manuscript_path}'."
        )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    chapters: list[dict[str, Any]] = []
    below_threshold_files: list[str] = []

    for idx, sec in enumerate(sections, start=1):
        # Judul pada baris penanda bukan bagian dari isi bab.
        body_only = "\n".join(sec["body_lines"][1:])
        word_count = count_words(body_only)
        is_short = word_count < min_words
        fname = f"bab_{sec['chapter_number']:02d}_{_slugify(sec['title'])}.md"
        if output_dir is not None:
            content = "\n".join(sec["body_lines"]).rstrip() + "\n"
            (output_dir / fname).write_text(content, encoding="utf-8")
        if is_short:
            below_threshold_files.append(fname)
        chapters.append(
            {
                "index": idx,
                "chapter_number": sec["chapter_number"],
                "title": sec["title"],
                "output_file": fname,
                "word_count": word_count,
                "below_threshold": is_short,
            }
        )

    return {
        "schema": KBM_SPLIT_SCHEMA,
        "source": str(manuscript_path),
        "output_dir": str(output_dir.resolve()) if output_dir is not None else None,
        "min_words": min_words,
        "chapter_count": len(chapters),
        "below_threshold_count": len(below_threshold_files),
        "below_threshold_files": below_threshold_files,
        "chapters": chapters,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pemecah manuskrip Markdown KBM menjadi berkas per-bab beserta audit panjang kata."
    )
    parser.add_argument("manuscript", type=Path, help="Path berkas manuskrip Markdown.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Direktori tujuan penulisan berkas per-bab.",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=DEFAULT_MIN_WORDS,
        help=f"Ambang minimal jumlah kata per bab (default: {DEFAULT_MIN_WORDS}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Keluar dengan kode 1 apabila ada bab yang berada di bawah --min-words.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        report = split_manuscript(args.manuscript, args.output_dir, min_words=args.min_words)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.strict and report["below_threshold_count"] > 0:
            return 1
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, KbmSplitError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
