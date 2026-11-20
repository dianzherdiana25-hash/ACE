#!/usr/bin/env python3
"""Pemetaan celah tes pada tools/: menemukan modul tanpa berkas tes padanan, terurut menurut ukuran.

Kenapa: tanpa peta celah otomatis, penulisan tes susulan cenderung memilih modul
kecil atau acak sementara utilitas besar di `tools/` luput dari smoke test.
Perkakas statis (AST-only, tanpa mengeksekusi modul target) ini mengurutkan modul
non-tes berdasarkan ukuran byte, memeriksa keberadaan berkas tes padanan maupun
rujukan tes lintas berkas, serta memisahkan wilayah terlarang / skrip satu-pakai
tanpa penjaga `__main__` agar antrean uji aman ditindaklanjuti.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys
from typing import Any

if __package__:
    from ._repo_name import canonical_repo_name
    from .coverage_and_flaky_audit import is_forbidden_path
    from .wiring_audit import _AWAITING_FORBIDDEN_CALLER_PATHS
else:
    from _repo_name import canonical_repo_name
    from coverage_and_flaky_audit import is_forbidden_path
    from wiring_audit import _AWAITING_FORBIDDEN_CALLER_PATHS


SCHEMA = "ace.tools-test-coverage-map.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py")


def _analyze_tool_module(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    size_bytes = len(raw)
    line_count = len(raw.splitlines())
    has_main_guard = False
    has_argparse = False
    parse_error: str | None = None
    try:
        src = raw.decode("utf-8")
        tree = ast.parse(src, filename=path.name)
    except (UnicodeDecodeError, SyntaxError) as exc:
        parse_error = f"{type(exc).__name__}: {exc}"
    else:
        for node in getattr(tree, "body", []):
            if isinstance(node, ast.If):
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                    and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators)
                ):
                    has_main_guard = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name == "argparse" for a in node.names):
                has_argparse = True
            elif isinstance(node, ast.ImportFrom) and node.module == "argparse":
                has_argparse = True
    return {
        "size_bytes": size_bytes,
        "line_count": line_count,
        "has_main_guard": has_main_guard,
        "has_argparse": has_argparse,
        "parse_error": parse_error,
    }


def _collect_test_references(test_files: list[Path]) -> tuple[set[str], dict[str, list[str]]]:
    test_names = {p.name for p in test_files}
    refs_by_stem: dict[str, list[str]] = {}
    parsed_tests: dict[str, tuple[set[str], str]] = {}

    for tp in sorted(test_files):
        text = tp.read_text(encoding="utf-8", errors="ignore")
        imported_stems: set[str] = set()
        try:
            tree = ast.parse(text, filename=tp.name)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_stems.add(alias.name.split(".")[-1])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported_stems.add(node.module.split(".")[-1])
                    for alias in node.names:
                        imported_stems.add(alias.name)
        parsed_tests[tp.name] = (imported_stems, text)

    def refs_for(stem: str, filename: str) -> list[str]:
        if stem in refs_by_stem:
            return refs_by_stem[stem]
        token_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(stem)}(?:\.py)?(?![A-Za-z0-9_])")
        hits = []
        for tname, (imp_stems, raw_text) in parsed_tests.items():
            if stem in imp_stems or filename in raw_text or token_re.search(raw_text):
                hits.append(tname)
        refs_by_stem[stem] = sorted(hits)
        return refs_by_stem[stem]

    # Kembalikan fungsi lookup via closure dictionary builder? Kita pakai lookup langsung
    return test_names, {
        k: v for k, v in parsed_tests.items()
    }


def build_coverage_map(repo_root: Path, *, include_forbidden: bool = False) -> dict[str, Any]:
    """Petakan modul tools/*.py yang belum memiliki berkas tes padanan, terurut menurut ukuran."""
    root = repo_root.resolve()
    tools_dir = root / "tools"
    if not tools_dir.is_dir():
        raise ValueError(f"Direktori tools tidak ditemukan di: {repo_root}")

    all_py = sorted(
        p for p in tools_dir.iterdir()
        if p.is_file() and not p.is_symlink() and p.suffix == ".py"
    )
    test_files = [p for p in all_py if _is_test_file(p)]
    test_names = {p.name for p in test_files}
    mod_files = [p for p in all_py if not _is_test_file(p) and not p.name.startswith("_")]

    parsed_tests: dict[str, tuple[set[str], str]] = {}
    for tp in test_files:
        text = tp.read_text(encoding="utf-8", errors="ignore")
        imp_stems: set[str] = set()
        try:
            tree = ast.parse(text, filename=tp.name)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imp_stems.add(alias.name.split(".")[-1])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imp_stems.add(node.module.split(".")[-1])
                    for alias in node.names:
                        imp_stems.add(alias.name)
        parsed_tests[tp.name] = (imp_stems, text)

    entries: list[dict[str, Any]] = []
    for mod in mod_files:
        rel_posix = f"tools/{mod.name}"
        forbidden = is_forbidden_path(rel_posix) or rel_posix in _AWAITING_FORBIDDEN_CALLER_PATHS
        if forbidden and not include_forbidden:
            continue
        stem = mod.stem
        matching_files = sorted(
            tname for tname in test_names
            if tname == f"test_{stem}.py" or tname.startswith(f"test_{stem}_")
        )
        token_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(stem)}(?:\.py)?(?![A-Za-z0-9_])")
        referenced_by = sorted(
            tname for tname, (imp_stems, raw_text) in parsed_tests.items()
            if stem in imp_stems or mod.name in raw_text or token_re.search(raw_text)
        )
        info = _analyze_tool_module(mod)
        entries.append(
            {
                "module": mod.name,
                "path": rel_posix,
                "size_bytes": info["size_bytes"],
                "line_count": info["line_count"],
                "has_main_guard": info["has_main_guard"],
                "has_argparse": info["has_argparse"],
                "matching_test_files": matching_files,
                "has_matching_test_file": bool(matching_files),
                "referenced_by_tests": referenced_by,
                "has_any_test_coverage": bool(matching_files or referenced_by),
                "is_forbidden": forbidden,
                "parse_error": info["parse_error"],
            }
        )

    entries.sort(key=lambda item: (-item["size_bytes"], item["path"]))

    missing_matching_test = [item for item in entries if not item["has_matching_test_file"]]
    untested_all_gaps = [item for item in entries if not item["has_any_test_coverage"]]
    untested_cli_gaps = [
        item for item in untested_all_gaps
        if item["has_main_guard"] and item["has_argparse"]
    ]

    return {
        "schema": SCHEMA,
        "repo_name": canonical_repo_name(root),
        "summary": {
            "total_modules_scanned": len(entries),
            "test_files_count": len(test_files),
            "with_matching_test_file": len(entries) - len(missing_matching_test),
            "missing_matching_test_file": len(missing_matching_test),
            "untested_all_gaps": len(untested_all_gaps),
            "untested_cli_gaps": len(untested_cli_gaps),
        },
        "top_smoke_candidates": untested_cli_gaps[:3],
        "untested_cli_gaps": untested_cli_gaps,
        "untested_all_gaps": untested_all_gaps,
        "missing_matching_test_file": missing_matching_test,
    }


def render_markdown(report: dict[str, Any], *, top: int = 20) -> str:
    s = report["summary"]
    lines = [
        f"# Peta Celah Tes `tools/` — {report['repo_name']}",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Total modul non-tes dipindai: **{s['total_modules_scanned']}** (`test_*.py`: **{s['test_files_count']}**)",
        f"- Modul tanpa berkas `test_<nama>[_*].py` padanan: **{s['missing_matching_test_file']}**",
        f"- Modul sama sekali belum tersentuh tes (`untested_all_gaps`): **{s['untested_all_gaps']}**",
        f"- Kandidat CLI siap smoke-test (`untested_cli_gaps`): **{s['untested_cli_gaps']}**",
        "",
        "## Kandidat Batch Smoke-Test Teratas (CLI Aman + Belum Tersentuh Tes)",
        "",
        "| Modul | Byte | Baris | `__main__` | `argparse` |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for item in report["untested_cli_gaps"][:top]:
        lines.append(
            f"| `{item['path']}` | {item['size_bytes']} | {item['line_count']} "
            f"| {item['has_main_guard']} | {item['has_argparse']} |"
        )
    if not report["untested_cli_gaps"]:
        lines.append("| - | 0 | 0 | - | - |")

    lines.extend(
        [
            "",
            f"## Seluruh Modul Tanpa Berkas `test_<nama>[_*].py` (Top {top})",
            "",
            "| Modul | Byte | Dirujuk Tes Lain |",
            "| --- | ---: | --- |",
        ]
    )
    for item in report["missing_matching_test_file"][:top]:
        refs = ", ".join(f"`{r}`" for r in item["referenced_by_tests"][:3]) or "-"
        lines.append(f"| `{item['path']}` | {item['size_bytes']} | {refs} |")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--top", type=int, default=20, help="Batas baris teratas pada keluaran Markdown.")
    parser.add_argument("--include-forbidden", action="store_true", help="Sertakan modul wilayah terlarang.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.top <= 0:
            raise ValueError("--top wajib bilangan bulat positif.")
        report = build_coverage_map(args.root, include_forbidden=args.include_forbidden)
        rendered = (
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.format == "json"
            else render_markdown(report, top=args.top)
        )
        if args.output is not None:
            out_path = args.output.resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
