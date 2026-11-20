#!/usr/bin/env python3
"""Auditor status keterhubungan modul (wiring vs orphan vs menunggu engineer utama).

Memindai skrip root, `tools/`, dan `code/` secara statis lewat `ast.parse`
tanpa mengimpor atau mengeksekusi berkas apa pun. Mengklasifikasikan modul ke:
- `MENUNGGU_ENGINEER_UTAMA`: modul di wilayah terlarang (`evo0007_run`, evaluator,
  scorer/instrument aktif, `memory_writeback`, `cognitive_memory`) atau modul yang
  titik sambungannya memang masuk ke wilayah terlarang.
- `WIRED`: diimpor oleh minimal satu pemanggil non-test (skrip root, `tools/`,
  atau modul `code/` non-test).
- `CLI_STANDALONE`: memiliki blok `__main__`, belum dipanggil oleh pemanggil non-test.
- `ORPHAN`: tidak memiliki pemanggil non-test dan bukan entrypoint CLI `__main__`.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

if __package__:
    from ._repo_name import canonical_repo_name
else:
    from _repo_name import canonical_repo_name

WIRING_SCHEMA = "ace.wiring-audit.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv", "checkpoints"})

_FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)evo0007_run\.py$"),
    re.compile(r"^code/ace_evaluator(/|$)"),
    re.compile(r"(^|/)abc_v3_(scorer|run)\.py$"),
    re.compile(r"(^|/)round2_(instrument|gate_run)\.py$"),
    re.compile(r"(^|/)g\d+_instrument\.py$"),
    re.compile(r"(^|/)memory_writeback\.py$"),
    re.compile(r"^code/ace_operational/cognitive_memory\.py$"),
)

# Modul aman yang pemanggil target utamanya berada di jalur terlarang (evo0007 / evaluator / memory write)
_AWAITING_FORBIDDEN_CALLER_PATHS = frozenset(
    {
        "tools/corpus_lint.py",
        "tools/corpus_registry.py",
        "tools/screen_census.py",
        "tools/pattern_distill.py",
        "tools/curriculum_gen.py",
        "tools/four_arm_report.py",
        "tools/corpus_tag.py",
        "tools/verify_f13_f14.py",
    }
)


def is_forbidden_module_path(rel_posix: str) -> bool:
    norm = rel_posix.replace("\\", "/").lstrip("./")
    return any(p.search(norm) for p in _FORBIDDEN_PATTERNS)


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
    if parts and parts[0] == "code":
        aliases.add("code." + mod)
    elif parts and parts[0] == "tools":
        aliases.add(mod.rsplit(".", 1)[-1])
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


def _has_main_guard(tree: ast.AST) -> bool:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators)
            ):
                return True
    return False


def _analyze_python_file(path: Path, rel_posix: str) -> dict[str, Any]:
    mod_name = _canonical_module_name(rel_posix)
    is_init = rel_posix.endswith("/__init__.py") or rel_posix == "__init__.py"
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=rel_posix)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return {
            "path": rel_posix,
            "module": mod_name,
            "aliases": sorted(_module_aliases(rel_posix)),
            "has_main_guard": False,
            "imports": set(),
            "parse_error": f"{type(exc).__name__}: {exc}",
        }

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative_import(mod_name, is_init, node.level, node.module)
                if node.level > 0
                else node.module
            )
            if base:
                imports.add(base)
                for alias in node.names:
                    if alias.name != "*":
                        imports.add(f"{base}.{alias.name}")
            else:
                for alias in node.names:
                    if alias.name != "*":
                        imports.add(alias.name)

    return {
        "path": rel_posix,
        "module": mod_name,
        "aliases": sorted(_module_aliases(rel_posix)),
        "has_main_guard": _has_main_guard(tree),
        "imports": imports,
        "parse_error": None,
    }


def _collect_repo_python_files(root: Path) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    non_test: list[tuple[Path, str]] = []
    tests: list[tuple[Path, str]] = []

    # Skrip tingkat akar
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.is_symlink() or not entry.is_file() or not entry.name.endswith(".py"):
            continue
        rel = entry.relative_to(root).as_posix()
        if _is_test_filename(entry.name):
            tests.append((entry, rel))
        else:
            non_test.append((entry, rel))

    for sub in ("tools", "code", "tests"):
        base = root / sub
        if not base.is_dir() or base.is_symlink():
            continue
        for cur_dir, dirnames, filenames in os.walk(base, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames if d not in IGNORED_DIRS and not (Path(cur_dir) / d).is_symlink()
            )
            for fname in sorted(filenames):
                if not fname.endswith(".py"):
                    continue
                fpath = Path(cur_dir) / fname
                if fpath.is_symlink():
                    continue
                rel = fpath.relative_to(root).as_posix()
                if sub == "tests" or _is_test_filename(fname):
                    tests.append((fpath, rel))
                else:
                    non_test.append((fpath, rel))

    return sorted(non_test, key=lambda x: x[1]), sorted(tests, key=lambda x: x[1])


def audit_wiring(repo_root: Path) -> dict[str, Any]:
    """Lakukan audit keterhubungan modul statis dan tandai modul menunggu engineer utama."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Direktori repositori tidak ditemukan: {repo_root}")

    non_test_paths, test_paths = _collect_repo_python_files(root)

    parsed_non_test: list[dict[str, Any]] = []
    parsed_tests: list[dict[str, Any]] = []

    for fpath, rel in non_test_paths:
        if fpath.name == "__init__.py":
            continue
        parsed_non_test.append(_analyze_python_file(fpath, rel))

    for fpath, rel in test_paths:
        parsed_tests.append(_analyze_python_file(fpath, rel))

    # Bangun indeks alias -> canonical paths
    records: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)

    for target in parsed_non_test:
        t_path = target["path"]
        t_aliases = set(target["aliases"])

        non_test_callers = sorted(
            src["path"]
            for src in parsed_non_test
            if src["path"] != t_path and (src["imports"] & t_aliases)
        )
        test_callers = sorted(
            tsrc["path"]
            for tsrc in parsed_tests
            if (tsrc["imports"] & t_aliases)
        )

        is_forbidden = is_forbidden_module_path(t_path)
        awaiting_forbidden_caller = t_path in _AWAITING_FORBIDDEN_CALLER_PATHS

        if is_forbidden or awaiting_forbidden_caller:
            status = "MENUNGGU_ENGINEER_UTAMA"
            reason = (
                "modul_wilayah_terlarang"
                if is_forbidden
                else "pemanggil_berada_di_jalur_evo0007_atau_evaluator"
            )
        elif non_test_callers:
            status = "WIRED"
            reason = "diimpor_pemanggil_non_test"
        elif target["has_main_guard"]:
            status = "CLI_STANDALONE"
            reason = "entrypoint_cli_mandiri_belum_disambungkan"
        else:
            status = "ORPHAN"
            reason = "tanpa_pemanggil_non_test_dan_tanpa_main"

        status_counts[status] += 1
        records.append(
            {
                "path": t_path,
                "module": target["module"],
                "status": status,
                "reason": reason,
                "has_main_guard": target["has_main_guard"],
                "non_test_callers": non_test_callers,
                "test_callers": test_callers,
                "non_test_caller_count": len(non_test_callers),
                "test_caller_count": len(test_callers),
                "parse_error": target["parse_error"],
            }
        )

    awaiting_entries = [r for r in records if r["status"] == "MENUNGGU_ENGINEER_UTAMA"]
    tools_unwired_safe = [
        r for r in records
        if r["path"].startswith("tools/") and r["status"] in ("CLI_STANDALONE", "ORPHAN")
    ]
    code_orphans_safe = [
        r for r in records
        if r["path"].startswith("code/") and r["status"] == "ORPHAN"
    ]

    return {
        "schema": WIRING_SCHEMA,
        "repo_name": canonical_repo_name(root),
        "summary": {
            "total_modules": len(records),
            "wired": status_counts["WIRED"],
            "cli_standalone": status_counts["CLI_STANDALONE"],
            "orphan": status_counts["ORPHAN"],
            "menunggu_engineer_utama": status_counts["MENUNGGU_ENGINEER_UTAMA"],
            "tools_unwired_safe": len(tools_unwired_safe),
            "code_orphans_safe": len(code_orphans_safe),
        },
        "awaiting_main_engineer": awaiting_entries,
        "tools_unwired_safe": tools_unwired_safe,
        "code_orphans_safe": code_orphans_safe,
        "modules": records,
    }


def render_markdown(report: dict[str, Any], *, max_rows: int = 100) -> str:
    s = report["summary"]
    lines = [
        f"# Audit Keterhubungan Modul & Wilayah Menunggu — {report['repo_name']}",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Total modul non-tes dipindai: {s['total_modules']}",
        f"- `WIRED` (aktif dipakai non-test): {s['wired']}",
        f"- `CLI_STANDALONE` (punya `__main__`, belum tersambung ke orkestrator): {s['cli_standalone']}",
        f"- `ORPHAN` (aman, belum tersambung): {s['orphan']}",
        f"- `MENUNGGU_ENGINEER_UTAMA` (wilayah terlarang / titik sambung EVO 0007 / evaluator / memory writeback): {s['menunggu_engineer_utama']}",
        "",
        "## Daftar Wilayah Menunggu Engineer Utama",
        "",
        "| Modul | Berkas | Alasan |",
        "| --- | --- | --- |",
    ]
    for r in report["awaiting_main_engineer"]:
        lines.append(f"| `{r['module']}` | `{r['path']}` | `{r['reason']}` |")

    lines.extend(["", f"## Perkakas Aman Belum Tersambung di `tools/` ({len(report['tools_unwired_safe'])})", "", "| Berkas | Status | Pemanggil Tes |", "| --- | --- | ---: |"])
    for r in report["tools_unwired_safe"][:max_rows]:
        lines.append(f"| `{r['path']}` | `{r['status']}` | {r['test_caller_count']} |")

    lines.extend(["", f"## Modul Aman `ORPHAN` di `code/` (Top {min(max_rows, len(report['code_orphans_safe']))} dari {len(report['code_orphans_safe'])})", "", "| Berkas | Modul | Pemanggil Tes |", "| --- | --- | ---: |"])
    for r in report["code_orphans_safe"][:max_rows]:
        lines.append(f"| `{r['path']}` | `{r['module']}` | {r['test_caller_count']} |")
    return "\n".join(lines) + "\n"


def _validate_snapshot_report(report: Any, label: str) -> dict[str, str]:
    if (
        not isinstance(report, dict)
        or report.get("schema") != WIRING_SCHEMA
        or not isinstance(report.get("modules"), list)
    ):
        raise ValueError(f"Snapshot audit wiring '{label}' tidak sah (wajib schema {WIRING_SCHEMA}).")
    by_path: dict[str, str] = {}
    for idx, entry in enumerate(report["modules"], 1):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not entry["path"].strip()
            or not isinstance(entry.get("status"), str)
            or not entry["status"].strip()
        ):
            raise ValueError(f"Entri modul ke-{idx} di snapshot '{label}' tidak sah.")
        if entry["path"] in by_path:
            raise ValueError(f"Path modul ganda '{entry['path']}' di snapshot '{label}'.")
        by_path[entry["path"]] = entry["status"]
    return by_path


WIRING_DIFF_SCHEMA = "ace.wiring-audit-diff.v1"


def diff_wiring_snapshots(old_report: dict[str, Any], new_report: dict[str, Any]) -> dict[str, Any]:
    """Bandingkan dua snapshot audit wiring JSON dan laporkan delta perubahan status modul."""
    old_by_path = _validate_snapshot_report(old_report, "lama")
    new_by_path = _validate_snapshot_report(new_report, "baru")

    newly_orphan: list[dict[str, Any]] = []
    newly_wired: list[dict[str, Any]] = []
    unchanged_paths: list[str] = []
    transitions: list[dict[str, Any]] = []
    added_only: list[dict[str, Any]] = []
    removed_only: list[dict[str, Any]] = []

    for path in sorted(old_by_path.keys() | new_by_path.keys()):
        old_status = old_by_path.get(path)
        new_status = new_by_path.get(path)
        if old_status == new_status:
            unchanged_paths.append(path)
            continue
        if new_status == "ORPHAN":
            newly_orphan.append({"path": path, "old_status": old_status, "new_status": new_status})
        if new_status == "WIRED":
            newly_wired.append({"path": path, "old_status": old_status, "new_status": new_status})
        if old_status is None:
            added_only.append({"path": path, "status": new_status})
        elif new_status is None:
            removed_only.append({"path": path, "status": old_status})
        else:
            transitions.append({"path": path, "old_status": old_status, "new_status": new_status})

    old_summary = old_report.get("summary") if isinstance(old_report.get("summary"), dict) else {}
    new_summary = new_report.get("summary") if isinstance(new_report.get("summary"), dict) else {}
    summary_keys = sorted(old_summary.keys() | new_summary.keys())
    summary_delta = {
        k: (new_summary.get(k, 0) - old_summary.get(k, 0))
        for k in summary_keys
        if isinstance(old_summary.get(k, 0), int) and isinstance(new_summary.get(k, 0), int)
    }

    return {
        "schema": WIRING_DIFF_SCHEMA,
        "repo_name": new_report.get("repo_name") or old_report.get("repo_name") or "",
        "summary": {
            "old_total_modules": len(old_by_path),
            "new_total_modules": len(new_by_path),
            "newly_orphan_count": len(newly_orphan),
            "newly_wired_count": len(newly_wired),
            "unchanged_count": len(unchanged_paths),
            "transition_count": len(transitions),
            "added_count": len(added_only),
            "removed_count": len(removed_only),
        },
        "summary_delta": summary_delta,
        "newly_orphan": newly_orphan,
        "newly_wired": newly_wired,
        "unchanged_modules": unchanged_paths,
        "transitions": transitions,
        "added_only": added_only,
        "removed_only": removed_only,
    }


def render_diff_markdown(diff_report: dict[str, Any]) -> str:
    s = diff_report["summary"]
    lines = [
        f"# Diff Snapshot Audit Keterhubungan Modul — {diff_report['repo_name'] or 'ACE'}",
        "",
        f"- Schema: `{diff_report['schema']}`",
        f"- Total modul (lama → baru): {s['old_total_modules']} → {s['new_total_modules']}",
        f"- Baru yatim (`newly_orphan`): **{s['newly_orphan_count']}**",
        f"- Baru terhubung (`newly_wired`): **{s['newly_wired_count']}**",
        f"- Hitungan tak berubah (`unchanged_count`): **{s['unchanged_count']}**",
        "",
        f"## Modul Baru Yatim ({s['newly_orphan_count']})",
        "",
    ]
    if diff_report["newly_orphan"]:
        for item in diff_report["newly_orphan"]:
            old_lbl = item["old_status"] or "(modul baru)"
            lines.append(f"- `{item['path']}` (`{old_lbl}` → `{item['new_status']}`)")
    else:
        lines.append("- (tidak ada)")

    lines.extend(["", f"## Modul Baru Terhubung ({s['newly_wired_count']})", ""])
    if diff_report["newly_wired"]:
        for item in diff_report["newly_wired"]:
            old_lbl = item["old_status"] or "(modul baru)"
            lines.append(f"- `{item['path']}` (`{old_lbl}` → `{item['new_status']}`)")
    else:
        lines.append("- (tidak ada)")

    lines.extend(["", f"## Transisi Status Lain & Modul Tambah/Hapus ({s['transition_count']} transisi, +{s['added_count']} / -{s['removed_count']})", ""])
    for item in diff_report["transitions"]:
        lines.append(f"- `{item['path']}` (`{item['old_status']}` → `{item['new_status']}`)")
    for item in diff_report["added_only"]:
        lines.append(f"- `+ {item['path']}` (`{item['status']}`)")
    for item in diff_report["removed_only"]:
        lines.append(f"- `- {item['path']}` (`{item['status']}`)")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit keterhubungan modul (wiring vs orphan vs menunggu engineer utama).")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Direktori akar repo target.")
    parser.add_argument("--diff", type=Path, default=None, help="Bandingkan snapshot audit JSON lama dengan audit terbaru / --new.")
    parser.add_argument("--new", type=Path, default=None, help="Snapshot audit JSON baru (opsional, dipakai bersama --diff).")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Format keluaran.")
    parser.add_argument("--output", type=Path, default=None, help="Tulis keluaran ke berkas.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.new is not None and args.diff is None:
            raise ValueError("--new hanya dapat dipakai bersama --diff.")
        if args.diff is not None:
            old_report = json.loads(args.diff.read_text(encoding="utf-8"))
            new_report = (
                json.loads(args.new.read_text(encoding="utf-8"))
                if args.new is not None
                else audit_wiring(args.root)
            )
            diff_rep = diff_wiring_snapshots(old_report, new_report)
            rendered = (
                json.dumps(diff_rep, indent=2, ensure_ascii=False) + "\n"
                if args.format == "json"
                else render_diff_markdown(diff_rep)
            )
        else:
            report = audit_wiring(args.root)
            rendered = (
                json.dumps(report, indent=2, ensure_ascii=False) + "\n"
                if args.format == "json"
                else render_markdown(report)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
