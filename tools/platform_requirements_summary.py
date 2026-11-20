#!/usr/bin/env python3
"""Ekstraktor ringkasan persyaratan platform, royalti, rel bukti, & batasan AI/privasi ACE (`ace.platform-requirements-summary.v1`).

Membaca secara pasif berkas Markdown pada `docs/`, `handover/`, `evidence/`, dan akar repo
(melewati symlink serta berkas target ringkasan sendiri), lalu mengekstrak bukti kutipan
terindeks berkas+baris tanpa karangan atau panggilan jaringan apa pun.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

if __package__:
    from ._repo_name import canonical_repo_name
else:
    from _repo_name import canonical_repo_name

REPO_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_SUMMARY_SCHEMA = "ace.platform-requirements-summary.v1"


def _canonical_repo_name(root: Path) -> str:
    """Nama repo dari URL remote origin via helper kanonis bersama."""
    return canonical_repo_name(root)

DEFAULT_OUTPUT_REL = "docs/research/ACE_PLATFORM_REQUIREMENTS_SUMMARY.md"
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"})
DERIVED_INDEX_DOCS = frozenset(
    {
        "docs/REPO_INDEX.md",
        "docs/HANDOVER_INDEX.md",
        "docs/REPO_CARTOGRAPHY.md",
    }
)

PLATFORMS: tuple[dict[str, Any], ...] = (
    {
        "id": "kbm_app",
        "label": "KBM App (Pilot Cerita Bersambung & SeaBank)",
        "pattern": re.compile(r"\bKBM\b|kbm_seabank|Novelis Perak", re.IGNORECASE),
    },
    {
        "id": "fastwork",
        "label": "Fastwork Indonesia (Rel Jasa & Penarikan Bank)",
        "pattern": re.compile(r"\bFastwork\b|fastwork_bank", re.IGNORECASE),
    },
    {
        "id": "gopay_qris_seabank",
        "label": "GoPay / QRIS / SeaBank / Rekening & Privasi",
        "pattern": re.compile(r"\bQRIS\b|\bGoPay\b|\bSeaBank\b|rekening penuh|DP-50%|INV/\[", re.IGNORECASE),
    },
    {
        "id": "facebook",
        "label": "Facebook Pro / Facebook (Terblokir Verifikasi Misi)",
        "pattern": re.compile(r"\bFacebook\b", re.IGNORECASE),
    },
    {
        "id": "royal_road_lynk_sribu",
        "label": "Royal Road / Lynk.id / Sribu / Penjualan Langsung",
        "pattern": re.compile(r"Royal Road|Lynk\.id|\bSribu\b|Direct-sales kit|AI-Generated tag", re.IGNORECASE),
    },
)

CONSTRAINT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "payout_fee_threshold",
        re.compile(r"(?i)(Rp\s?\d|coin|koin|payout|cair|share|100%|fee|biaya|transfer|penarikan)"),
    ),
    (
        "exclusivity_ip",
        re.compile(r"(?i)(eksklusif|exclusiv|exclusive|terkunci|re-sold)"),
    ),
    (
        "verification_blocker",
        re.compile(r"(?i)(block|blokir|unverified|belum terverifikasi|contradiction|bertentangan|menunggu panel|null)"),
    ),
    (
        "privacy_redaction",
        re.compile(r"(?i)(privasi|privacy|rekening|account number|placeholder|Pasal 8|written-permission)"),
    ),
    (
        "content_ai_gate",
        re.compile(r"(?i)(AI-Generated|bab\b|chapter|\b8 bab\b|minimum|ambang|human-checker|pronunciation|QA gate)"),
    ),
)


def _iter_markdown_sources(repo_root: Path, excludes: set[str]) -> list[Path]:
    root = repo_root.resolve()
    collected: list[Path] = []

    for fname in sorted(os.listdir(root)):
        fpath = root / fname
        if fpath.is_symlink() or not fpath.is_file() or fpath.suffix.lower() != ".md":
            continue
        rel = fpath.relative_to(root).as_posix()
        if rel not in excludes:
            collected.append(fpath)

    for sub in ("docs", "handover", "evidence"):
        sdir = root / sub
        if sdir.is_symlink() or not sdir.is_dir():
            continue
        for cur_dir, dirnames, filenames in os.walk(sdir, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink()
            )
            for fname in sorted(filenames):
                if not fname.lower().endswith(".md"):
                    continue
                fp = Path(cur_dir) / fname
                if fp.is_symlink():
                    continue
                rel = fp.relative_to(root).as_posix()
                if rel in excludes:
                    continue
                collected.append(fp)

    collected.sort(key=lambda p: p.relative_to(root).as_posix())
    return collected


def _classify_tags(line: str) -> list[str]:
    tags = [name for name, pat in CONSTRAINT_RULES if pat.search(line)]
    return tags


def extract_platform_requirements(
    repo_root: Path,
    *,
    exclude_paths: set[str] | None = None,
    max_citations_per_platform: int = 25,
) -> dict[str, Any]:
    """Pindai berkas Markdown repositori untuk mengekstrak syarat platform ber-sitasi baris."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    excludes = {DEFAULT_OUTPUT_REL} | set(DERIVED_INDEX_DOCS)
    if exclude_paths:
        for item in exclude_paths:
            excludes.add(item.lstrip("./"))

    sources = _iter_markdown_sources(root, excludes)
    hits_by_platform: dict[str, list[dict[str, Any]]] = {p["id"]: [] for p in PLATFORMS}
    seen_snippets: dict[str, set[tuple[str, int]]] = {p["id"]: set() for p in PLATFORMS}
    total_lines_scanned = 0

    for fpath in sources:
        rel = fpath.relative_to(root).as_posix()
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        total_lines_scanned += len(lines)
        for line_no, raw_line in enumerate(lines, start=1):
            clean = re.sub(r"\s+", " ", raw_line).strip()
            if not clean or clean.startswith("#") or clean.startswith("<!--"):
                continue
            tags = _classify_tags(clean)
            if not tags:
                continue
            for pmeta in PLATFORMS:
                pid = pmeta["id"]
                if not pmeta["pattern"].search(clean):
                    continue
                key = (rel, line_no)
                if key in seen_snippets[pid]:
                    continue
                seen_snippets[pid].add(key)
                hits_by_platform[pid].append(
                    {
                        "path": rel,
                        "line": line_no,
                        "tags": tags,
                        "snippet": clean[:220] + ("…" if len(clean) > 220 else ""),
                    }
                )

    sections: list[dict[str, Any]] = []
    category_totals: Counter[str] = Counter()
    total_citations_kept = 0
    for pmeta in PLATFORMS:
        pid = pmeta["id"]
        all_hits = hits_by_platform[pid]
        # Prioritaskan kutipan yang kaya tag persyaratan/kendala dan urutkan deterministik.
        all_hits.sort(key=lambda h: (-len(h["tags"]), h["path"], h["line"]))
        kept = all_hits[:max_citations_per_platform]
        kept.sort(key=lambda h: (h["path"], h["line"]))
        for h in kept:
            for t in h["tags"]:
                category_totals[t] += 1
        total_citations_kept += len(kept)
        sections.append(
            {
                "platform_id": pid,
                "label": pmeta["label"],
                "total_matches": len(all_hits),
                "cited_count": len(kept),
                "citations": kept,
            }
        )

    return {
        "schema": PLATFORM_SUMMARY_SCHEMA,
        "brain_of_origin": "gravity-proposal",
        "repo_name": _canonical_repo_name(root),
        "summary": {
            "markdown_files_scanned": len(sources),
            "lines_scanned": total_lines_scanned,
            "platform_count": len(sections),
            "total_citations_kept": total_citations_kept,
            "tag_counts": dict(sorted(category_totals.items())),
        },
        "platforms": sections,
    }


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Ringkasan Persyaratan Platform & Monetisasi ACE",
        "",
        f"> Dihasilkan secara deterministik dan pasif oleh `tools/platform_requirements_summary.py` (`{report['schema']}`, `brain_of_origin: {report['brain_of_origin']}`). Seluruh poin dikutip langsung beserta berkas dan nomor barisnya; nol karangan dan nol eksekusi pembayaran.",
        "",
        "## 1. Statistik Pemindaian",
        "",
        f"- Berkas Markdown dipindai: **{s['markdown_files_scanned']}**",
        f"- Total baris dipindai: **{s['lines_scanned']}**",
        f"- Total sitasi syarat/batasan terpilih: **{s['total_citations_kept']}** across `{s['platform_count']}` kelompok platform",
        "",
        "### Distribusi Tag Syarat",
        "",
        "| Kategori Tag | Jumlah Sitasi |",
        "| --- | ---: |",
    ]
    if s["tag_counts"]:
        for tag, cnt in sorted(s["tag_counts"].items()):
            lines.append(f"| `{tag}` | {cnt} |")
    else:
        lines.append("| - | 0 |")

    for sec in report["platforms"]:
        lines.extend(
            [
                "",
                f"## {sec['label']}",
                "",
                f"- Total kecocokan terdeteksi: **{sec['total_matches']}** | Ditampilkan: **{sec['cited_count']}**",
                "",
                "| Sumber & Baris | Kategori | Kutipan Persyaratan / Kendala |",
                "| --- | --- | --- |",
            ]
        )
        if not sec["citations"]:
            lines.append("| - | - | Tidak ada kutipan kecocokan pada berkas repo target |")
        else:
            for cit in sec["citations"]:
                src = f"`{cit['path']}:{cit['line']}`"
                tags = ", ".join(f"`{t}`" for t in cit["tags"])
                lines.append(f"| {src} | {tags} | {_md_escape(cit['snippet'])} |")

    return "\n".join(lines) + "\n"


def check_summary_doc(repo_root: Path, target_file: Path) -> tuple[bool, str]:
    root = repo_root.resolve()
    target = target_file if target_file.is_absolute() else (root / target_file)
    excludes: set[str] = set()
    try:
        excludes.add(target.resolve().relative_to(root).as_posix())
    except ValueError:
        pass
    expected = render_markdown(extract_platform_requirements(root, exclude_paths=excludes))
    if not target.is_file():
        return False, f"STALE: berkas ringkasan platform tidak ditemukan: {target}"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"STALE: {target} berbeda dari isi dokumen sumber saat ini."
    return True, f"FRESH: {target} mutakhir dan cocok persis ({len(expected)} karakter)."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ekstrak ringkasan persyaratan platform monetisasi ACE ber-sitasi sumber."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None, help="Verifikasi kesegaran dokumen ringkasan (0/1).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            fresh, msg = check_summary_doc(args.root, args.check)
            print(msg, file=sys.stdout if fresh else sys.stderr)
            return 0 if fresh else 1

        excludes: set[str] = set()
        if args.output is not None:
            out_abs = args.output if args.output.is_absolute() else (args.root.resolve() / args.output)
            try:
                excludes.add(out_abs.resolve().relative_to(args.root.resolve()).as_posix())
            except ValueError:
                pass
        rep = extract_platform_requirements(args.root, exclude_paths=excludes)
        rendered = (
            json.dumps(rep, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(rep)
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
