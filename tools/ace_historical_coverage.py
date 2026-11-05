#!/usr/bin/env python3
"""ACE historical test coverage preflight: read-only, fail-closed, no imports.

Parse the TESTS literal from an existing regression runner without executing it.
This gate only verifies whether the declared test source files exist in the
exact checkout. It never claims to execute, pass, or certify those tests.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MODULE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)+")
HEAD = re.compile(r"[0-9a-f]{40}")


class CoverageError(ValueError):
    """The source manifest or checkout is incomplete or untrusted."""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_declared_tests(manifest: bytes) -> dict[str, tuple[str, ...]]:
    """Read a single statically declared TESTS dictionary, with no imports."""
    if not isinstance(manifest, bytes) or not manifest or len(manifest) > 2_000_000:
        raise CoverageError("invalid manifest size/type")
    try:
        tree = ast.parse(manifest, mode="exec")
    except (SyntaxError, ValueError) as exc:
        raise CoverageError("invalid runner syntax") from exc
    declarations = [n for n in tree.body if isinstance(n, ast.Assign) and
                    any(isinstance(target, ast.Name) and target.id == "TESTS"
                        for target in n.targets)]
    if len(declarations) != 1 or len(declarations[0].targets) != 1 or not isinstance(declarations[0].targets[0], ast.Name):
        raise CoverageError("expected exactly one direct static TESTS assignment")
    try:
        value = ast.literal_eval(declarations[0].value)
    except (ValueError, TypeError, RecursionError, MemoryError) as exc:
        raise CoverageError("TESTS must be a literal dictionary") from exc
    if not isinstance(value, dict) or not value:
        raise CoverageError("TESTS must be a nonempty dictionary")
    node = declarations[0].value
    if not isinstance(node, ast.Dict):
        raise CoverageError("TESTS must be a dict literal")
    if len(node.keys) != len(value):
        raise CoverageError("duplicate test group key")
    groups = {}
    for name, modules in value.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            raise CoverageError("invalid group name")
        if not isinstance(modules, (tuple, list)) or not modules:
            raise CoverageError("empty/invalid module group")
        if any(not isinstance(m, str) or not MODULE.fullmatch(m) for m in modules):
            raise CoverageError(f"invalid module identifier for {name}")
        if len(set(modules)) != len(modules):
            raise CoverageError(f"duplicate test module within {name}")
        groups[name] = tuple(modules)
    all_modules = [m for modules in groups.values() for m in modules]
    if len(set(all_modules)) != len(all_modules):
        raise CoverageError("duplicate module across test groups")
    return dict(sorted(groups.items()))


def _regular_file_in(root: Path, relative: Path) -> bool:
    """Reject symlinks and nonfiles in the entire path, not just the leaf."""
    cursor = root
    if not root.is_dir() or root.is_symlink():
        raise CoverageError("invalid checkout directory or symlink root")
    for component in relative.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise CoverageError(f"symlink path forbidden: {relative.as_posix()}")
    return cursor.is_file()


def module_path(module: str) -> Path:
    if not isinstance(module, str) or not MODULE.fullmatch(module):
        raise CoverageError("unsafe module name")
    prefix = Path() if module.startswith("tools.") else Path("code")
    if module.split(".")[0] not in ("tools", "e14", "ace_loop"):
        raise CoverageError(f"unsupported test package prefix: {module}")
    return prefix / (module.replace(".", "/") + ".py")


def checkout_head(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CoverageError("cannot verify git checkout HEAD") from exc
    sha = completed.stdout.strip()
    if completed.returncode != 0 or not HEAD.fullmatch(sha):
        raise CoverageError("cannot establish valid git HEAD")
    return sha


def git_source_inventory(root: Path) -> set[str]:
    """Use committed Git paths, not untracked files, as the evidence inventory."""
    try:
        status = subprocess.run(["git", "-C", str(root), "status", "--porcelain",
                                 "--untracked-files=no"], capture_output=True,
                                timeout=10, check=False)
        tree = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", "HEAD"],
                              capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CoverageError("cannot verify committed Git tree") from exc
    if status.returncode != 0 or tree.returncode != 0:
        raise CoverageError("Git status/tree lookup failed")
    if status.stdout.strip():
        raise CoverageError("TRACKED_CHECKOUT_DIRTY: refuse to certify modified checkout")
    try:
        names = tree.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise CoverageError("non-UTF8 Git tree paths") from exc
    return set(names)


def audit(root: Path, *, expected_head: str, manifest_path: str =
          "tools/ace_e15_regression.py", require_groups: tuple[str, ...] = ()) -> dict:
    if not isinstance(expected_head, str) or not HEAD.fullmatch(expected_head):
        raise CoverageError("expected_head must be exact 40-char lowercase SHA")
    if not isinstance(root, Path):
        raise CoverageError("root must be a Path")
    root = root.absolute()
    head = checkout_head(root)
    if head != expected_head:
        raise CoverageError("CHECKOUT_HEAD_MISMATCH")
    if manifest_path != "tools/ace_e15_regression.py":
        raise CoverageError("manifest must be the declared E1.5 regression runner")
    manifest_relative = Path(manifest_path)
    if not _regular_file_in(root, manifest_relative):
        raise CoverageError("runner manifest missing")
    manifest = (root / manifest_relative).read_bytes()
    inventory = git_source_inventory(root)
    if manifest_path not in inventory:
        raise CoverageError("manifest source is not committed")
    groups = parse_declared_tests(manifest)
    if not isinstance(require_groups, tuple) or any(not isinstance(x, str) for x in require_groups):
        raise CoverageError("invalid required groups")
    unknown = sorted(set(require_groups) - set(groups))
    if unknown:
        raise CoverageError(f"unknown required groups: {unknown}")
    results = []
    for group, modules in groups.items():
        missing = []
        for name in modules:
            relative = module_path(name)
            present = _regular_file_in(root, relative)
            if not present or relative.as_posix() not in inventory:
                missing.append({"module": name, "path": relative.as_posix()})
        results.append({"group": group, "declared_modules": len(modules),
                        "missing": missing,
                        "status": ("MISSING_TEST_SOURCE" if missing else "SOURCE_PRESENT_NOT_EXECUTED")})
    miss_count = sum(len(x["missing"]) for x in results)
    report = {
        "schema_version": 1,
        "status": "INCOMPLETE_HISTORICAL_COVERAGE" if miss_count else "SOURCE_INVENTORY_COMPLETE_TESTS_NOT_RUN",
        "checkout_head": head,
        "manifest_path": manifest_path,
        "manifest_sha256": _sha(manifest),
        "declared_group_count": len(results),
        "declared_test_module_count": sum(len(x) for x in groups.values()),
        "missing_test_source_count": miss_count,
        "historical_tests_executed": 0,
        "historical_tests_passed": 0,
        "scientific_status": "NOT_ASSESSED",
        "groups": results,
    }
    report["report_sha256"] = _sha(canonical(report))
    return report


def write_atomic(path: Path, report: dict) -> None:
    data = json.dumps(report, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        raise CoverageError("refusing to overwrite existing report")
    fd, temporary = tempfile.mkstemp(prefix=".ace-coverage-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.root, expected_head=args.expected_head)
        if args.output:
            write_atomic(args.output, report)
        print(json.dumps(report, sort_keys=True, indent=2))
        return 2 if report["status"] == "INCOMPLETE_HISTORICAL_COVERAGE" else 0
    except (CoverageError, OSError, ValueError) as exc:
        print(json.dumps({"status": "UNKNOWN_INTEGRITY_HALT", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
