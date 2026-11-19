#!/usr/bin/env python3
"""Indeksator deterministik untuk dokumen handover/ dan docs/ repositori ACE.

Memetakan seluruh berkas di `handover/` dan `docs/` (kategori, jumlah baris,
ukuran byte, prefix SHA-256, dan judul ringkas), mendukung ekspor Markdown/JSON
serta verifikasi `--check` (exit 0 jika mutakhir, 1 jika usang/hilang).
Symlink dilewati secara eksplisit agar traversal tetap aman di dalam batas repo.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

HANDOVER_INDEX_SCHEMA = "ace.handover-index.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"})
DEFAULT_OUTPUT_REL = "docs/HANDOVER_INDEX.md"

_HEADING_RE = re.compile(r"^\s{0,3}#{1,3}\s+(?P<title>.+?)\s*$")


def _categorize_doc(rel_posix: str) -> str:
    lower = rel_posix.lower()
    name = Path(rel_posix).name.lower()
    if lower.endswith(".jsonl") or "corpus" in name:
        return "corpus_frozen"
    if "preregistrasi" in name or "preregistration" in name:
        return "preregistration"
    if "verdict" in name or "penilaian" in name or "keputusan" in name or "exit_gate" in name:
        return "verdict_decision"
    if "slate" in name or "serving" in lower or "ik_llama" in name:
        return "slate_serving"
    if "custody" in name or "lineage" in name or "governance" in name or "spec" in name or "spesifikasi" in name or "design" in name or "desain" in name or "rancangan" in name or "security" in lower or "architecture" in lower:
        return "spec_governance"
    if "akuntansi" in name or "accounting" in name or "audit" in name or "verification" in name or "validation" in lower:
        return "audit_accounting"
    if "konsolidasi" in name or "staging_note" in name or "intake" in name or "run_note" in name or "run_sheet" in name or "inventory" in name:
        return "consolidation_ops"
    if "research/" in lower or "report" in name or "diagnosis" in name:
        return "research_report"
    if lower.endswith((".py", ".sh", ".bash")):
        return "helper_script"
    if lower.endswith(".json"):
        return "manifest_json"
    return "reference_doc"


def _extract_title(path: Path, raw: bytes) -> tuple[str, int]:
    ext = path.suffix.lower()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ("(binary)", 0)

    lines = text.splitlines()
    line_count = len(lines)
    if ext in (".md", ".markdown", ".txt", ".rst"):
        for line in lines[:40]:
            m = _HEADING_RE.match(line)
            if m:
                return (re.sub(r"\s+", " ", m.group("title")).strip(), line_count)
        for line in lines[:10]:
            stripped = line.strip()
            if stripped and not stripped.startswith("---"):
                return (re.sub(r"\s+", " ", stripped)[:100], line_count)
        return ("-", line_count)

    if ext == ".json" and len(raw) <= 262_144:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                for key in ("schema", "title", "name", "mission_id", "id", "status"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        return (f"{key}: {val.strip()[:80]}", line_count)
        except json.JSONDecodeError:
            pass
        return ("JSON", line_count)

    if ext == ".jsonl":
        return ("JSONL corpus/stream", line_count)

    if ext == ".py":
        for line in lines[:20]:
            s = line.strip().strip('"\'')
            if s and not s.startswith("#!") and not s.startswith("from ") and not s.startswith("import "):
                return (s[:90], line_count)
        return ("Python helper", line_count)

    if ext in (".sh", ".bash"):
        return ("Shell script", line_count)

    return ("-", line_count)


def _normalize_excludes(root: Path, exclude_paths: set[str] | None) -> set[str]:
    excludes = {DEFAULT_OUTPUT_REL}
    if exclude_paths:
        for item in exclude_paths:
            p = Path(item)
            if p.is_absolute():
                try:
                    excludes.add(p.resolve().relative_to(root).as_posix())
                except ValueError:
                    pass
            else:
                excludes.add(p.as_posix().lstrip("./"))
    return excludes


def build_handover_index(
    repo_root: Path,
    *,
    areas: tuple[str, ...] = ("handover", "docs"),
    exclude_paths: set[str] | None = None,
) -> dict[str, Any]:
    """Bangun indeks deterministik berkas `handover/` dan `docs/` dari `repo_root`."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    excludes = _normalize_excludes(root, exclude_paths)
    entries: list[dict[str, Any]] = []
    skipped_symlinks: list[str] = []
    missing_areas: list[str] = []

    for area in areas:
        area_dir = root / area
        if area_dir.is_symlink():
            skipped_symlinks.append(area)
            continue
        if not area_dir.is_dir():
            missing_areas.append(area)
            continue

        for cur_dir, dirnames, filenames in os.walk(area_dir, followlinks=False):
            kept_dirs: list[str] = []
            for dname in sorted(dirnames):
                if dname in IGNORED_DIRS:
                    continue
                dpath = Path(cur_dir) / dname
                if dpath.is_symlink():
                    skipped_symlinks.append(dpath.relative_to(root).as_posix())
                    continue
                kept_dirs.append(dname)
            dirnames[:] = kept_dirs

            for fname in sorted(filenames):
                fpath = Path(cur_dir) / fname
                rel_posix = fpath.relative_to(root).as_posix()
                if fpath.is_symlink():
                    skipped_symlinks.append(rel_posix)
                    continue
                if rel_posix in excludes:
                    continue
                raw = fpath.read_bytes()
                sha256_full = hashlib.sha256(raw).hexdigest()
                title, line_count = _extract_title(fpath, raw)
                entries.append(
                    {
                        "area": area,
                        "path": rel_posix,
                        "category": _categorize_doc(rel_posix),
                        "format": fpath.suffix.lstrip(".").lower() or "none",
                        "size_bytes": len(raw),
                        "line_count": line_count,
                        "sha256": sha256_full,
                        "sha256_prefix": sha256_full[:12],
                        "title": title,
                    }
                )

    entries.sort(key=lambda item: (item["area"], item["path"]))
    area_counts = Counter(e["area"] for e in entries)
    category_counts = Counter(e["category"] for e in entries)

    return {
        "schema": HANDOVER_INDEX_SCHEMA,
        "repo_name": root.name,
        "areas_scanned": list(areas),
        "missing_areas": sorted(missing_areas),
        "summary": {
            "total_files": len(entries),
            "total_bytes": sum(e["size_bytes"] for e in entries),
            "total_lines": sum(e["line_count"] for e in entries),
            "handover_files": area_counts.get("handover", 0),
            "docs_files": area_counts.get("docs", 0),
            "skipped_symlinks": len(skipped_symlinks),
            "categories": dict(sorted(category_counts.items())),
        },
        "skipped_symlinks": sorted(skipped_symlinks),
        "entries": entries,
    }


def _md_cell(value: str, max_len: int = 100) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip().replace("|", "\\|")
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1] + "…"
    return cleaned or "-"


def render_markdown(index: dict[str, Any]) -> str:
    """Render indeks handover & docs ke Markdown deterministik."""
    s = index["summary"]
    lines = [
        f"# Indeks Handover & Dokumentasi ACE — {index['repo_name']}",
        "",
        f"> Dihasilkan deterministik oleh `tools/handover_index.py` (`{index['schema']}`). Berkas target indeks sendiri (`{DEFAULT_OUTPUT_REL}`) dikecualikan agar idempoten 100%.",
        "",
        "## 1. Ringkasan",
        "",
        f"- Schema: `{index['schema']}`",
        f"- Total berkas terindeks: **{s['total_files']}** (`handover/`: **{s['handover_files']}**, `docs/`: **{s['docs_files']}**)",
        f"- Total baris teks UTF-8: **{s['total_lines']}**",
        f"- Total ukuran: **{s['total_bytes']}** byte",
        f"- Symlink dilewati: **{s['skipped_symlinks']}**",
        "",
        "### Distribusi Kategori",
        "",
        "| Kategori | Jumlah Berkas |",
        "| --- | ---: |",
    ]
    if s["categories"]:
        for cat, cnt in sorted(s["categories"].items()):
            lines.append(f"| `{cat}` | {cnt} |")
    else:
        lines.append("| - | 0 |")

    for area in index["areas_scanned"]:
        subset = [e for e in index["entries"] if e["area"] == area]
        section_num = "2" if area == "handover" else "3"
        lines.extend(
            [
                "",
                f"## {section_num}. Inventaris `{area}/` ({len(subset)} berkas)",
                "",
                "| Berkas | Kategori | Baris | Byte | SHA-256 | Judul / Ringkasan |",
                "| --- | --- | ---: | ---: | --- | --- |",
            ]
        )
        if not subset:
            lines.append(f"| - | - | 0 | 0 | - | Tidak ada berkas pada `{area}/` |")
        else:
            for item in subset:
                lines.append(
                    f"| `{item['path']}` | `{item['category']}` | {item['line_count']} "
                    f"| {item['size_bytes']} | `{item['sha256_prefix']}` | {_md_cell(item['title'])} |"
                )

    if index["skipped_symlinks"]:
        lines.extend(["", "## Catatan Symlink Dilewati", ""])
        for sym in index["skipped_symlinks"]:
            lines.append(f"- `{sym}`")

    return "\n".join(lines) + "\n"


def check_handover_index(repo_root: Path, target_file: Path) -> tuple[bool, str]:
    """Periksa apakah `target_file` ada dan cocok persis byte-per-byte dengan hasil render terbaru."""
    root = repo_root.resolve()
    target = target_file if target_file.is_absolute() else (root / target_file)
    excludes: set[str] = set()
    try:
        excludes.add(target.resolve().relative_to(root).as_posix())
    except ValueError:
        pass
    expected = render_markdown(build_handover_index(root, exclude_paths=excludes))
    if not target.is_file():
        return False, f"STALE: berkas indeks tidak ditemukan: {target}"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"STALE: {target} berbeda dari status handover/ & docs/ saat ini."
    return True, f"FRESH: {target} mutakhir dan cocok persis ({len(expected)} karakter)."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generator indeks deterministik handover/ & docs/ serta pemeriksa --check."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format keluaran (default: markdown).",
    )
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    parser.add_argument(
        "--check",
        type=Path,
        default=None,
        help="Verifikasi berkas Markdown target cocok byte-per-byte (exit 0 segar, 1 usang).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            fresh, message = check_handover_index(args.root, args.check)
            print(message, file=sys.stdout if fresh else sys.stderr)
            return 0 if fresh else 1

        excludes: set[str] = set()
        if args.output is not None:
            out_abs = args.output if args.output.is_absolute() else (args.root.resolve() / args.output)
            try:
                excludes.add(out_abs.resolve().relative_to(args.root.resolve()).as_posix())
            except ValueError:
                pass
        idx = build_handover_index(args.root, exclude_paths=excludes)
        rendered = (
            json.dumps(idx, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(idx)
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
