#!/usr/bin/env python3
"""Pantau kemajuan banyak judul KBM dari satu katalog tanpa antrean ganda.

Masukan memakai bentuk katalog kbm_schedule, berupa daftar JSON atau objek
dengan daftar `serials`. Satu rekord berisi `id`, `title`, `total_chapters`,
dan `completed_chapters` atau `completed_chapters_list`. Tambahkan `status`
(riset, naskah, cek, paket, terbit) dan `total_words` (jumlah kata tercatat).
Operator mencatat angka di katalog. Kedua laporan memakai sumber yang sama.

Contoh pemakaian dari akar repo:
    python3 tools/kbm_titles.py state.json --format markdown
    python3 tools/kbm_titles.py state.json --format json
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import sys
from typing import Any

TITLE_REPORT_SCHEMA = "ace.kbm-titles.v1"
STATUSES = ("riset", "naskah", "cek", "paket", "terbit")
_MARKDOWN_MARKERS = str.maketrans({char: f"&#{ord(char)};" for char in r"\`*_[]~!|"})


class KbmTitlesError(ValueError):
    """Kesalahan pembacaan atau validasi berkas state per judul."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise KbmTitlesError("Kunci JSON duplikat.")
    return obj


def _completed_chapters(entry: dict[str, Any], prefix: str, target: int) -> int:
    count = entry.get("completed_chapters")
    numbers = entry.get("completed_chapters_list")
    if count is not None and (type(count) is not int or not 0 <= count <= target):
        raise KbmTitlesError(f"{prefix} completed_chapters wajib integer pada rentang 0..{target}.")
    if numbers is None:
        if count is None:
            raise KbmTitlesError(f"{prefix} Jumlah atau daftar bab selesai wajib ada.")
        return count
    if not isinstance(numbers, list) or any(
        type(number) is not int or not 1 <= number <= target for number in numbers
    ):
        raise KbmTitlesError(f"{prefix} completed_chapters_list wajib daftar nomor bab pada rentang 1..{target}.")
    if len(numbers) != len(set(numbers)):
        raise KbmTitlesError(f"{prefix} Nomor bab selesai duplikat.")
    if count is not None and count != len(numbers):
        raise KbmTitlesError(f"{prefix} Jumlah bab selesai tidak cocok dengan daftar.")
    return len(numbers)


def build_report(state: Path) -> dict[str, Any]:
    """Baca katalog dan hitung total lintas judul dalam urutan sumber."""
    raw = json.loads(state.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    entries = raw.get("serials") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise KbmTitlesError("State wajib berupa daftar serial atau objek dengan daftar serials.")

    serials = []
    seen_ids = set()
    status_counts = dict.fromkeys(STATUSES, 0)
    for index, entry in enumerate(entries, 1):
        prefix = f"Serial ke-{index}."
        if not isinstance(entry, dict):
            raise KbmTitlesError(f"{prefix} Entri wajib berupa objek JSON.")
        for key in ("id", "title"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip() or not value.isprintable():
                raise KbmTitlesError(f"{prefix} Field {key} wajib teks satu baris dan tidak kosong.")
        serial_id = entry["id"].strip()
        if serial_id in seen_ids:
            raise KbmTitlesError(f"{prefix} ID serial duplikat.")
        seen_ids.add(serial_id)
        status = entry.get("status")
        if status not in STATUSES:
            raise KbmTitlesError(f"{prefix} Status yang sah adalah {', '.join(STATUSES)}.")
        target = entry.get("total_chapters")
        if type(target) is not int or target <= 0:
            raise KbmTitlesError(f"{prefix} total_chapters wajib bilangan bulat positif.")
        words = entry.get("total_words")
        if type(words) is not int or words < 0:
            raise KbmTitlesError(f"{prefix} total_words wajib bilangan bulat nonnegatif.")
        serials.append({
            "id": serial_id,
            "title": entry["title"].strip(),
            "status": status,
            "completed_chapters": _completed_chapters(entry, prefix, target),
            "total_chapters": target,
            "total_words": words,
        })
        status_counts[status] += 1

    return {
        "schema": TITLE_REPORT_SCHEMA,
        "serials": serials,
        "summary": {
            "total_serials": len(serials),
            "completed_chapters": sum(serial["completed_chapters"] for serial in serials),
            "total_chapters": sum(serial["total_chapters"] for serial in serials),
            "total_words": sum(serial["total_words"] for serial in serials),
            "by_status": status_counts,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Tampilkan progres bab per judul dan total dari laporan yang sama."""
    summary = report["summary"]
    lines = [
        "# Progres judul KBM",
        "",
        f"{summary['total_serials']} judul · "
        f"{summary['completed_chapters']}/{summary['total_chapters']} bab selesai · "
        f"{summary['total_words']} kata",
        "",
        "| ID | Judul | Status | Bab selesai / target | Kata |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for serial in report["serials"]:
        serial_id = escape(serial["id"]).translate(_MARKDOWN_MARKERS)
        title = escape(serial["title"]).translate(_MARKDOWN_MARKERS)
        lines.append(
            f"| {serial_id} | {title} | {serial['status']} | "
            f"{serial['completed_chapters']}/{serial['total_chapters']} | {serial['total_words']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Laporkan state per judul KBM dari katalog lokal.")
    parser.add_argument("state", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.state)
    except (OSError, ValueError) as exc:
        print(f"ERROR: Berkas state KBM tidak sah atau gagal dibaca. {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
