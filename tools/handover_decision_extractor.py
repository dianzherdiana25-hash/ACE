#!/usr/bin/env python3
"""Ekstraktor keputusan pemilik/hub, verdit, aturan tata kelola, & usulan terbuka (`ace.handover-decisions.v1`).

Memindai secara pasif berkas Markdown di `handover/` dan `docs/` (serta lewat symlink
yang dilewati aman), mengekstrak setiap butir beserta sitasi `path:line` tepat, dan
memberi label provenance `"brain_of_origin": "gravity-proposal"` pada ringkasan hasil.
Mendukung keluaran Markdown/JSON dan verifikasi `--check`.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISIONS_SCHEMA = "ace.handover-decisions.v1"
DEFAULT_OUTPUT_REL = "docs/research/ACE_HANDOVER_DECISIONS_EXTRACTED.md"
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"})
DERIVED_DOC_NAMES = frozenset(
    {
        "REPO_INDEX.md",
        "HANDOVER_INDEX.md",
        "REPO_CARTOGRAPHY.md",
        "PROGRAM_GLOSSARY.md",
        "BUILDER_ONBOARDING_PACK.md",
        "ACE_PLATFORM_REQUIREMENTS_SUMMARY.md",
        "ACE_HANDOVER_DECISIONS_EXTRACTED.md",
    }
)

_CATEGORIES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "GOVERNANCE_RULE",
        "Aturan Tata Kelola & Kontrak Tetap",
        re.compile(
            r"(?i)(Aturan\s+[12]\b|Tata Kelola|BERHASIL\b|STAGED\b|ratifikasi independen|"
            r"wilayah terlarang|tidak dapat ditawar|immutable|mandatory)"
        ),
    ),
    (
        "OWNER_HUB_DECISION",
        "Keputusan Pemilik / Hub / Verdict",
        re.compile(
            r"(?i)(Keputusan Pemilik|Keputusan hub|Hub decision|owner mandate|Ditetapkan\b|"
            r"\bAPPROVED\b|\bRATIFIED\b|\bVERDICT\b|\bPASS\b|arahan hub|terverifikasi sha256)"
        ),
    ),
    (
        "PARKED_OR_BLOCKED",
        "Butir Diparkir / Terblokir / Menunggu",
        re.compile(
            r"(?i)(\bdiparkir\b|\bparkir\b|\bBLOCKED\b|\bterblokir\b|BELUM TERVERIFIKASI|"
            r"menunggu vonis|menunggu panel|NOT_ASSESSED|\bREJECTED\b|owner-panel-blocked)"
        ),
    ),
    (
        "OPEN_PROPOSAL",
        "Usulan / Draf / Langkah Berikutnya",
        re.compile(
            r"(?i)(\bUSULAN\b|\bproposal\b|\bDRAF\b|BUKAN preregistrasi|tahap berikutnya|"
            r"rancangan\b|\bnext action\b|\bANTREAN\b)"
        ),
    ),
)

_ACTOR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pemilik", re.compile(r"(?i)(pemilik|owner)")),
    ("hub", re.compile(r"(?i)(\bhub\b|\bila\b|orkestrator)")),
    ("engineer_utama", re.compile(r"(?i)(\bIan\b|Engineer Utama)")),
)


def _iter_source_docs(repo_root: Path, excludes: set[str]) -> list[Path]:
    root = repo_root.resolve()
    files: list[Path] = []
    for sub in ("handover", "docs"):
        sdir = root / sub
        if sdir.is_symlink() or not sdir.is_dir():
            continue
        for cur_dir, dirnames, filenames in os.walk(sdir, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink()
            )
            for fname in sorted(filenames):
                if not fname.lower().endswith(".md"):
                    continue
                if fname in DERIVED_DOC_NAMES or fname.startswith("ACE_GRAVITY_"):
                    continue
                fp = Path(cur_dir) / fname
                if fp.is_symlink():
                    continue
                rel = fp.relative_to(root).as_posix()
                if rel in excludes:
                    continue
                files.append(fp)
    files.sort(key=lambda p: p.relative_to(root).as_posix())
    return files


def _detect_actor(line: str, rel_path: str) -> str:
    combined = f"{rel_path} {line}"
    for actor, pat in _ACTOR_PATTERNS:
        if pat.search(combined):
            return actor
    return "repo_record"


def extract_decisions(
    repo_root: Path,
    *,
    exclude_paths: set[str] | None = None,
    max_per_category: int = 35,
) -> dict[str, Any]:
    """Ekstrak daftar keputusan & usulan terbuka ber-sitasi `path:line` secara deterministik."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    excludes = {DEFAULT_OUTPUT_REL}
    if exclude_paths:
        for item in exclude_paths:
            excludes.add(item.lstrip("./"))

    sources = _iter_source_docs(root, excludes)
    buckets: dict[str, list[dict[str, Any]]] = {cat_id: [] for cat_id, _, _ in _CATEGORIES}
    lines_scanned = 0

    for fp in sources:
        rel = fp.relative_to(root).as_posix()
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        lines_scanned += len(lines)
        area_bonus = 1 if rel.startswith("handover/") else 0
        for line_no, raw in enumerate(lines, start=1):
            clean = re.sub(r"\s+", " ", raw).strip()
            if len(clean) < 18 or clean.startswith("| ---"):
                continue
            matched_cats: list[str] = [cid for cid, _, pat in _CATEGORIES if pat.search(clean)]
            if not matched_cats:
                continue
            primary = matched_cats[0]
            score = len(matched_cats) + area_bonus + (1 if clean.startswith("#") else 0)
            buckets[primary].append(
                {
                    "category": primary,
                    "path": rel,
                    "line": line_no,
                    "source_actor": _detect_actor(clean, rel),
                    "signal_score": score,
                    "snippet": clean[:220] + ("…" if len(clean) > 220 else ""),
                }
            )

    groups: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    actor_counts: Counter[str] = Counter()
    total_kept = 0

    for cat_id, cat_label, _ in _CATEGORIES:
        items = buckets[cat_id]
        # Prioritaskan handover/, heading/skor sinyal tertinggi, lalu urut path:line stabil.
        items.sort(key=lambda it: (-it["signal_score"], it["path"], it["line"]))
        kept = items[:max_per_category]
        kept.sort(key=lambda it: (it["path"], it["line"]))
        category_counts[cat_id] = len(kept)
        for it in kept:
            actor_counts[it["source_actor"]] += 1
        total_kept += len(kept)
        groups.append(
            {
                "category": cat_id,
                "label": cat_label,
                "total_matches": len(items),
                "cited_count": len(kept),
                "items": kept,
            }
        )

    return {
        "schema": DECISIONS_SCHEMA,
        "brain_of_origin": "gravity-proposal",
        "repo_name": root.name,
        "summary": {
            "files_scanned": len(sources),
            "lines_scanned": lines_scanned,
            "total_items_kept": total_kept,
            "category_counts": dict(sorted(category_counts.items())),
            "actor_counts": dict(sorted(actor_counts.items())),
        },
        "groups": groups,
    }


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Ekstraksi Keputusan Pemilik/Hub, Verdit, & Usulan Terbuka",
        "",
        f"> Dihasilkan deterministik oleh `tools/handover_decision_extractor.py` (`{report['schema']}`, `brain_of_origin: {report['brain_of_origin']}`). Setiap butir ber-sitasi persis `<path>:<line>`; bukan otorisasi eksekusi.",
        "",
        "## 1. Ringkasan Pemindaian",
        "",
        f"- Berkas `handover/` & `docs/` dipindai: **{s['files_scanned']}**",
        f"- Total baris dipindai: **{s['lines_scanned']}**",
        f"- Total butir tersitasi: **{s['total_items_kept']}**",
        f"- Tag asal ringkasan: `{report['brain_of_origin']}`",
        "",
        "### Distribusi per Kategori",
        "",
        "| Kategori | Jumlah Tersitasi |",
        "| --- | ---: |",
    ]
    for cat_id, cnt in sorted(s["category_counts"].items()):
        lines.append(f"| `{cat_id}` | {cnt} |")

    for grp in report["groups"]:
        lines.extend(
            [
                "",
                f"## {grp['label']} (`{grp['category']}`)",
                "",
                f"- Kecocokan total: **{grp['total_matches']}** | Ditampilkan: **{grp['cited_count']}**",
                "",
                "| Sumber & Baris | Aktor Sumber | Asal Ringkasan | Kutipan |",
                "| --- | --- | --- | --- |",
            ]
        )
        if not grp["items"]:
            lines.append("| - | - | `gravity-proposal` | Tidak ada kutipan cocok |")
        else:
            for item in grp["items"]:
                lines.append(
                    f"| `{item['path']}:{item['line']}` | `{item['source_actor']}` | `gravity-proposal` | {_md_escape(item['snippet'])} |"
                )

    return "\n".join(lines) + "\n"


def check_extracted_doc(repo_root: Path, target_file: Path) -> tuple[bool, str]:
    root = repo_root.resolve()
    target = target_file if target_file.is_absolute() else (root / target_file)
    excludes: set[str] = set()
    try:
        excludes.add(target.resolve().relative_to(root).as_posix())
    except ValueError:
        pass
    expected = render_markdown(extract_decisions(root, exclude_paths=excludes))
    if not target.is_file():
        return False, f"STALE: berkas keputusan handover tidak ditemukan: {target}"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"STALE: {target} berbeda dari berkas handover/ & docs/ saat ini."
    return True, f"FRESH: {target} mutakhir dan cocok persis ({len(expected)} karakter)."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ekstraktor keputusan & usulan handover ber-sitasi path:line + brain_of_origin."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None, help="Cek kesegaran dokumen hasil ekstraksi (0/1).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            fresh, msg = check_extracted_doc(args.root, args.check)
            print(msg, file=sys.stdout if fresh else sys.stderr)
            return 0 if fresh else 1

        excludes: set[str] = set()
        if args.output is not None:
            out_abs = args.output if args.output.is_absolute() else (args.root.resolve() / args.output)
            try:
                excludes.add(out_abs.resolve().relative_to(args.root.resolve()).as_posix())
            except ValueError:
                pass
        rep = extract_decisions(args.root, exclude_paths=excludes)
        rendered = json.dumps(rep, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_markdown(rep)
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
