#!/usr/bin/env python3
"""Generator indeks repositori otomatis berformat Markdown deterministik.

Memetakan berkas per direktori (terurut stabil, mengabaikan artefak VCS/cache)
serta menyusun peta modul Python berisi nama modul, baris pertama docstring,
dan daftar dependensi internal antar modul di dalam repositori.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

INDEX_SCHEMA = "ace.repo-index.v1"

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

REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"})


def _categorize_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    if ext in (".md", ".rst", ".txt"):
        return "docs"
    if ext in (".json", ".jsonl", ".yaml", ".yml", ".toml"):
        return "data"
    if ext in (".sh", ".bash"):
        return "scripts"
    return "other"


def _module_name_for_py(rel_posix: str) -> str:
    parts = list(Path(rel_posix).parts)
    if parts and parts[0] == "code" and len(parts) > 1:
        parts = parts[1:]
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts) if parts else "__init__"


def _parse_python_module(path: Path, rel_posix: str) -> dict[str, Any]:
    mod_name = _module_name_for_py(rel_posix)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_posix)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return {
            "module": mod_name,
            "path": rel_posix,
            "docstring": "",
            "raw_imports": [],
            "from_imports": [],
            "relative_imports": [],
        }

    doc = ast.get_docstring(tree) or ""
    first_line = doc.strip().splitlines()[0].strip() if doc.strip() else ""

    raw_imports: list[str] = []
    from_imports: list[tuple[str, list[str]]] = []
    relative_imports: list[tuple[int, str | None, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                names = [a.name for a in node.names if a.name != "*"]
                relative_imports.append((node.level, node.module, names))
            elif node.module:
                names = [a.name for a in node.names if a.name != "*"]
                from_imports.append((node.module, names))

    return {
        "module": mod_name,
        "path": rel_posix,
        "docstring": first_line,
        "raw_imports": raw_imports,
        "from_imports": from_imports,
        "relative_imports": relative_imports,
    }


def _resolve_relative_import(current_mod: str, is_pkg_init: bool, level: int, target: str | None) -> str | None:
    parts = current_mod.split(".") if current_mod else []
    pkg_parts = parts if is_pkg_init else parts[:-1]
    up = level - 1
    if up > len(pkg_parts):
        return None
    base = pkg_parts[: len(pkg_parts) - up]
    if target:
        base.extend(target.split("."))
    return ".".join(base) if base else None


def build_repo_index(repo_root: Path) -> dict[str, Any]:
    """Pindai `repo_root` secara deterministik dan kembalikan struktur indeks repo."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    dirs_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    py_raw: list[dict[str, Any]] = []

    for cur_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink())
        filenames.sort()
        cur = Path(cur_dir)
        rel_dir = cur.relative_to(root).as_posix()
        dir_label = "." if rel_dir == "." else rel_dir
        for fname in filenames:
            fpath = cur / fname
            if fpath.is_symlink():
                continue
            rel_posix = fpath.relative_to(root).as_posix()
            dirs_map[dir_label].append(
                {
                    "name": fname,
                    "path": rel_posix,
                    "category": _categorize_file(fpath),
                }
            )
            if fpath.suffix.lower() == ".py":
                py_raw.append(_parse_python_module(fpath, rel_posix))

    known_modules = {m["module"] for m in py_raw}
    modules: list[dict[str, Any]] = []
    for item in sorted(py_raw, key=lambda x: (x["module"], x["path"])):
        is_init = item["path"].endswith("/__init__.py") or item["path"] == "__init__.py"
        deps: set[str] = set()
        for imp in item["raw_imports"]:
            if imp in known_modules and imp != item["module"]:
                deps.add(imp)
            else:
                prefix = imp.rsplit(".", 1)[0] if "." in imp else imp
                if prefix in known_modules and prefix != item["module"]:
                    deps.add(prefix)
        for mod_target, names in item["from_imports"]:
            matched_sub = False
            for name in names:
                cand = f"{mod_target}.{name}"
                if cand in known_modules and cand != item["module"]:
                    deps.add(cand)
                    matched_sub = True
            if (not matched_sub or not names) and mod_target in known_modules and mod_target != item["module"]:
                deps.add(mod_target)
        for level, target, names in item["relative_imports"]:
            resolved = _resolve_relative_import(item["module"], is_init, level, target)
            matched_rel = False
            for sub_name in names:
                sub_mod = f"{resolved}.{sub_name}" if resolved else sub_name
                if sub_mod in known_modules and sub_mod != item["module"]:
                    deps.add(sub_mod)
                    matched_rel = True
            if (not matched_rel or not names) and resolved and resolved in known_modules and resolved != item["module"]:
                deps.add(resolved)

        modules.append(
            {
                "module": item["module"],
                "path": item["path"],
                "docstring": item["docstring"],
                "internal_deps": sorted(deps),
            }
        )

    directories = [
        {
            "directory": dname,
            "file_count": len(dirs_map[dname]),
            "files": sorted(dirs_map[dname], key=lambda f: f["name"]),
        }
        for dname in sorted(dirs_map)
    ]

    return {
        "schema": INDEX_SCHEMA,
        "repo_name": _canonical_repo_name(root),
        "directory_count": len(directories),
        "file_count": sum(d["file_count"] for d in directories),
        "module_count": len(modules),
        "directories": directories,
        "python_modules": modules,
    }


def render_markdown_index(index: dict[str, Any]) -> str:
    """Render objek indeks menjadi dokumen Markdown deterministik."""
    lines = [
        f"# Indeks Repositori — {index['repo_name']}",
        "",
        f"- Schema: `{index['schema']}`",
        f"- Total direktori: {index['directory_count']}",
        f"- Total berkas: {index['file_count']}",
        f"- Total modul Python: {index['module_count']}",
        "",
        "## Daftar Berkas per Direktori",
        "",
    ]

    for entry in index["directories"]:
        lines.append(f"### `{entry['directory']}` ({entry['file_count']} berkas)")
        for fitem in entry["files"]:
            lines.append(f"- `{fitem['name']}` ({fitem['category']})")
        lines.append("")

    lines.extend(
        [
            "## Peta Modul Python",
            "",
            "| Modul | Berkas | Docstring | Dependensi Internal |",
            "| --- | --- | --- | --- |",
        ]
    )
    for mod in index["python_modules"]:
        doc = mod["docstring"].replace("|", "\\|") if mod["docstring"] else "-"
        deps = ", ".join(f"`{d}`" for d in mod["internal_deps"]) if mod["internal_deps"] else "-"
        lines.append(f"| `{mod['module']}` | `{mod['path']}` | {doc} | {deps} |")

    if not index["python_modules"]:
        lines.append("| - | - | Tidak ada modul Python | - |")

    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bangun indeks Markdown/JSON repositori ACE secara deterministik."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Format keluaran (default: markdown).",
    )
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        idx = build_repo_index(args.root)
        rendered = (
            json.dumps(idx, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown_index(idx)
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
