#!/usr/bin/env python3
"""Periksa kontinuitas KBM agar temuan naskah mengarah ke bab yang perlu ditelaah.

Konfigurasi judul JSON memuat daftar nama kanonis pada `characters` dan,
bila ada, pemetaan ejaan keliru ke nama kanonis pada `name_variants`.
Misalnya {"characters":["Sora"],"name_variants":{"Sorra":"Sora"}}.
Nama dicocokkan tanpa membedakan kapital setelah normalisasi Unicode dan
spasi. Pemeriksaan hanya mengenali ejaan yang ditetapkan dalam konfigurasi.
Penanda TAMAT adalah baris tersendiri, termasuk dalam heading atau penekanan
Markdown. Penanda bersifat opsional dan hanya boleh muncul di bab terakhir.
Jumlah kata memakai tokenizer splitter atas isi bab di luar penanda TAMAT.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path
import re
import sys
from typing import Any
import unicodedata

if __package__:
    from .kbm_split import count_words, parse_chapters
else:
    from kbm_split import count_words, parse_chapters


QC_SCHEMA = "ace.kbm-qc.v1"
DEFAULT_MIN_WORDS = 1000
_TAMAT_LINE = re.compile(
    r"^\s*(?:#{1,6}\s+)?(?P<emphasis>\*{1,2}|_{1,2})?TAMAT[.!]?(?(emphasis)(?P=emphasis))\s*$",
    re.IGNORECASE,
)


class KbmQcError(ValueError):
    """Masukan QC tidak dapat dibaca atau belum membentuk konfigurasi yang sah."""


def _normalize_name(text: str) -> str:
    return unicodedata.normalize("NFC", " ".join(text.split()))


def _configured_name(text: Any) -> str:
    if not isinstance(text, str) or not text.strip() or not text.isprintable():
        raise KbmQcError("Nama tokoh wajib berupa string yang berisi teks.")
    return _normalize_name(text)


def _characters(config: Any) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    if not isinstance(config, dict) or not isinstance(config.get("characters"), list) or not config["characters"]:
        raise KbmQcError("Konfigurasi judul wajib memuat daftar characters berisi nama kanonis.")

    canonical = {}
    for value in config["characters"]:
        name = _configured_name(value)
        key = name.casefold()
        if key in canonical:
            raise KbmQcError("Daftar characters mengandung nama yang sama setelah normalisasi.")
        canonical[key] = name

    raw_variants = config.get("name_variants", {})
    if not isinstance(raw_variants, dict):
        raise KbmQcError("name_variants wajib berupa objek ejaan keliru ke nama kanonis.")
    variants = {}
    for raw_alias, raw_target in raw_variants.items():
        alias = _configured_name(raw_alias)
        target = _configured_name(raw_target).casefold()
        key = alias.casefold()
        if target not in canonical:
            raise KbmQcError("Target name_variants wajib tercantum pada characters.")
        if key in canonical or key in variants:
            raise KbmQcError("Ejaan name_variants bertabrakan setelah normalisasi.")
        variants[key] = (alias, canonical[target])
    return canonical, variants


def audit_manuscript(
    manuscript_path: Path, title_config_path: Path, *, min_words: int = DEFAULT_MIN_WORDS,
) -> dict[str, Any]:
    """Kumpulkan temuan per bab tanpa membuat berkas hasil pemecahan."""
    if type(min_words) is not int or min_words < 1:
        raise KbmQcError("Ambang kata wajib berupa bilangan bulat positif.")
    manuscript = manuscript_path.read_text(encoding="utf-8")
    config = json.loads(title_config_path.read_text(encoding="utf-8"))
    canonical, variants = _characters(config)
    # Coba nama lebih spesifik terlebih dahulu agar nama majemuk tetap utuh.
    spellings = sorted(canonical.keys() | variants.keys(), key=lambda name: (-len(name), name))
    name_pattern = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, spellings)) + r")(?!\w)")

    sections = parse_chapters(manuscript)
    if not sections:
        raise KbmQcError("Penanda bab tidak ditemukan pada naskah.")
    numbers = Counter(section["chapter_number"] for section in sections)
    chapters = []
    for position, section in enumerate(sections, 1):
        number = section["chapter_number"]
        body_lines = section["body_lines"][1:]
        end_markers = [index for index, line in enumerate(body_lines, 1) if _TAMAT_LINE.fullmatch(line)]
        marker_lines = set(end_markers)
        prose = "\n".join(line for index, line in enumerate(body_lines, 1) if index not in marker_lines)
        words = count_words(prose)
        mentions = Counter(name_pattern.findall(_normalize_name(prose).casefold()))
        issues = []

        if number != position:
            issues.append({"code": "chapter_out_of_sequence", "expected_number": position})
        if numbers[number] > 1:
            issues.append({"code": "duplicate_chapter_number"})
        if words < min_words:
            issues.append({"code": "chapter_too_short", "min_words": min_words})
        if end_markers and position != len(sections):
            issues.append({"code": "early_end_marker", "body_lines": end_markers})
        for spelling, count in sorted(mentions.items()):
            if spelling in variants:
                alias, expected = variants[spelling]
                issues.append({
                    "code": "character_name_variant", "found": alias, "expected": expected, "count": count,
                })
        chapters.append({
            "position": position,
            "chapter_number": number,
            "word_count": words,
            "end_marker_count": len(end_markers),
            "characters_seen": sorted(
                {canonical[spelling] if spelling in canonical else variants[spelling][1] for spelling in mentions}
            ),
            "issues": issues,
        })

    issue_count = sum(len(chapter["issues"]) for chapter in chapters)
    return {
        "schema": QC_SCHEMA,
        "valid": issue_count == 0,
        "min_words": min_words,
        "chapter_count": len(chapters),
        "issue_count": issue_count,
        "chapters": chapters,
    }


def _issue_text(issue: dict[str, Any]) -> str:
    code = issue["code"]
    if code == "chapter_out_of_sequence":
        return f"Nomor yang diharapkan pada posisi ini adalah {issue['expected_number']}."
    if code == "duplicate_chapter_number":
        return "Nomor bab muncul lebih dari sekali."
    if code == "chapter_too_short":
        return f"Isi bab kurang dari {issue['min_words']} kata."
    if code == "early_end_marker":
        return f"Penanda TAMAT muncul di bab sebelum bab terakhir pada baris isi {issue['body_lines']}."
    return f"Ejaan {escape(issue['found'])} muncul {issue['count']} kali. Ejaan kanonisnya {escape(issue['expected'])}."


def render_markdown(report: dict[str, Any]) -> str:
    """Cetak jumlah kata dan temuan sehingga bab yang perlu ditelaah mudah ditemukan."""
    verdict = "LULUS" if report["valid"] else "GAGAL"
    lines = [
        "# QC naskah KBM",
        "",
        f"{verdict} — {report['chapter_count']} bab dan {report['issue_count']} temuan.",
        f"Ambang isi per bab adalah {report['min_words']} kata.",
        "",
    ]
    for chapter in report["chapters"]:
        status = "GAGAL" if chapter["issues"] else "LULUS"
        lines.append(
            f"- Bab {chapter['chapter_number']} (posisi {chapter['position']}) — "
            f"{chapter['word_count']} kata. {status}."
        )
        lines.extend(f"  - {_issue_text(issue)}" for issue in chapter["issues"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("manuscript", type=Path, help="Naskah Markdown utuh bertanda Bab atau Chapter.")
    parser.add_argument("--title-config", type=Path, required=True, help="Konfigurasi judul JSON.")
    parser.add_argument("--min-words", type=int, default=DEFAULT_MIN_WORDS,
                        help=f"Ambang isi per bab (default {DEFAULT_MIN_WORDS}).")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        report = audit_manuscript(args.manuscript, args.title_config, min_words=args.min_words)
    except (OSError, ValueError) as exc:
        print(f"Error QC: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
