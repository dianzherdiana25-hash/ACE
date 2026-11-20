#!/usr/bin/env python3
"""Pembangkit glosarium istilah teknis program ACE berbasis Markdown & AST statis (`ace.program-glossary.v1`).

Mengumpulkan definisi eksplisit, heading kunci, konstanta `*_SCHEMA`, dan docstring modul/kelas
langsung dari berkas Markdown dan Python AST (tanpa impor atau eksekusi modul). Setiap entri
glosarium memuat berkas dan nomor baris sumber aslinya.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
GLOSSARY_SCHEMA = "ace.program-glossary.v1"

def _canonical_repo_name(root: Path) -> str:
    """Nama repo dari URL remote git — stabil di semua nama direktori
    checkout; jatuh ke nama direktori bila bukan repo git."""
    try:
        url = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        url = ""
    if url:
        name = url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        return name[:-4] if name.endswith(".git") else name
    return root.name

DEFAULT_OUTPUT_REL = "docs/PROGRAM_GLOSSARY.md"
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

_BOLD_DEF_RE = re.compile(
    r"^\s*[-*]\s+\*\*(?P<term>[A-Za-z0-9_./() -]{2,64}?)\*\*\s*(?:[:—–-]\s+)(?P<desc>.+)$"
)
_CODE_DEF_RE = re.compile(
    r"^\s*[-*]\s+`(?P<term>[A-Za-z0-9_./:-]{2,64})`\s*(?:[:—–=-]\s+)(?P<desc>.+)$"
)
_TERM_HEADING_RE = re.compile(
    r"^\s{0,3}#{2,3}\s+(?P<term>(?:Gate\s+\d|EVO\s+\d+|WS-[A-Z0-9]+|G[0-5]|Rel\s+\d|Aturan\s+\d)[^#\n]{0,60})$"
)


def _walk_repo_files(repo_root: Path, excludes: set[str]) -> tuple[list[Path], list[Path]]:
    root = repo_root.resolve()
    md_files: list[Path] = []
    py_files: list[Path] = []

    for cur_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink()
        )
        cur = Path(cur_dir)
        rel_dir = cur.relative_to(root).as_posix()
        top = "." if rel_dir == "." else rel_dir.split("/", 1)[0]
        for fname in sorted(filenames):
            fp = cur / fname
            if fp.is_symlink():
                continue
            rel = fp.relative_to(root).as_posix()
            if rel in excludes:
                continue
            if fname.lower().endswith(".md"):
                if fname in DERIVED_DOC_NAMES or fname.startswith("ACE_GRAVITY_"):
                    continue
                if top in (".", "docs", "handover"):
                    md_files.append(fp)
            elif fname.endswith(".py") and not fname.startswith("test_") and top in ("tools", "code", "."):
                py_files.append(fp)

    md_files.sort(key=lambda p: p.relative_to(root).as_posix())
    py_files.sort(key=lambda p: p.relative_to(root).as_posix())
    return md_files, py_files


def _first_doc_line(doc: str | None) -> str:
    if not doc or not doc.strip():
        return ""
    for ln in doc.strip().splitlines():
        cleaned = re.sub(r"\s+", " ", ln).strip()
        if cleaned:
            return cleaned
    return ""


def build_glossary(
    repo_root: Path,
    *,
    exclude_paths: set[str] | None = None,
    max_per_kind: int = 80,
) -> dict[str, Any]:
    """Bangun glosarium istilah teknis berbasis definisi Markdown & AST Python statis."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    excludes = {DEFAULT_OUTPUT_REL}
    if exclude_paths:
        for item in exclude_paths:
            excludes.add(item.lstrip("./"))

    md_files, py_files = _walk_repo_files(root, excludes)
    raw_entries: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    def add_entry(term: str, kind: str, path: str, line: int, definition: str) -> None:
        t = re.sub(r"\s+", " ", term).strip()
        d = re.sub(r"\s+", " ", definition).strip()
        if not t or not d or len(d) < 6:
            return
        key = (t.casefold(), kind)
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        raw_entries.append(
            {
                "term": t,
                "source_kind": kind,
                "path": path,
                "line": line,
                "definition": d[:220] + ("…" if len(d) > 220 else ""),
            }
        )

    for fp in md_files:
        rel = fp.relative_to(root).as_posix()
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for idx, raw_line in enumerate(lines, start=1):
            m_bold = _BOLD_DEF_RE.match(raw_line)
            if m_bold:
                add_entry(m_bold.group("term"), "markdown_def", rel, idx, m_bold.group("desc"))
                continue
            m_code = _CODE_DEF_RE.match(raw_line)
            if m_code:
                add_entry(m_code.group("term"), "markdown_def", rel, idx, m_code.group("desc"))
                continue
            m_head = _TERM_HEADING_RE.match(raw_line)
            if m_head:
                desc = ""
                for nxt in lines[idx : idx + 6]:
                    clean_nxt = re.sub(r"\s+", " ", nxt).strip()
                    if clean_nxt and not clean_nxt.startswith("#") and not clean_nxt.startswith("|"):
                        desc = clean_nxt
                        break
                if desc:
                    add_entry(m_head.group("term"), "markdown_heading", rel, idx, desc)

    for fp in py_files:
        rel = fp.relative_to(root).as_posix()
        try:
            src = fp.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=rel)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        mod_doc = _first_doc_line(ast.get_docstring(tree))
        if mod_doc:
            mod_term = rel[:-3].replace("/", ".")
            add_entry(mod_term, "ast_module", rel, 1, mod_doc)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_doc = _first_doc_line(ast.get_docstring(node))
                if cls_doc:
                    add_entry(node.name, "ast_class", rel, node.lineno, cls_doc)
            elif isinstance(node, ast.Assign):
                if (
                    len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id.endswith("SCHEMA")
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    add_entry(
                        node.value.value,
                        "ast_schema",
                        rel,
                        node.lineno,
                        f"Skema JSON `{node.targets[0].id}` pada `{rel}`",
                    )

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for entry in raw_entries:
        by_kind.setdefault(entry["source_kind"], []).append(entry)

    kept_entries: list[dict[str, Any]] = []
    for kind in sorted(by_kind):
        subset = sorted(by_kind[kind], key=lambda e: (e["term"].casefold(), e["path"], e["line"]))
        kept_entries.extend(subset[:max_per_kind])

    kept_entries.sort(key=lambda e: (e["term"].casefold(), e["source_kind"], e["path"], e["line"]))
    kind_counts = Counter(e["source_kind"] for e in kept_entries)

    return {
        "schema": GLOSSARY_SCHEMA,
        "repo_name": _canonical_repo_name(root),
        "summary": {
            "markdown_files_scanned": len(md_files),
            "python_files_scanned": len(py_files),
            "total_terms_discovered": len(raw_entries),
            "total_terms_kept": len(kept_entries),
            "kind_counts": dict(sorted(kind_counts.items())),
        },
        "terms": kept_entries,
    }


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(glossary: dict[str, Any]) -> str:
    s = glossary["summary"]
    lines = [
        f"# Glosarium Istilah Teknis ACE — {glossary['repo_name']}",
        "",
        f"> Dibangun otomatis dari definisi Markdown & AST Python statis oleh `tools/program_glossary.py` (`{glossary['schema']}`). Seluruh definisi bersumber langsung dari berkas repositori (nol definisi rekaan).",
        "",
        "## 1. Ringkasan Sumber",
        "",
        f"- Berkas Markdown dipindai: **{s['markdown_files_scanned']}**",
        f"- Berkas Python AST dipindai (non-test): **{s['python_files_scanned']}**",
        f"- Total istilah terindeks: **{s['total_terms_kept']}** (dari {s['total_terms_discovered']} kandidat unik)",
        "",
        "### Komposisi Sumber",
        "",
        "| Jenis Sumber | Jumlah Istilah |",
        "| --- | ---: |",
    ]
    for kind, cnt in sorted(s["kind_counts"].items()):
        lines.append(f"| `{kind}` | {cnt} |")

    lines.extend(
        [
            "",
            "## 2. Daftar Istilah Alfabetis",
            "",
            "| Istilah | Jenis | Sumber & Baris | Definisi Sumber |",
            "| --- | --- | --- | --- |",
        ]
    )
    if glossary["terms"]:
        for item in glossary["terms"]:
            lines.append(
                f"| `{_md_cell(item['term'])}` | `{item['source_kind']}` | "
                f"`{item['path']}:{item['line']}` | {_md_cell(item['definition'])} |"
            )
    else:
        lines.append("| - | - | - | Tidak ada istilah terindeks |")

    return "\n".join(lines) + "\n"


def check_glossary_doc(repo_root: Path, target_file: Path) -> tuple[bool, str]:
    root = repo_root.resolve()
    target = target_file if target_file.is_absolute() else (root / target_file)
    excludes: set[str] = set()
    try:
        excludes.add(target.resolve().relative_to(root).as_posix())
    except ValueError:
        pass
    expected = render_markdown(build_glossary(root, exclude_paths=excludes))
    if not target.is_file():
        return False, f"STALE: berkas glosarium tidak ditemukan: {target}"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"STALE: {target} berbeda dari isi Markdown/AST saat ini."
    return True, f"FRESH: {target} mutakhir dan cocok persis ({len(expected)} karakter)."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pembangkit glosarium program deterministik berbasis Markdown + AST Python."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None, help="Verifikasi kesegaran glosarium (0/1).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            fresh, msg = check_glossary_doc(args.root, args.check)
            print(msg, file=sys.stdout if fresh else sys.stderr)
            return 0 if fresh else 1

        excludes: set[str] = set()
        if args.output is not None:
            out_abs = args.output if args.output.is_absolute() else (args.root.resolve() / args.output)
            try:
                excludes.add(out_abs.resolve().relative_to(args.root.resolve()).as_posix())
            except ValueError:
                pass
        gl = build_glossary(args.root, exclude_paths=excludes)
        rendered = json.dumps(gl, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else render_markdown(gl)
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
