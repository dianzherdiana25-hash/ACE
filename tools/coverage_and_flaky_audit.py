#!/usr/bin/env python3
"""Auditor cakupan simbol test (AST) dan detektor tes flaky non-verdict.

Perkakas standalone (stdlib-only) untuk:
1. Memindai modul Python non-terlarang di `tools/` dan `code/` secara statis
   lewat `ast.parse` (tanpa mengimpor atau mengeksekusi modul) dan memetakan
   fungsi/kelas publik ke berkas tes di `tools/`, `code/`, dan `tests/`.
2. Menjalankan target `unittest` yang diminta secara berulang (N kali) dalam
   subproses terisolasi (`PYTHONDONTWRITEBYTECODE=1`), mengukur varians waktu
   eksekusi, mendeteksi inkonsistensi pass/fail, dan memeriksa kebersihan tree.

Wilayah terlarang (evo0007_run, ace_evaluator, scorer/instrument aktif, jalur
tulis memori) dilewati secara eksplisit dan ditolak oleh runner.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
from typing import Any

AUDIT_SCHEMA = "ace.coverage-flaky-audit.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "checkpoints"})

_FORBIDDEN_PATH_PATTERNS = (
    re.compile(r"(^|/)evo0007_run\.py$"),
    re.compile(r"^code/ace_evaluator(/|$)"),
    re.compile(r"(^|/)abc_v3_(scorer|run)\.py$"),
    re.compile(r"(^|/)round2_(instrument|gate_run)\.py$"),
    re.compile(r"(^|/)g\d+_instrument\.py$"),
    re.compile(r"(^|/)memory_writeback\.py$"),
    re.compile(r"^code/ace_operational/cognitive_memory\.py$"),
    re.compile(r"(^|/)(test_)?(evo0007|sealed_evaluator|abc_v3_scorer|round2_instrument|g\d+_instrument|memory_writeback)(_.*)?\.py$"),
)

_FORBIDDEN_TARGET_PATTERNS = (
    re.compile(r"(?:^|[./])evo0007_run(?:$|[./])"),
    re.compile(r"(?:^|[./])ace_evaluator(?:$|[./])"),
    re.compile(r"(?:^|[./])abc_v3_(?:scorer|run)(?:$|[./])"),
    re.compile(r"(?:^|[./])round2_(?:instrument|gate_run)(?:$|[./])"),
    re.compile(r"(?:^|[./])g\d+_instrument(?:$|[./])"),
    re.compile(r"(?:^|[./])memory_writeback(?:$|[./])"),
    re.compile(r"(?:^|[./])cognitive_memory(?:$|[./])"),
    re.compile(r"(?:^|[./])tests/e2e(?:$|[./])"),
)

_RAN_RE = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s")
_SAFE_TARGET_RE = re.compile(r"^[A-Za-z0-9_./:-]+$")


def is_forbidden_path(rel_posix: str) -> bool:
    """Kembalikan True jika path berada di wilayah instrumen/verdict/memori terlarang."""
    normalized = rel_posix.replace("\\", "/").lstrip("./")
    return any(pat.search(normalized) for pat in _FORBIDDEN_PATH_PATTERNS)


def is_forbidden_target(target: str) -> bool:
    """Kembalikan True jika target unittest menunjuk wilayah terlarang."""
    normalized = target.strip().replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return any(pat.search(normalized) for pat in _FORBIDDEN_TARGET_PATTERNS)


def _is_test_filename(name: str) -> bool:
    return name.startswith("test_") or name.endswith("_test.py")


def _canonical_module_name(rel_posix: str) -> str:
    parts = list(Path(rel_posix).parts)
    if parts and parts[0] == "code" and len(parts) > 1:
        parts = parts[1:]
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts) if parts else "__init__"


def _module_aliases(rel_posix: str) -> set[str]:
    mod = _canonical_module_name(rel_posix)
    aliases = {mod}
    parts = list(Path(rel_posix).parts)
    stem_mod = mod.rsplit(".", 1)[-1]
    if parts and parts[0] == "code":
        aliases.add("code." + mod)
    elif parts and parts[0] == "tools":
        aliases.add(stem_mod)
    return aliases


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


def extract_module_symbols(path: Path, rel_posix: str) -> dict[str, Any]:
    """Ekstrak daftar simbol publik tingkat-atas modul Python via AST (tanpa eksekusi)."""
    mod_name = _canonical_module_name(rel_posix)
    aliases = sorted(_module_aliases(rel_posix))
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_posix)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "module": mod_name,
            "path": rel_posix,
            "aliases": aliases,
            "parse_error": f"{type(exc).__name__}: {exc}",
            "symbols": [],
        }

    symbols: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if not name.startswith("_") and name not in seen_names:
                seen_names.add(name)
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                symbols.append({"name": name, "kind": kind, "lineno": node.lineno})

    return {
        "module": mod_name,
        "path": rel_posix,
        "aliases": aliases,
        "parse_error": None,
        "symbols": symbols,
    }


def extract_test_references(path: Path, rel_posix: str) -> dict[str, Any]:
    """Ekstrak modul yang diimpor dan nama/atribut yang direferensikan berkas tes via AST."""
    test_mod = _canonical_module_name(rel_posix)
    is_init = rel_posix.endswith("/__init__.py") or rel_posix == "__init__.py"
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel_posix)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "path": rel_posix,
            "test_module": test_mod,
            "parse_error": f"{type(exc).__name__}: {exc}",
            "imported_modules": set(),
            "imported_symbols_by_module": defaultdict(set),
            "referenced_names": set(),
            "referenced_attrs": set(),
        }

    imported_modules: set[str] = set()
    imported_symbols_by_module: dict[str, set[str]] = defaultdict(set)
    referenced_names: set[str] = set()
    referenced_attrs: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
                if alias.asname:
                    referenced_names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            base_mod: str | None = None
            if node.level > 0:
                base_mod = _resolve_relative_import(test_mod, is_init, node.level, node.module)
            elif node.module:
                base_mod = node.module

            if base_mod:
                imported_modules.add(base_mod)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    imported_modules.add(f"{base_mod}.{alias.name}")
                    imported_symbols_by_module[base_mod].add(alias.name)
            else:
                for alias in node.names:
                    if alias.name != "*":
                        imported_modules.add(alias.name)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced_attrs.add(node.attr)

    return {
        "path": rel_posix,
        "test_module": test_mod,
        "parse_error": None,
        "imported_modules": imported_modules,
        "imported_symbols_by_module": imported_symbols_by_module,
        "referenced_names": referenced_names,
        "referenced_attrs": referenced_attrs,
    }


def _collect_py_files(root: Path, subdirs: tuple[str, ...]) -> list[tuple[Path, str]]:
    collected: list[tuple[Path, str]] = []
    for sub in subdirs:
        base = root / sub
        if not base.is_dir() or base.is_symlink():
            continue
        for cur_dir, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink()
            )
            filenames.sort()
            cur = Path(cur_dir)
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = cur / fname
                if fpath.is_symlink():
                    continue
                rel_posix = fpath.relative_to(root).as_posix()
                collected.append((fpath, rel_posix))
    return sorted(collected, key=lambda item: item[1])


def _is_test_linked_to_module(test_info: dict[str, Any], mod_aliases: set[str], mod_stem: str) -> bool:
    imported_mods = test_info["imported_modules"]
    if imported_mods & mod_aliases:
        return True
    for alias in mod_aliases:
        parent = alias.rsplit(".", 1)[0] if "." in alias else ""
        if parent and parent in imported_mods and (
            mod_stem in test_info["referenced_names"] or mod_stem in test_info["referenced_attrs"]
        ):
            return True
    return False


def audit_symbol_coverage(repo_root: Path) -> dict[str, Any]:
    """Audit cakupan simbol publik pada modul non-terlarang di `tools/` dan `code/`."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    src_candidates = _collect_py_files(root, ("tools", "code"))
    test_candidates = _collect_py_files(root, ("tools", "code", "tests"))

    skipped_forbidden: set[str] = set()
    source_modules: list[dict[str, Any]] = []
    test_refs: list[dict[str, Any]] = []

    for fpath, rel_posix in src_candidates:
        if is_forbidden_path(rel_posix):
            skipped_forbidden.add(rel_posix)
            continue
        fname = fpath.name
        if fname == "__init__.py" or _is_test_filename(fname):
            continue
        info = extract_module_symbols(fpath, rel_posix)
        source_modules.append(info)

    for fpath, rel_posix in test_candidates:
        if is_forbidden_path(rel_posix):
            skipped_forbidden.add(rel_posix)
            continue
        if _is_test_filename(fpath.name):
            test_refs.append(extract_test_references(fpath, rel_posix))

    module_reports: list[dict[str, Any]] = []
    pkg_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"modules": 0, "modules_with_tests": 0, "total_symbols": 0, "covered_symbols": 0}
    )

    total_symbols = 0
    covered_symbols = 0
    modules_with_tests = 0
    uncovered_modules: list[str] = []

    for mod in source_modules:
        aliases = set(mod["aliases"])
        mod_stem = Path(mod["path"]).stem
        linked = [t for t in test_refs if _is_test_linked_to_module(t, aliases, mod_stem)]

        direct_imported: set[str] = set()
        used_tokens: set[str] = set()
        for t in linked:
            for alias in aliases:
                direct_imported.update(t["imported_symbols_by_module"].get(alias, set()))
            used_tokens.update(t["referenced_names"])
            used_tokens.update(t["referenced_attrs"])

        sym_names = [s["name"] for s in mod["symbols"]]
        cov_syms = [s for s in sym_names if s in direct_imported or s in used_tokens]
        uncov_syms = [s for s in sym_names if s not in cov_syms]

        has_tests = len(linked) > 0
        if has_tests:
            modules_with_tests += 1
        elif sym_names:
            uncovered_modules.append(mod["path"])

        total_symbols += len(sym_names)
        covered_symbols += len(cov_syms)

        parts = Path(mod["path"]).parts
        pkg_key = "/".join(parts[:2]) if len(parts) >= 2 and parts[0] == "code" else parts[0]
        pstat = pkg_stats[pkg_key]
        pstat["modules"] += 1
        if has_tests:
            pstat["modules_with_tests"] += 1
        pstat["total_symbols"] += len(sym_names)
        pstat["covered_symbols"] += len(cov_syms)

        pct = round((len(cov_syms) / len(sym_names) * 100.0), 1) if sym_names else 100.0
        module_reports.append(
            {
                "module": mod["module"],
                "path": mod["path"],
                "parse_error": mod["parse_error"],
                "public_symbol_count": len(sym_names),
                "covered_symbol_count": len(cov_syms),
                "coverage_pct": pct,
                "covered_symbols": cov_syms,
                "uncovered_symbols": uncov_syms,
                "linked_test_files": sorted(t["path"] for t in linked),
            }
        )

    package_summary = [
        {
            "package": pkg,
            "modules": st["modules"],
            "modules_with_tests": st["modules_with_tests"],
            "total_symbols": st["total_symbols"],
            "covered_symbols": st["covered_symbols"],
            "coverage_pct": round((st["covered_symbols"] / st["total_symbols"] * 100.0), 1)
            if st["total_symbols"]
            else 100.0,
        }
        for pkg, st in sorted(pkg_stats.items())
    ]

    overall_pct = round((covered_symbols / total_symbols * 100.0), 1) if total_symbols else 100.0
    total_modules = len(module_reports)

    return {
        "summary": {
            "total_source_modules": total_modules,
            "modules_with_tests": modules_with_tests,
            "modules_without_tests": len(uncovered_modules),
            "test_files_scanned": len(test_refs),
            "total_public_symbols": total_symbols,
            "covered_public_symbols": covered_symbols,
            "uncovered_public_symbols": total_symbols - covered_symbols,
            "symbol_coverage_pct": overall_pct,
            "forbidden_skipped_count": len(skipped_forbidden),
        },
        "package_summary": package_summary,
        "uncovered_modules": sorted(uncovered_modules),
        "skipped_forbidden": sorted(skipped_forbidden),
        "modules": module_reports,
    }


def _file_digest(path: Path) -> str:
    try:
        st = path.stat()
        if st.st_size > 2_000_000:
            return f"stat:{st.st_size}:{st.st_mtime_ns}"
        data = path.read_bytes()
        return f"size:{st.st_size}:ns:{st.st_mtime_ns}:sha1:{hashlib.sha1(data).hexdigest()}"
    except OSError:
        return "missing"


def _snapshot_tree_state(root: Path) -> dict[str, str]:
    """Ambil snapshot deterministik status working tree (git atau digest berkas)."""
    if (root / ".git").exists():
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            state: dict[str, str] = {}
            for line in proc.stdout.splitlines():
                if len(line) < 4:
                    continue
                status_code = line[:2]
                rel_part = line[3:].strip()
                if " -> " in rel_part:
                    rel_part = rel_part.split(" -> ", 1)[1]
                target = root / rel_part
                digest = _file_digest(target) if target.is_file() else status_code
                state[rel_part] = f"{status_code}:{digest}"
            return state

    entries: dict[str, str] = {}
    for cur_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink())
        for fname in sorted(filenames):
            fpath = Path(cur_dir) / fname
            if fpath.is_symlink():
                continue
            rel = fpath.relative_to(root).as_posix()
            entries[rel] = _file_digest(fpath)
    return entries


def validate_targets(targets: list[str]) -> list[str]:
    """Validasi daftar target unittest dari karakter tidak aman dan wilayah terlarang."""
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets harus berupa list non-kosong")
    cleaned: list[str] = []
    for raw in targets:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Setiap target harus berupa string non-kosong")
        t = raw.strip()
        if t.startswith("-") or not _SAFE_TARGET_RE.fullmatch(t):
            raise ValueError(f"Format target tidak valid: {t}")
        if is_forbidden_target(t):
            raise ValueError(f"Target berada di wilayah terlarang: {t}")
        cleaned.append(t)
    return cleaned


def run_flaky_audit(
    repo_root: Path,
    targets: list[str],
    runs: int = 3,
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    """Jalankan setiap target `unittest` N kali untuk mendeteksi flakiness & residu tree."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 1:
        raise ValueError("runs harus bilangan bulat >= 1")
    if isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float)) or not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ValueError("timeout_sec harus angka berhingga > 0")

    clean_targets = validate_targets(targets)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    python_paths = [str(root / "code"), str(root)]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)

    results: list[dict[str, Any]] = []
    for target in clean_targets:
        statuses: list[str] = []
        durations_ms: list[float] = []
        test_counts: list[int] = []
        dirty_files: set[str] = set()

        for _ in range(runs):
            before = _snapshot_tree_state(root)
            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "unittest", target],
                    cwd=str(root),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=float(timeout_sec),
                    check=False,
                )
                elapsed_ms = round((time.monotonic() - t0) * 1000.0, 2)
                combined_out = (proc.stdout or "") + "\n" + (proc.stderr or "")
                m = _RAN_RE.search(combined_out)
                if m:
                    test_counts.append(int(m.group(1)))
                statuses.append("PASS" if proc.returncode == 0 else "FAIL")
                durations_ms.append(elapsed_ms)
            except subprocess.TimeoutExpired:
                elapsed_ms = round((time.monotonic() - t0) * 1000.0, 2)
                statuses.append("TIMEOUT")
                durations_ms.append(elapsed_ms)

            after = _snapshot_tree_state(root)
            diff = {k for k in (before.keys() | after.keys()) if before.get(k) != after.get(k)}
            if diff:
                dirty_files.update(sorted(diff))

        passed_runs = sum(1 for s in statuses if s == "PASS")
        failed_runs = sum(1 for s in statuses if s == "FAIL")
        timeout_runs = sum(1 for s in statuses if s == "TIMEOUT")
        unique_outcomes = set(statuses)
        tree_clean = len(dirty_files) == 0
        is_flaky = len(unique_outcomes) > 1 or not tree_clean
        all_passed = passed_runs == runs and tree_clean
        consistent_fail = passed_runs == 0 and runs > 0

        mean_ms = round(statistics.mean(durations_ms), 2) if durations_ms else 0.0
        stdev_ms = round(statistics.stdev(durations_ms), 2) if len(durations_ms) >= 2 else 0.0
        results.append(
            {
                "target": target,
                "runs": runs,
                "passed_runs": passed_runs,
                "failed_runs": failed_runs,
                "timeout_runs": timeout_runs,
                "statuses": statuses,
                "flaky": is_flaky,
                "all_passed": all_passed,
                "consistent_fail": consistent_fail,
                "tree_clean": tree_clean,
                "dirty_entries": sorted(dirty_files),
                "test_counts": test_counts,
                "mean_ms": mean_ms,
                "stdev_ms": stdev_ms,
                "min_ms": min(durations_ms) if durations_ms else 0.0,
                "max_ms": max(durations_ms) if durations_ms else 0.0,
            }
        )

    flaky_count = sum(1 for r in results if r["flaky"])
    failing_count = sum(1 for r in results if r["consistent_fail"])
    passing_count = sum(1 for r in results if r["all_passed"])
    dirty_count = sum(1 for r in results if not r["tree_clean"])

    return {
        "summary": {
            "runs_per_target": runs,
            "target_count": len(results),
            "passing_targets": passing_count,
            "flaky_targets": flaky_count,
            "failing_targets": failing_count,
            "dirty_targets": dirty_count,
            "passed": flaky_count == 0 and failing_count == 0 and dirty_count == 0,
        },
        "targets": results,
    }


def build_audit_report(
    repo_root: Path,
    targets: list[str] | None = None,
    runs: int = 3,
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    """Susun laporan audit cakupan AST + deteksi flaky terpadu."""
    coverage = audit_symbol_coverage(repo_root)
    flaky = run_flaky_audit(repo_root, targets, runs=runs, timeout_sec=timeout_sec) if targets else None
    return {
        "schema": AUDIT_SCHEMA,
        "repo_name": repo_root.resolve().name,
        "coverage": coverage,
        "flaky": flaky,
    }


def render_markdown_report(report: dict[str, Any], top_uncovered: int = 25) -> str:
    """Render hasil audit menjadi laporan Markdown deterministik."""
    cov = report["coverage"]
    csum = cov["summary"]
    lines = [
        f"# Audit Cakupan Simbol & Deteksi Tes Flaky — {report['repo_name']}",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Modul sumber dipindai (non-terlarang): {csum['total_source_modules']}",
        f"- Modul punya berkas tes tertaut: {csum['modules_with_tests']} / {csum['total_source_modules']}",
        f"- Modul bersimbol publik tanpa tes tertaut: {csum['modules_without_tests']}",
        f"- Berkas tes dipindai: {csum['test_files_scanned']}",
        f"- Cakupan simbol publik (AST): {csum['covered_public_symbols']} / {csum['total_public_symbols']} ({csum['symbol_coverage_pct']}%)",
        f"- Wilayah terlarang dilewati eksplisit: {csum['forbidden_skipped_count']} berkas",
        "",
        "## Ringkasan Cakupan per Paket",
        "",
        "| Paket | Modul | Modul dgn Tes | Simbol Tercakup | Total Simbol | Cakupan |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for pkg in cov["package_summary"]:
        lines.append(
            f"| `{pkg['package']}` | {pkg['modules']} | {pkg['modules_with_tests']} | "
            f"{pkg['covered_symbols']} | {pkg['total_symbols']} | {pkg['coverage_pct']}% |"
        )

    uncovered_mods = [m for m in cov["modules"] if not m["linked_test_files"] and m["public_symbol_count"] > 0]
    lines.extend(["", f"## Modul Bersimbol Publik Tanpa Tes Tertaut (Top {min(top_uncovered, len(uncovered_mods))} dari {len(uncovered_mods)})", ""])
    if uncovered_mods:
        lines.append("| Modul | Berkas | Jumlah Simbol Publik |")
        lines.append("| --- | --- | ---: |")
        for m in uncovered_mods[:top_uncovered]:
            lines.append(f"| `{m['module']}` | `{m['path']}` | {m['public_symbol_count']} |")
    else:
        lines.append("- Tidak ada modul tanpa tes tertaut.")

    flaky = report.get("flaky")
    lines.extend(["", "## Audit Tes Flaky (Subproses Berulang)", ""])
    if flaky is None:
        lines.append("- Mode cakupan-saja (`--targets` tidak diberikan / `--skip-flaky`).")
    else:
        fsum = flaky["summary"]
        lines.extend(
            [
                f"- Target diuji: {fsum['target_count']} (masing-masing {fsum['runs_per_target']} eksekusi)",
                f"- Konsisten lulus & tree bersih: {fsum['passing_targets']}",
                f"- Flaky terdeteksi: {fsum['flaky_targets']}",
                f"- Konsisten gagal: {fsum['failing_targets']}",
                f"- Kotor tree (dirty_targets): {fsum['dirty_targets']}",
                f"- Status keseluruhan: `{'PASS' if fsum['passed'] else 'FAIL'}`",
                "",
                "| Target | Lulus/Run | Flaky | Tree Bersih | Rerata (ms) | Stdev (ms) |",
                "| --- | ---: | --- | --- | ---: | ---: |",
            ]
        )
        for item in flaky["targets"]:
            lines.append(
                f"| `{item['target']}` | {item['passed_runs']}/{item['runs']} | "
                f"{'YA' if item['flaky'] else 'TIDAK'} | {'YA' if item['tree_clean'] else 'TIDAK'} | "
                f"{item['mean_ms']} | {item['stdev_ms']} |"
            )

    lines.extend(["", "## Berkas Wilayah Terlarang yang Dilewati Eksplisit", ""])
    for item in cov["skipped_forbidden"]:
        lines.append(f"- `{item}`")

    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit cakupan simbol AST dan deteksi tes flaky non-verdict ACE."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--runs", type=int, default=3, help="Jumlah pengulangan tiap target unittest.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Batas waktu per run (detik).")
    parser.add_argument(
        "--targets",
        nargs="+",
        default=None,
        help="Target unittest yang akan diuji ulang untuk deteksi flaky.",
    )
    parser.add_argument(
        "--skip-flaky",
        action="store_true",
        help="Jalankan audit cakupan simbol AST saja tanpa eksekusi unittest.",
    )
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
        targets = None if args.skip_flaky else args.targets
        report = build_audit_report(args.root, targets=targets, runs=args.runs, timeout_sec=args.timeout)
        rendered = (
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.format == "json"
            else render_markdown_report(report)
        )
        if args.output is not None:
            out_path = args.output.resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    flaky = report.get("flaky")
    if flaky is not None and not flaky["summary"]["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
