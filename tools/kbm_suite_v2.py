#!/usr/bin/env python3
"""Perkakas produksi KBM v2: audit mutu bab/sampul/duplikasi & proyeksi royalti Decimal (`ace.kbm-suite.v2`).

Memadukan:
1. Pemeriksaan paket (`tools.kbm_pack_check`) dan dimensi/rasio aspek biner sampul (`tools.cover_check`).
2. Audit QA naskah bab (deteksi bab kosong, pacing jumlah kata min/maks/rata-rata,
   dan deteksi bab duplikat SHA-256 ternormalisasi).
3. Proyeksi royalti berbasis `Decimal` (dengan integrasi `tools.royalty_track` opsional
   dan ambang cair KBM Rp15.000) ke format JSON dan CSV deterministik.

Zero jaringan live.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import cover_check as _cover_check
from tools import kbm_pack_check as _pack_check
from tools import royalty_track as _royalty_track

KBM_SUITE_V2_SCHEMA = "ace.kbm-suite.v2"
KBM_MIN_PAYOUT_IDR = Decimal("15000")

_WORD_RE = re.compile(r"\S+")


class KbmSuiteV2Error(ValueError):
    """Kesalahan direktori paket, aturan QA, parameter Decimal, atau argumen CLI KBM v2."""


def _normalize_for_dup_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _word_stats(text: str) -> tuple[int, int]:
    words = _WORD_RE.findall(text)
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return len(words), len(paragraphs)


def audit_manuscript_package(
    package_dir: Path,
    *,
    min_words: int = 800,
    max_words: int = 6000,
    min_bytes: int = _pack_check.DEFAULT_MIN_BYTES,
    cover_name: str | None = None,
    cover_rules_path: Path | None = None,
) -> dict[str, Any]:
    """Audit lengkap direktori bab KBM: pack_check, cover_check, pacing kata, & duplikasi bab."""
    if min_words < 0 or max_words < min_words:
        raise KbmSuiteV2Error("Rentang `--min-words` / `--max-words` tidak valid.")
    if not package_dir.is_dir():
        raise KbmSuiteV2Error(f"Direktori paket KBM tidak ditemukan: {package_dir}")

    root = package_dir.resolve()
    for p in root.iterdir():
        if p.is_symlink():
            raise KbmSuiteV2Error(f"Symlink tidak diizinkan dalam paket KBM: {p}")

    pack_rep = _pack_check.check_package(root, min_bytes=min_bytes, cover_name=cover_name)

    cover_rep: dict[str, Any] | None = None
    cover_file_name = (pack_rep.get("cover") or {}).get("file")
    if cover_file_name:
        rules = _cover_check.load_rules(cover_rules_path)
        cover_rep = _cover_check.check_cover(root / str(cover_file_name), rules=rules)

    chapter_files = sorted(
        (
            p
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in {".md", ".txt"}
        ),
        key=lambda p: p.name.lower(),
    )

    hash_buckets: dict[str, list[str]] = defaultdict(list)
    chapters_qa: list[dict[str, Any]] = []
    empty_chapters: list[str] = []
    pacing_violations: list[dict[str, Any]] = []
    word_counts: list[int] = []

    for ch in chapter_files:
        try:
            text = ch.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise KbmSuiteV2Error(f"Gagal membaca bab UTF-8 '{ch.name}': {exc}") from exc

        words, paras = _word_stats(text)
        norm = _normalize_for_dup_hash(text)
        content_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        hash_buckets[content_hash].append(ch.name)
        word_counts.append(words)

        status = "OK"
        if words == 0:
            status = "EMPTY"
            empty_chapters.append(ch.name)
        elif words < min_words:
            status = "TOO_SHORT"
            pacing_violations.append({"file": ch.name, "word_count": words, "reason": f"< {min_words} kata"})
        elif words > max_words:
            status = "TOO_LONG"
            pacing_violations.append({"file": ch.name, "word_count": words, "reason": f"> {max_words} kata"})

        chapters_qa.append(
            {
                "file": ch.name,
                "word_count": words,
                "paragraph_count": paras,
                "normalized_hash": content_hash,
                "pacing_status": status,
            }
        )

    duplicate_groups = [
        {"hash": h, "files": sorted(names)}
        for h, names in sorted(hash_buckets.items())
        if len(names) > 1
    ]

    mean_w = round(sum(word_counts) / len(word_counts), 2) if word_counts else 0.0
    var_w = (
        sum((w - mean_w) ** 2 for w in word_counts) / len(word_counts)
        if word_counts
        else 0.0
    )
    pacing_summary = {
        "chapter_count": len(chapters_qa),
        "total_words": sum(word_counts),
        "min_words_actual": min(word_counts) if word_counts else 0,
        "max_words_actual": max(word_counts) if word_counts else 0,
        "mean_words": mean_w,
        "stddev_words": round(math.sqrt(var_w), 2),
        "expected_min_words": min_words,
        "expected_max_words": max_words,
    }

    cover_ok = True if cover_rep is None else bool(cover_rep["valid"])
    if not pack_rep["cover"]["found"]:
        cover_ok = False
    qa_passed = (
        bool(pack_rep["valid"])
        and cover_ok
        and not empty_chapters
        and not pacing_violations
        and not duplicate_groups
    )

    return {
        "schema": KBM_SUITE_V2_SCHEMA,
        "mode": "qa",
        "package_dir": str(root),
        "qa_passed": qa_passed,
        "pack_check": pack_rep,
        "cover_check": cover_rep,
        "pacing_summary": pacing_summary,
        "empty_chapters": empty_chapters,
        "pacing_violations": pacing_violations,
        "duplicate_chapter_groups": duplicate_groups,
        "chapters": chapters_qa,
    }


def _parse_dec(raw: str, name: str) -> Decimal:
    try:
        val = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise KbmSuiteV2Error(f"Nilai `{name}` bukan Decimal sah: {raw!r}") from exc
    if not val.is_finite():
        raise KbmSuiteV2Error(f"Nilai `{name}` harus finit: {raw!r}")
    return val


def project_royalties(
    *,
    unit_price_idr: str,
    author_share_rate: str,
    monthly_units: int,
    months: int = 6,
    royalty_csv_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """Proyeksi royalti bulanan deterministik beraritmetika `Decimal` + opsional histori CSV."""
    price = _parse_dec(unit_price_idr, "unit_price_idr")
    share = _parse_dec(author_share_rate, "author_share_rate")
    if price <= 0:
        raise KbmSuiteV2Error("`unit_price_idr` wajib > 0.")
    if not (Decimal("0") < share <= Decimal("1")):
        raise KbmSuiteV2Error("`author_share_rate` wajib di rentang (0, 1].")
    if isinstance(monthly_units, bool) or monthly_units < 0:
        raise KbmSuiteV2Error("`monthly_units` wajib >= 0.")
    if isinstance(months, bool) or months <= 0 or months > 120:
        raise KbmSuiteV2Error("`months` wajib di rentang 1..120.")

    history_summary: dict[str, Any] | None = None
    starting_balance = Decimal("0.00")
    if royalty_csv_paths:
        history_summary = _royalty_track.summarize_royalties(royalty_csv_paths)
        hist_idr = history_summary["totals_by_currency"].get("IDR")
        if hist_idr is not None:
            starting_balance = Decimal(hist_idr)

    q = Decimal("0.01")
    unit_royalty = (price * share).quantize(q, rounding=ROUND_HALF_UP)
    monthly_gross = (price * Decimal(monthly_units)).quantize(q, rounding=ROUND_HALF_UP)
    monthly_net = (unit_royalty * Decimal(monthly_units)).quantize(q, rounding=ROUND_HALF_UP)

    rows: list[dict[str, Any]] = []
    cumulative = starting_balance
    unpaid_pool = Decimal("0.00")
    payout_events = 0

    for m_idx in range(1, months + 1):
        cumulative += monthly_net
        unpaid_pool += monthly_net
        payout_triggered = unpaid_pool >= KBM_MIN_PAYOUT_IDR
        payout_amount = Decimal("0.00")
        if payout_triggered:
            payout_amount = unpaid_pool.quantize(q, rounding=ROUND_HALF_UP)
            unpaid_pool = Decimal("0.00")
            payout_events += 1
        rows.append(
            {
                "month_index": m_idx,
                "projected_units": monthly_units,
                "gross_idr": format(monthly_gross, "f"),
                "net_royalty_idr": format(monthly_net, "f"),
                "cumulative_royalty_idr": format(cumulative.quantize(q, rounding=ROUND_HALF_UP), "f"),
                "payout_triggered": payout_triggered,
                "payout_idr": format(payout_amount, "f"),
                "carried_balance_idr": format(unpaid_pool.quantize(q, rounding=ROUND_HALF_UP), "f"),
            }
        )

    return {
        "schema": KBM_SUITE_V2_SCHEMA,
        "mode": "projection",
        "parameters": {
            "unit_price_idr": format(price, "f"),
            "author_share_rate": format(share, "f"),
            "unit_royalty_idr": format(unit_royalty, "f"),
            "monthly_units": monthly_units,
            "months": months,
            "payout_threshold_idr": format(KBM_MIN_PAYOUT_IDR, "f"),
        },
        "historical_idr_start": format(starting_balance.quantize(q, rounding=ROUND_HALF_UP), "f"),
        "history": history_summary,
        "summary": {
            "total_projected_gross_idr": format((monthly_gross * Decimal(months)).quantize(q, rounding=ROUND_HALF_UP), "f"),
            "total_projected_net_idr": format((monthly_net * Decimal(months)).quantize(q, rounding=ROUND_HALF_UP), "f"),
            "payout_events_count": payout_events,
            "ending_carried_balance_idr": format(unpaid_pool.quantize(q, rounding=ROUND_HALF_UP), "f"),
        },
        "schedule": rows,
    }


def render_projection_csv(proj: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "month_index",
            "projected_units",
            "gross_idr",
            "net_royalty_idr",
            "cumulative_royalty_idr",
            "payout_triggered",
            "payout_idr",
            "carried_balance_idr",
        ]
    )
    for row in proj["schedule"]:
        writer.writerow(
            [
                row["month_index"],
                row["projected_units"],
                row["gross_idr"],
                row["net_royalty_idr"],
                row["cumulative_royalty_idr"],
                str(row["payout_triggered"]).lower(),
                row["payout_idr"],
                row["carried_balance_idr"],
            ]
        )
    return buf.getvalue()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Perkakas KBM v2: audit QA paket/sampul/duplikasi dan proyeksi royalti Decimal."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    qa_p = sub.add_parser("qa", help="Audit paket bab KBM + cover + pacing + duplikasi.")
    qa_p.add_argument("package_dir", type=Path, help="Direktori paket KBM.")
    qa_p.add_argument("--min-words", type=int, default=800)
    qa_p.add_argument("--max-words", type=int, default=6000)
    qa_p.add_argument("--min-bytes", type=int, default=_pack_check.DEFAULT_MIN_BYTES)
    qa_p.add_argument("--cover", default=None)
    qa_p.add_argument("--cover-rules", type=Path, default=None)
    qa_p.add_argument("--strict", action="store_true", help="Exit 1 bila ada pelanggaran QA.")

    proj_p = sub.add_parser("project", help="Proyeksi royalti Decimal & ambang cair Rp15.000.")
    proj_p.add_argument("--unit-price-idr", required=True, help="Harga jual per unit/bab/episode (Decimal string).")
    proj_p.add_argument("--author-share-rate", required=True, help="Bagian penulis (mis. 0.70).")
    proj_p.add_argument("--monthly-units", required=True, type=int, help="Perkiraan unit terjual per bulan.")
    proj_p.add_argument("--months", type=int, default=6, help="Jumlah bulan proyeksi (default: 6).")
    proj_p.add_argument("--royalty-csv", nargs="*", type=Path, default=None, help="CSV histori royalti opsional.")
    proj_p.add_argument("--format", choices=("json", "csv"), default="json")
    proj_p.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "qa":
            rep = audit_manuscript_package(
                args.package_dir,
                min_words=args.min_words,
                max_words=args.max_words,
                min_bytes=args.min_bytes,
                cover_name=args.cover,
                cover_rules_path=args.cover_rules,
            )
            print(json.dumps(rep, ensure_ascii=False, indent=2))
            if args.strict and not rep["qa_passed"]:
                return 1
            return 0

        proj = project_royalties(
            unit_price_idr=args.unit_price_idr,
            author_share_rate=args.author_share_rate,
            monthly_units=args.monthly_units,
            months=args.months,
            royalty_csv_paths=args.royalty_csv or None,
        )
        rendered = render_projection_csv(proj) if args.format == "csv" else (json.dumps(proj, ensure_ascii=False, indent=2) + "\n")
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (
        OSError,
        KbmSuiteV2Error,
        _pack_check.KbmPackCheckError,
        _cover_check.CoverCheckInputError,
        _royalty_track.RoyaltyTrackError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
