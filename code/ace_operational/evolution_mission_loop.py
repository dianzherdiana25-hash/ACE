"""AI-Agnostic Passive Evolution Work-Order Loop (`evolution_mission_loop.py`).

Enables a continuous closed loop between ACE and *any* external AI or developer:
  1. ``RealRepoAuditor`` scans editable ACE Python modules + test suites +
     Compositional OAIE artifacts to surface real, deterministic findings with
     exact file paths, line ranges, and measured AST/runtime metrics.
  2. ``PassiveEvolutionPlanner`` ranks unresolved findings, snapshots file
     SHA-256 digests and test assertion baselines, and emits self-contained
     work orders (``EVOLUTION_WORK_ORDER.json``, ``EVOLUTION_WORK_ORDER.md``,
     ``EVOLUTION_BACKLOG.json``) ready for any AI (Antigravity, Claude, Codex,
     Gemini) to execute.
  3. ``EvolutionPatchVerifier`` verifies candidate edits fail-closed after the
     AI edits ACE: checking custody & ``UPSTREAM_SOURCES.json`` pins, rejecting
     no-op or syntax-broken edits, running AST anti-cheat checks (no newly added
     hardcoded ``"verified": True``, no newly added silent ``except: pass``, no
     deleted test assertions), running acceptance tests + target metric checks,
     and ratifying passing evolutions into ``StigmergicDAGMemory`` +
     ``SubstrateSpore`` (or quarantining failures into ``counterexample_fossil``).
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from .local_repo_workflow import atomic_write_verified
from .memory_writeback import (
    recall_context,
    record_event_outcomes,
    record_verified_event,
)
from .sovereign_runtime import SovereignRuntimeSupervisor, SubstrateSpore

FROZEN_CUSTODY_PREFIXES: tuple[str, ...] = (
    "code/ace_runtime/",
    "code/ace_mission/",
    "code/ace_autonomy/",
    "code/ace_host_controller/",
    "evidence/",
    "tools/",
)

FROZEN_EXACT_PATHS: frozenset[str] = frozenset({"docs/UPSTREAM_SOURCES.json"})

SEVERITY_RANK: dict[str, int] = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_protected_upstream_paths(repo_root: Path) -> set[str]:
    """Load protected file paths from ``docs/UPSTREAM_SOURCES.json`` if present."""
    manifest = repo_root / "docs" / "UPSTREAM_SOURCES.json"
    if not manifest.is_file():
        return set()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    files = data.get("files", {})
    if isinstance(files, dict):
        return {str(k) for k in files.keys()}
    return set()


def is_forbidden_path(rel_path: str, protected_files: set[str]) -> bool:
    """Return True if ``rel_path`` is frozen by custody or upstream pins."""
    norm = rel_path.replace("\\", "/").lstrip("./")
    if norm in FROZEN_EXACT_PATHS or norm in protected_files:
        return True
    return any(norm.startswith(prefix) for prefix in FROZEN_CUSTODY_PREFIXES)


def _max_nesting_depth(node: ast.AST, current_depth: int = 0) -> int:
    """Compute maximum block nesting depth inside a function AST node."""
    nesting_types = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)
    best = current_depth
    elif_nodes: set[int] = set()
    if isinstance(node, ast.If) and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
        elif_nodes.add(id(node.orelse[0]))
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        is_nested = isinstance(child, nesting_types) and id(child) not in elif_nodes
        next_depth = current_depth + 1 if is_nested else current_depth
        child_best = _max_nesting_depth(child, next_depth)
        if child_best > best:
            best = child_best
    return best


def _branch_count(node: ast.AST) -> int:
    """Count branching/control-flow constructs inside a function AST node."""
    branch_types = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With, ast.AsyncWith)
    count = 0
    for child in ast.walk(node):
        if child is not node and isinstance(child, branch_types):
            count += 1
    return count


def _is_test_filename(name: str) -> bool:
    return name.startswith("test_") or name.endswith("_test.py")


def _expected_companion_test_rel(rel_path: str) -> str | None:
    p = Path(rel_path)
    if len(p.parts) < 2 or p.parts[0] != "code" or _is_test_filename(p.name):
        return None
    return (p.parent / f"test_{p.name}").as_posix()


def _is_same_type_constant_equal(left: ast.AST, right: ast.AST) -> bool:
    return (
        isinstance(left, ast.Constant)
        and isinstance(right, ast.Constant)
        and type(left.value) is type(right.value)
        and left.value == right.value
    )


def _is_trivial_assert_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.Constant) and bool(test.value):
            return True
        if (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Constant)
            and not bool(test.operand.value)
        ):
            return True
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
            if isinstance(test.ops[0], (ast.Eq, ast.Is)):
                return _is_same_type_constant_equal(test.left, test.comparators[0])
        return False
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        if name == "assertTrue" and node.args:
            return isinstance(node.args[0], ast.Constant) and bool(node.args[0].value)
        if name == "assertFalse" and node.args:
            return isinstance(node.args[0], ast.Constant) and not bool(node.args[0].value)
        if name in {"assertEqual", "assertIs"} and len(node.args) >= 2:
            return _is_same_type_constant_equal(node.args[0], node.args[1])
    return False


def _find_trivial_test_assertions(tree: ast.AST) -> list[int]:
    """Identify tautological constant test assertions (e.g. ``assert True``, ``assertEqual(1, 1)``)."""
    hits = [int(getattr(node, "lineno", 1)) for node in ast.walk(tree) if _is_trivial_assert_node(node)]
    return sorted(set(hits))


def _count_unittest_methods(tree: ast.AST) -> int:
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    )


def _count_test_assertions(tree: ast.AST) -> int:
    """Count assert statements and ``assert*`` method/function calls in a test AST."""
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            total += 1
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr.startswith("assert"):
                total += 1
            elif isinstance(func, ast.Name) and func.id.startswith("assert"):
                total += 1
    return total


def _has_guard_return_or_raise(func_node: ast.AST) -> bool:
    """Check whether a function contains a failure guard (raise or literal False return)."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Return) and node.value is not None:
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and sub.value is False:
                    return True
    return False


def _find_unguarded_verified_true_lines(tree: ast.AST) -> list[int]:
    """Identify suspicious hardcoded ``'verified': True`` literals outside guarded checks.

    Catches lambdas, fallback ``else:`` defaults, or functions returning
    ``{"verified": True}`` without any failure guard (``raise`` / ``False``).
    """
    hits: list[int] = []

    def _visit(node: ast.AST, in_else: bool, enclosing_fn: ast.AST | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in node.body:
                _visit(stmt, False, node)
            return
        if isinstance(node, ast.Lambda):
            _visit(node.body, True, node)
            return
        if isinstance(node, ast.If):
            for s in node.body:
                _visit(s, False, enclosing_fn)
            for s in node.orelse:
                _visit(s, True, enclosing_fn)
            return
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (
                    isinstance(k, ast.Constant)
                    and k.value == "verified"
                    and isinstance(v, ast.Constant)
                    and v.value is True
                ):
                    if in_else or enclosing_fn is None or not _has_guard_return_or_raise(enclosing_fn):
                        hits.append(int(node.lineno))
        for child in ast.iter_child_nodes(node):
            _visit(child, in_else, enclosing_fn)

    _visit(tree, False, None)
    return sorted(set(hits))


def _find_silent_except_lines(tree: ast.AST) -> list[int]:
    """Identify bare ``except:`` or broad ``except Exception:`` handlers whose body is ``pass``."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}
        )
        if is_broad and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            hits.append(int(node.lineno))
    return sorted(hits)


@dataclass(frozen=True)
class AuditFinding:
    """Deterministic, evidence-backed code/capability improvement finding."""

    finding_key: str
    kind: str
    severity: str
    priority_score: int
    file_path: str
    symbol: str
    start_line: int
    end_line: int
    measured_metrics: dict[str, Any]
    summary: str
    recommended_action: str
    acceptance_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _infer_unittest_module(repo_root: Path, rel_path: str) -> str | None:
    """Map an editable module under ``code/`` to its sibling ``test_<name>.py`` module."""
    target = Path(rel_path)
    if len(target.parts) < 2 or target.parts[0] != "code":
        return None
    if _is_test_filename(target.name):
        candidate = repo_root / target
    else:
        primary = repo_root / target.parent / f"test_{target.name}"
        alt = repo_root / target.parent / f"{target.stem}_test.py"
        candidate = primary if primary.is_file() else alt
    if not candidate.is_file():
        return None
    rel_mod = candidate.relative_to(repo_root / "code").with_suffix("")
    return ".".join(rel_mod.parts)


def _record_py_dir_snapshot(
    *,
    repo_root: Path,
    root_dir: Path,
    hashes: dict[str, str],
    assert_counts: dict[str, int],
    trivial_counts: dict[str, int],
) -> None:
    if not root_dir.exists():
        return
    for py_file in sorted(root_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(repo_root).as_posix()
        hashes[rel] = _sha256_file(py_file)
        if _is_test_filename(py_file.name):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=rel)
                assert_counts[rel] = _count_test_assertions(tree)
                trivial_counts[rel] = len(_find_trivial_test_assertions(tree))
            except SyntaxError:
                assert_counts[rel] = 0
                trivial_counts[rel] = 0


def _snapshot_repo_state(
    repo_root: Path,
    scan_subpath: str = "code",
) -> tuple[dict[str, str], dict[str, int], dict[str, int]]:
    """Compute SHA-256 digests across protected + all editable ``code/`` files and test baselines."""
    hashes: dict[str, str] = {}
    assert_counts: dict[str, int] = {}
    trivial_counts: dict[str, int] = {}

    protected_exact = load_protected_upstream_paths(repo_root) | FROZEN_EXACT_PATHS
    for rel in sorted(protected_exact):
        full = repo_root / rel
        if full.is_file():
            hashes[rel] = _sha256_file(full)

    for prefix in FROZEN_CUSTODY_PREFIXES:
        pdir = repo_root / prefix.rstrip("/")
        if not pdir.exists():
            continue
        for fpath in sorted(pdir.rglob("*")):
            if "__pycache__" in fpath.parts or not fpath.is_file():
                continue
            rel = fpath.relative_to(repo_root).as_posix()
            hashes[rel] = _sha256_file(fpath)

    # Always snapshot ALL Python files under code/ regardless of scan_subpath to prevent blindspots.
    _record_py_dir_snapshot(
        repo_root=repo_root,
        root_dir=repo_root / "code",
        hashes=hashes,
        assert_counts=assert_counts,
        trivial_counts=trivial_counts,
    )
    norm_sub = scan_subpath.strip("/")
    if norm_sub and norm_sub != "code" and not norm_sub.startswith("code/"):
        _record_py_dir_snapshot(
            repo_root=repo_root,
            root_dir=repo_root / norm_sub,
            hashes=hashes,
            assert_counts=assert_counts,
            trivial_counts=trivial_counts,
        )
    return hashes, assert_counts, trivial_counts


class RealRepoAuditor:
    """Performs deterministic AST, test, and synthesis-telemetry audits on ACE."""

    def __init__(self, repo_root: str | Path, *, scan_subpath: str = "code") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.scan_subpath = scan_subpath.strip("/")
        self.protected_paths = load_protected_upstream_paths(self.repo_root)

    def _default_checks_for(self, rel_path: str) -> tuple[str, ...]:
        checks: list[str] = []
        mod = _infer_unittest_module(self.repo_root, rel_path)
        if mod:
            checks.append(f"PYTHONPATH=code {sys.executable} -m unittest {mod} -v")
        if (self.repo_root / "tools" / "verify_sources.py").is_file():
            checks.append(f"{sys.executable} tools/verify_sources.py")
        return tuple(checks)

    def _audit_non_test_ast(self, rel: str, tree: ast.AST, checks: tuple[str, ...]) -> list[AuditFinding]:
        out: list[AuditFinding] = []
        ver_lines = _find_unguarded_verified_true_lines(tree)
        if ver_lines:
            out.append(
                AuditFinding(
                    finding_key=f"unguarded_verified_true::{rel}::<module>",
                    kind="unguarded_verified_true",
                    severity="HIGH",
                    priority_score=850 + min(50, len(ver_lines) * 10),
                    file_path=rel,
                    symbol="<module>",
                    start_line=ver_lines[0],
                    end_line=ver_lines[-1],
                    measured_metrics={"unguarded_verified_true_count": len(ver_lines), "lines": ver_lines},
                    summary=f"Unguarded hardcoded `'verified': True` found at line(s) {ver_lines} in {rel}.",
                    recommended_action=(
                        f"Replace unguarded hardcoded `'verified': True` at line(s) {ver_lines} in {rel} "
                        "with empirical behavioral verification or fail-closed error handling."
                    ),
                    acceptance_checks=checks,
                )
            )

        silent_lines = _find_silent_except_lines(tree)
        if silent_lines:
            out.append(
                AuditFinding(
                    finding_key=f"silent_except_pass::{rel}::<module>",
                    kind="silent_except_pass",
                    severity="MEDIUM",
                    priority_score=700 + min(50, len(silent_lines) * 10),
                    file_path=rel,
                    symbol="<module>",
                    start_line=silent_lines[0],
                    end_line=silent_lines[-1],
                    measured_metrics={"silent_except_count": len(silent_lines), "lines": silent_lines},
                    summary=f"{len(silent_lines)} broad silent `except ...: pass` handler(s) in {rel}.",
                    recommended_action=(
                        f"Replace silent `except ...: pass` at line(s) {silent_lines} in {rel} "
                        "with explicit exception narrowing, structured logging, or error propagation."
                    ),
                    acceptance_checks=checks,
                )
            )
        out.extend(self._audit_function_complexity(rel, tree, checks))
        return out

    def _audit_test_ast(self, rel: str, tree: ast.AST, checks: tuple[str, ...]) -> list[AuditFinding]:
        trivial_lines = _find_trivial_test_assertions(tree)
        if not trivial_lines:
            return []
        return [
            AuditFinding(
                finding_key=f"trivial_test_assertion::{rel}::<module>",
                kind="trivial_test_assertion",
                severity="HIGH",
                priority_score=820 + min(50, len(trivial_lines) * 10),
                file_path=rel,
                symbol="<module>",
                start_line=trivial_lines[0],
                end_line=trivial_lines[-1],
                measured_metrics={"trivial_assertion_count": len(trivial_lines), "lines": trivial_lines},
                summary=f"{len(trivial_lines)} tautological constant assertion(s) at line(s) {trivial_lines} in {rel}.",
                recommended_action=(
                    f"Replace trivial constant assertion(s) at line(s) {trivial_lines} in {rel} "
                    "with real behavioral assertions exercising module outputs."
                ),
                acceptance_checks=checks,
            )
        ]

    def _audit_missing_unit_test(
        self,
        py_file: Path,
        rel: str,
        lines: list[str],
        tree: ast.AST,
        checks: tuple[str, ...],
    ) -> list[AuditFinding]:
        companion_rel = _expected_companion_test_rel(rel)
        if companion_rel is None or py_file.name in {"__init__.py", "__main__.py"} or len(lines) < 25:
            return []
        has_defs = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in tree.body
        )
        if not has_defs:
            return []
        if (py_file.parent / f"test_{py_file.name}").is_file():
            return []
        if (py_file.parent / f"{py_file.stem}_test.py").is_file():
            return []
        test_mod = ".".join(Path(companion_rel).relative_to("code").with_suffix("").parts)
        test_checks = [f"PYTHONPATH=code {sys.executable} -m unittest {test_mod} -v"]
        for cmd in checks:
            if cmd not in test_checks:
                test_checks.append(cmd)
        return [
            AuditFinding(
                finding_key=f"missing_unit_test::{rel}::<module>",
                kind="missing_unit_test",
                severity="LOW",
                priority_score=350,
                file_path=rel,
                symbol="<module>",
                start_line=1,
                end_line=len(lines),
                measured_metrics={"missing_unit_test": 1, "loc": len(lines)},
                summary=f"Module {rel} ({len(lines)} lines) lacks companion unit test {companion_rel}.",
                recommended_action=(
                    f"Create {companion_rel} with at least 2 non-trivial behavioral assertions "
                    f"covering functions/classes defined in {rel}."
                ),
                acceptance_checks=tuple(test_checks),
            )
        ]

    def _audit_function_complexity(self, rel: str, tree: ast.AST, checks: tuple[str, ...]) -> list[AuditFinding]:
        out: list[AuditFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end_ln = int(getattr(node, "end_lineno", node.lineno))
            loc = end_ln - node.lineno + 1
            branches = _branch_count(node)
            nesting = _max_nesting_depth(node)
            if loc > 120 or branches > 20 or nesting >= 5:
                score = 500 + min(250, loc // 2 + branches * 4 + nesting * 10)
                out.append(
                    AuditFinding(
                        finding_key=f"complex_function::{rel}::{node.name}",
                        kind="complex_function",
                        severity="MEDIUM",
                        priority_score=score,
                        file_path=rel,
                        symbol=node.name,
                        start_line=int(node.lineno),
                        end_line=end_ln,
                        measured_metrics={"loc": loc, "branches": branches, "max_nesting": nesting},
                        summary=f"Function `{node.name}` in {rel} has loc={loc}, branches={branches}, max_nesting={nesting}.",
                        recommended_action=(
                            f"Decompose `{node.name}` ({rel}:L{node.lineno}-L{end_ln}) into smaller, "
                            "cohesive single-responsibility helper functions while preserving behavior."
                        ),
                        acceptance_checks=checks,
                    )
                )
        return out

    def _audit_single_python_file(self, py_file: Path) -> list[AuditFinding]:
        py_file = Path(py_file).resolve()
        rel = py_file.relative_to(self.repo_root).as_posix()
        src = py_file.read_text(encoding="utf-8")
        lines = src.splitlines()
        out: list[AuditFinding] = []
        checks = self._default_checks_for(rel)
        try:
            tree = ast.parse(src, filename=rel)
        except SyntaxError as exc:
            out.append(
                AuditFinding(
                    finding_key=f"syntax_error::{rel}::<module>",
                    kind="syntax_error",
                    severity="CRITICAL",
                    priority_score=1000,
                    file_path=rel,
                    symbol="<module>",
                    start_line=int(exc.lineno or 1),
                    end_line=int(exc.lineno or 1),
                    measured_metrics={"syntax_errors": 1},
                    summary=f"SyntaxError in {rel}: {exc.msg}",
                    recommended_action=f"Fix Python syntax error near line {exc.lineno or 1} in {rel}.",
                    acceptance_checks=checks,
                )
            )
            return out

        if _is_test_filename(py_file.name):
            out.extend(self._audit_test_ast(rel, tree, checks))
        else:
            out.extend(self._audit_non_test_ast(rel, tree, checks))
            out.extend(self._audit_missing_unit_test(py_file, rel, lines, tree, checks))

        if ast.get_docstring(tree) is None and len(lines) > 10:
            out.append(
                AuditFinding(
                    finding_key=f"missing_module_docstring::{rel}::<module>",
                    kind="missing_module_docstring",
                    severity="LOW",
                    priority_score=200,
                    file_path=rel,
                    symbol="<module>",
                    start_line=1,
                    end_line=1,
                    measured_metrics={"missing_module_docstring": 1, "loc": len(lines)},
                    summary=f"Module {rel} ({len(lines)} lines) lacks a module docstring.",
                    recommended_action=f"Add a concise, accurate module docstring to {rel}.",
                    acceptance_checks=checks,
                )
            )
        return out

    def _audit_test_modules(self, test_modules: list[str]) -> list[AuditFinding]:
        out: list[AuditFinding] = []
        env = {**os.environ, "PYTHONPATH": str(self.repo_root / "code"), "PYTHONDONTWRITEBYTECODE": "1"}
        for mod in test_modules:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", mod, "-v"],
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                test_rel = f"code/{mod.replace('.', '/')}.py"
                test_p = Path(test_rel)
                target_rel = test_rel
                if test_p.name.startswith("test_"):
                    companion = test_p.parent / test_p.name[len("test_"):]
                    if (self.repo_root / companion).is_file():
                        target_rel = companion.as_posix()
                excerpt = (proc.stderr or proc.stdout or "").strip()[-1200:]
                out.append(
                    AuditFinding(
                        finding_key=f"test_failure::{target_rel}::{mod}",
                        kind="test_failure",
                        severity="CRITICAL",
                        priority_score=950,
                        file_path=target_rel,
                        symbol=mod,
                        start_line=1,
                        end_line=1,
                        measured_metrics={"test_exit_code": proc.returncode, "test_failures": 1},
                        summary=f"Unit test module `{mod}` failed (exit code {proc.returncode}).",
                        recommended_action=f"Diagnose and fix failure causing `{mod}` to fail.\nOutput:\n{excerpt}",
                        acceptance_checks=(f"PYTHONPATH=code {sys.executable} -m unittest {mod} -v",),
                    )
                )
        return out

    def _resolve_compositional_target(self) -> str | None:
        primary = self.repo_root / "code" / "ace_operational" / "compositional_oaie.py"
        if primary.is_file():
            return primary.relative_to(self.repo_root).as_posix()
        alt = self.repo_root / self.scan_subpath / "compositional_oaie.py"
        if alt.is_file():
            return alt.relative_to(self.repo_root).as_posix()
        return None

    def _audit_compositional_report(self, report_path: Path) -> list[AuditFinding]:
        if not report_path.is_file():
            return []
        try:
            doc = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        target_rel = self._resolve_compositional_target()
        if target_rel is None:
            return []
        out: list[AuditFinding] = []
        for gen in doc.get("generations", []):
            for task in gen.get("tasks", []):
                ev = task.get("ace_evolving", {})
                tid = str(task.get("task_id", "unknown"))
                cands = int(ev.get("candidates", 0))
                if not ev.get("verified", False):
                    out.append(
                        AuditFinding(
                            finding_key=f"oaie_unsolved_task::{target_rel}::{tid}",
                            kind="oaie_unsolved_task",
                            severity="HIGH",
                            priority_score=900,
                            file_path=target_rel,
                            symbol=tid,
                            start_line=1,
                            end_line=1,
                            measured_metrics={"solved": 0, "candidates": cands},
                            summary=f"Compositional OAIE task `{tid}` failed verification in `ace_evolving`.",
                            recommended_action=(
                                f"Investigate why `{tid}` failed in {target_rel} (status={ev.get('status')}) "
                                "and fix synthesis primitive coverage or verifier contract without overfitting."
                            ),
                            acceptance_checks=self._default_checks_for(target_rel),
                        )
                    )
                elif cands > 80_000:
                    out.append(
                        AuditFinding(
                            finding_key=f"oaie_high_search_cost::{target_rel}::{tid}",
                            kind="oaie_high_search_cost",
                            severity="MEDIUM",
                            priority_score=650,
                            file_path=target_rel,
                            symbol=tid,
                            start_line=1,
                            end_line=1,
                            measured_metrics={"candidates_generated": cands, "solved": 1},
                            summary=f"Compositional OAIE task `{tid}` required {cands} candidates (> 80,000).",
                            recommended_action=(
                                f"Add reusable intermediate skill/macro curriculum support or synthesis ordering "
                                f"to reduce search cost on `{tid}` below 80,000 candidates."
                            ),
                            acceptance_checks=self._default_checks_for(target_rel),
                        )
                    )
        return out

    def audit(
        self,
        *,
        test_modules: list[str] | None = None,
        compositional_report_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Run deterministic static, test, and telemetry audits across editable files."""
        scan_dir = self.repo_root / self.scan_subpath
        findings: list[AuditFinding] = []
        files_scanned = 0

        if test_modules:
            findings.extend(self._audit_test_modules(test_modules))

        if compositional_report_path is not None:
            findings.extend(self._audit_compositional_report(Path(compositional_report_path)))

        if scan_dir.exists():
            for py_file in sorted(scan_dir.rglob("*.py")):
                if "__pycache__" in py_file.parts:
                    continue
                rel = py_file.relative_to(self.repo_root).as_posix()
                if is_forbidden_path(rel, self.protected_paths):
                    continue
                files_scanned += 1
                findings.extend(self._audit_single_python_file(py_file))

        findings.sort(
            key=lambda f: (
                SEVERITY_RANK.get(f.severity, 9),
                -f.priority_score,
                f.file_path,
                f.start_line,
                f.finding_key,
            )
        )
        return {
            "schema": "ace.repo_audit.v1",
            "repo_root": str(self.repo_root),
            "scan_subpath": self.scan_subpath,
            "files_scanned": files_scanned,
            "findings_count": len(findings),
            "findings": [f.to_dict() for f in findings],
        }


def _render_work_order_markdown(order: dict[str, Any]) -> str:
    """Render a standalone AI-agnostic prompt document for any external AI/developer."""
    finding = order["finding"]
    checks_md = "\n".join(f"- `{cmd}`" for cmd in order["acceptance_checks"])
    forbidden_md = "\n".join(f"- `{p}`" for p in order["forbidden_paths"])
    target_md = "\n".join(f"- `{t}`" for t in order["target_files"])
    metrics_json = json.dumps(finding["measured_metrics"], indent=2, sort_keys=True)
    return (
        f"# ACE Evolution Work Order: `{order['order_id']}`\n\n"
        f"- **Generation**: `{order['generation_seq']}`\n"
        f"- **Finding Key**: `{finding['finding_key']}`\n"
        f"- **Kind / Severity**: `{finding['kind']}` (`{finding['severity']}`)\n"
        f"- **Order SHA-256**: `{order['order_sha256']}`\n\n"
        f"## 1. Objective\n{order['goal']}\n\n"
        f"### Observed Evidence (`{finding['file_path']}:L{finding['start_line']}-L{finding['end_line']}`)\n"
        f"{finding['summary']}\n\n"
        f"**Recommended Action:**\n{finding['recommended_action']}\n\n"
        f"### Measured Pre-Edit Metrics\n```json\n{metrics_json}\n```\n\n"
        f"## 2. Allowed Target File(s)\n{target_md}\n\n"
        f"## 3. Strictly Forbidden Custody & Upstream Paths\n"
        f"Do NOT modify any of the following paths (automatic fail-closed rejection):\n"
        f"{forbidden_md}\n\n"
        f"## 4. Anti-Theater & Quality Constraints (AST-Enforced)\n"
        f"- Do NOT hardcode `'verified': True` fallback/literal bypasses in non-test code.\n"
        f"- Do NOT introduce silent `except: pass` or `except Exception: pass` handlers.\n"
        f"- Do NOT delete assertions or insert trivial constant assertions (`assert True`, `assertEqual(1, 1)`).\n"
        f"- Any newly created unit test module must contain >= 2 non-trivial assertions and >= 1 `test_*` method.\n"
        f"- No-op or syntactically broken edits will fail closed and be quarantined.\n\n"
        f"## 5. Acceptance Verification Commands\n{checks_md}\n\n"
        f"Then ask ACE to verify & ratify your patch via:\n"
        f"```bash\n"
        f"PYTHONPATH=code python3 -m ace_operational.oaie_cli "
        f"--workspace \"{order['workspace']}\" evolve-verify --repo-root \"{order['repo_root']}\"\n"
        f"```\n"
    )


def _portable_path(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
        return rel or "."
    except ValueError:
        return str(path.resolve())


class PassiveEvolutionPlanner:
    """Selects real unresolved findings and emits AI-agnostic passive work orders."""

    def __init__(
        self,
        workspace: str | Path,
        repo_root: str | Path,
        *,
        scan_subpath: str = "code",
        memory_root: str | Path | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.repo_root = Path(repo_root).resolve()
        self.scan_subpath = scan_subpath.strip("/")
        # Cognitive-memory write-back (EVO 0009 milestone 5):
        # active only when a memory root is configured; None
        # keeps every existing caller byte-identical.
        self.memory_root = Path(memory_root) if memory_root else None
        self.auditor = RealRepoAuditor(self.repo_root, scan_subpath=self.scan_subpath)
        self.supervisor = SovereignRuntimeSupervisor(self.workspace / "runtime")
        self.state_path = self.workspace / "evolution_state.json"
        self.work_order_json_path = self.workspace / "EVOLUTION_WORK_ORDER.json"
        self.work_order_md_path = self.workspace / "EVOLUTION_WORK_ORDER.md"
        self.backlog_path = self.workspace / "EVOLUTION_BACKLOG.json"

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.is_file():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "schema": "ace.passive_evolution_state.v1",
            "generation_seq": 0,
            "ratified_count": 0,
            "rejected_count": 0,
            "completed_finding_keys": {},
            "ratified_history": [],
        }

    def _save_state(self, state: dict[str, Any]) -> None:
        atomic_write_verified(self.state_path, json.dumps(state, indent=2, sort_keys=True))

    def _derive_target_files(self, top: dict[str, Any]) -> list[str]:
        kind = top["kind"]
        f_rel = str(top["file_path"])
        if kind == "missing_unit_test":
            companion = _expected_companion_test_rel(f_rel)
            return [companion, f_rel] if companion else [f_rel]
        if kind in {"oaie_unsolved_task", "oaie_high_search_cost"}:
            targets = [f_rel]
            comp_synth = "code/ace_component_synthesis/component_synthesizer.py"
            if (self.repo_root / comp_synth).is_file() and comp_synth not in targets:
                targets.append(comp_synth)
            return targets
        return [f_rel]

    def _snapshot_before_ast_counts(self, target_files: list[str]) -> dict[str, dict[str, int]]:
        before_target_audit: dict[str, dict[str, int]] = {}
        for rel in target_files:
            p = self.repo_root / rel
            if not p.is_file():
                continue
            try:
                t = ast.parse(p.read_text(encoding="utf-8"), filename=rel)
                before_target_audit[rel] = {
                    "unguarded_verified_true_count": len(_find_unguarded_verified_true_lines(t)),
                    "silent_except_count": len(_find_silent_except_lines(t)),
                }
            except SyntaxError:
                before_target_audit[rel] = {
                    "unguarded_verified_true_count": 0,
                    "silent_except_count": 0,
                }
        return before_target_audit

    def _extract_comp_report_meta(
        self,
        compositional_report_path: str | Path | None,
    ) -> tuple[str | None, dict[str, Any]]:
        if compositional_report_path is None:
            return None, {}
        rp = Path(compositional_report_path)
        stored_path = _portable_path(rp, self.repo_root)
        budget: dict[str, Any] = {}
        if rp.is_file():
            try:
                doc = json.loads(rp.read_text(encoding="utf-8"))
                if isinstance(doc.get("budget"), dict):
                    budget = dict(doc["budget"])
            except (OSError, json.JSONDecodeError):
                budget = {}
        return stored_path, budget

    def plan_next_evolution(
        self,
        *,
        test_modules: list[str] | None = None,
        compositional_report_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Audit the repository, rank open findings, and emit the next Work Order."""
        state = self._load_state()
        audit = self.auditor.audit(
            test_modules=test_modules,
            compositional_report_path=compositional_report_path,
        )
        atomic_write_verified(self.backlog_path, json.dumps(audit, indent=2, sort_keys=True))

        comp_sha = ""
        if compositional_report_path is not None:
            crp = Path(compositional_report_path)
            if crp.is_file():
                comp_sha = _sha256_file(crp)
        completed = state.get("completed_finding_keys", {})
        open_findings: list[dict[str, Any]] = []
        sha_by_key: dict[str, str] = {}
        for f in audit["findings"]:
            if str(f.get("kind", "")).startswith("oaie_"):
                cur_sha = comp_sha
            else:
                target_file = self.repo_root / f["file_path"]
                cur_sha = _sha256_file(target_file) if target_file.is_file() else ""
            if completed.get(f["finding_key"]) == cur_sha and cur_sha:
                continue
            open_findings.append(f)
            sha_by_key[f["finding_key"]] = cur_sha

        # Memory write-back (write-path design S3-S4, EVO 0009
        # milestone 5): a HIGH backlog finding surfacing as
        # open is a verified event, written at the event point.
        # The evidence anchor is the finding's own state
        # (key + kind + file digest), so replaying the same
        # audit writes nothing new (record_verified_event is
        # idempotent on content + anchor); a changed file is a
        # changed finding state and anchors a new record.
        self._last_opened_record_ids: dict[str, str | None] = {}
        if self.memory_root is not None:
            for f in open_findings:
                if f.get("severity") != "HIGH":
                    continue
                anchor = _canonical_json({
                    "finding_key": f["finding_key"],
                    "kind": f.get("kind", ""),
                    "severity": f.get("severity", ""),
                    "file_path": f.get("file_path", ""),
                    "file_sha256": sha_by_key.get(f["finding_key"], ""),
                }).encode("utf-8")
                self._last_opened_record_ids[f["finding_key"]] = \
                    record_verified_event(
                        self.memory_root,
                        event="finding_high_opened",
                        summary=(f"HIGH finding opened: "
                                 f"{f['finding_key']} "
                                 f"({f.get('kind', '')}) in "
                                 f"{f.get('file_path', '')}"),
                        evidence_bytes=anchor,
                        content_extra={
                            "finding_key": f["finding_key"]},
                    )

        if not open_findings:
            return {
                "schema": "ace.passive_evolution_plan.v1",
                "status": "HOLD_NO_ACTIONABLE_FINDINGS",
                "files_scanned": audit["files_scanned"],
                "open_findings_count": 0,
                "backlog_path": str(self.backlog_path),
            }

        top = open_findings[0]
        next_seq = int(state["generation_seq"]) + 1
        state["generation_seq"] = next_seq
        self._save_state(state)

        key_digest8 = hashlib.sha256(top["finding_key"].encode("utf-8")).hexdigest()[:8]
        order_id = f"evo-{next_seq:04d}-{key_digest8}"
        target_files = self._derive_target_files(top)
        snapshot_hashes, snapshot_asserts, snapshot_trivial = _snapshot_repo_state(self.repo_root, self.scan_subpath)
        before_target_audit = self._snapshot_before_ast_counts(target_files)
        stored_comp_path, comp_budget = self._extract_comp_report_meta(compositional_report_path)

        forbidden_paths = sorted(list(FROZEN_CUSTODY_PREFIXES) + list(FROZEN_EXACT_PATHS))
        order_body: dict[str, Any] = {
            "schema": "ace.passive_work_order.v1",
            "order_id": order_id,
            "generation_seq": next_seq,
            "workspace": _portable_path(self.workspace, self.repo_root),
            "repo_root": _portable_path(self.repo_root, self.repo_root),
            "scan_subpath": self.scan_subpath,
            "goal": f"[{top['severity']}] {top['summary']}",
            "finding": top,
            "target_files": target_files,
            "before_hashes": {rel: snapshot_hashes.get(rel, "") for rel in target_files},
            "before_metrics": top["measured_metrics"],
            "before_target_ast_counts": before_target_audit,
            "forbidden_paths": forbidden_paths,
            "acceptance_checks": list(top["acceptance_checks"]),
            "compositional_report_path": stored_comp_path,
            "compositional_budget": comp_budget,
            "snapshot_file_hashes": snapshot_hashes,
            "snapshot_test_assert_counts": snapshot_asserts,
            "snapshot_test_trivial_counts": snapshot_trivial,
        }
        order_sha = _sha256_bytes(_canonical_json(order_body).encode("utf-8"))
        order = {**order_body, "order_sha256": order_sha}

        atomic_write_verified(self.work_order_json_path, json.dumps(order, indent=2, sort_keys=True))
        atomic_write_verified(self.work_order_md_path, _render_work_order_markdown(order))
        self.supervisor.work_bridge.export_work_order(
            order_id=order_id,
            goal=order["goal"],
            target_files=target_files,
            acceptance_checks=order["acceptance_checks"],
            forbidden_paths=forbidden_paths,
        )

        result_plan: dict[str, Any] = {
            "schema": "ace.passive_evolution_plan.v1",
            "status": "MISSION_EMITTED",
            "order_id": order_id,
            "order_sha256": order_sha,
            "generation_seq": next_seq,
            "files_scanned": audit["files_scanned"],
            "open_findings_count": len(open_findings),
            "top_finding": top,
            "work_order_json_path": str(self.work_order_json_path),
            "work_order_md_path": str(self.work_order_md_path),
            "backlog_path": str(self.backlog_path),
        }
        if self.memory_root is not None:
            result_plan["memory_writeback_opened"] = dict(
                self._last_opened_record_ids)
        return result_plan


class EvolutionPatchVerifier:
    """Fail-closed verifier and causal-lineage ratifier for external AI patches."""

    def __init__(self, workspace: str | Path, repo_root: str | Path,
                 *, memory_root: str | Path | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.work_order_json_path = self.workspace / "EVOLUTION_WORK_ORDER.json"
        self.state_path = self.workspace / "evolution_state.json"
        self.supervisor = SovereignRuntimeSupervisor(self.workspace / "runtime")
        self.spore_path = self.workspace / "evolution_spore.json"
        self.protected_paths = load_protected_upstream_paths(self.repo_root)
        # Cognitive-memory write-back (absorption PR #231 item
        # #8): active only when a memory root is configured;
        # None keeps every existing caller byte-identical.
        self.memory_root = Path(memory_root) if memory_root else None
        self._recalled_memory: list[dict[str, Any]] = []

    def _load_order(self) -> dict[str, Any]:
        if not self.work_order_json_path.is_file():
            raise FileNotFoundError(f"Missing work order at {self.work_order_json_path}")
        raw = json.loads(self.work_order_json_path.read_text(encoding="utf-8"))
        claimed = raw.get("order_sha256", "")
        body = {k: v for k, v in raw.items() if k != "order_sha256"}
        recomputed = _sha256_bytes(_canonical_json(body).encode("utf-8"))
        if claimed != recomputed:
            raise ValueError("Work order SHA-256 mismatch (tampered EVOLUTION_WORK_ORDER.json)")
        return raw

    def _detect_changes(self, order: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Compare post-edit file digests (and newly added files) against pre-edit snapshot."""
        snap = order.get("snapshot_file_hashes", {})
        scan_subpath = str(order.get("scan_subpath", "code"))
        current_hashes, _, _ = _snapshot_repo_state(self.repo_root, scan_subpath)
        all_paths = sorted(set(snap.keys()) | set(current_hashes.keys()))
        changed: list[str] = []
        touched_forbidden: list[str] = []
        for rel in all_paths:
            old_sha = snap.get(rel, "ABSENT")
            new_sha = current_hashes.get(rel, "MISSING")
            if new_sha != old_sha:
                changed.append(rel)
                if is_forbidden_path(rel, self.protected_paths):
                    touched_forbidden.append(rel)
        return changed, touched_forbidden

    def _check_test_ast_anti_cheat(
        self,
        *,
        rel: str,
        tree: ast.AST,
        before_asserts: dict[str, int],
        before_trivial: dict[str, int],
    ) -> list[str]:
        violations: list[str] = []
        new_trivial = _find_trivial_test_assertions(tree)
        old_trivial = int(before_trivial.get(rel, 0))
        if len(new_trivial) > old_trivial:
            violations.append(f"added_trivial_test_assertions:{rel}:{new_trivial}")
        new_asserts = _count_test_assertions(tree)
        if rel in before_asserts:
            old_asserts = int(before_asserts[rel])
            if new_asserts < old_asserts:
                violations.append(f"assertions_weakened:{rel}:{old_asserts}->{new_asserts}")
        else:
            if new_asserts < 2:
                violations.append(f"insufficient_new_test_assertions:{rel}:{new_asserts}")
            if _count_unittest_methods(tree) < 1:
                violations.append(f"missing_unittest_methods:{rel}")
        return violations

    def _check_ast_anti_cheat(self, order: dict[str, Any], changed_files: list[str]) -> list[str]:
        violations: list[str] = []
        before_target = order.get("before_target_ast_counts", {})
        before_asserts = order.get("snapshot_test_assert_counts", {})
        before_trivial = order.get("snapshot_test_trivial_counts", {})

        for rel in changed_files:
            fpath = self.repo_root / rel
            if not fpath.is_file() or not rel.endswith(".py"):
                continue
            try:
                tree = ast.parse(fpath.read_text(encoding="utf-8"), filename=rel)
            except SyntaxError as exc:
                violations.append(f"syntax_error:{rel}:{exc.lineno}")
                continue

            if _is_test_filename(fpath.name):
                violations.extend(
                    self._check_test_ast_anti_cheat(
                        rel=rel,
                        tree=tree,
                        before_asserts=before_asserts,
                        before_trivial=before_trivial,
                    )
                )
            else:
                new_ver = len(_find_unguarded_verified_true_lines(tree))
                old_ver = int(before_target.get(rel, {}).get("unguarded_verified_true_count", 0))
                if new_ver > old_ver:
                    violations.append(f"added_unguarded_verified_true:{rel}:{old_ver}->{new_ver}")
                new_sil = len(_find_silent_except_lines(tree))
                old_sil = int(before_target.get(rel, {}).get("silent_except_count", 0))
                if new_sil > old_sil:
                    violations.append(f"added_silent_except_pass:{rel}:{old_sil}->{new_sil}")
        return violations

    def _purge_stale_pyc(self, changed_files: list[str]) -> None:
        for rel in changed_files:
            p = self.repo_root / rel
            if p.suffix != ".py":
                continue
            cache_dir = p.parent / "__pycache__"
            if not cache_dir.is_dir():
                continue
            for pyc in cache_dir.glob(f"{p.stem}.*.pyc"):
                pyc.unlink(missing_ok=True)

    def _run_oaie_subprocess(self, budget: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        script = (
            "import contextlib, inspect, io, json, tempfile\n"
            "from ace_operational.compositional_oaie import CompositionalOAIERunner\n"
            "budget = json.loads(%r)\n"
            "sig = inspect.signature(CompositionalOAIERunner.__init__)\n"
            "kw = {k: v for k, v in budget.items() if k in sig.parameters}\n"
            "with tempfile.TemporaryDirectory(prefix='ace_oaie_recheck_') as d:\n"
            "    with contextlib.redirect_stdout(io.StringIO()):\n"
            "        runner = CompositionalOAIERunner(d, **kw)\n"
            "        rsig = inspect.signature(runner.run)\n"
            "        rkw = {'include_falsification': True} if 'include_falsification' in rsig.parameters else {}\n"
            "        rep = runner.run(**rkw)\n"
            "print(json.dumps(rep))\n"
        ) % (json.dumps(budget),)
        env = {**os.environ, "PYTHONPATH": str(self.repo_root / "code"), "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=str(self.repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return None, (proc.stderr or proc.stdout or "oaie_subprocess_failed").strip()[-400:]
        try:
            return json.loads(proc.stdout), ""
        except json.JSONDecodeError as exc:
            return None, f"oaie_invalid_json:{exc}"

    def _verify_oaie_finding_resolved(
        self,
        order: dict[str, Any],
        finding: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any], dict[str, Any] | None]:
        tid = str(finding["symbol"])
        kind = str(finding["kind"])
        budget = order.get("compositional_budget") or {}
        rep, err = self._run_oaie_subprocess(budget)
        if rep is None:
            return False, f"oaie_recheck_error:{err}", {}, None

        kernel_status = rep.get("experiment_kernel_audit", {}).get("status")
        if kernel_status is not None and kernel_status != "CLEAN":
            return False, f"oaie_kernel_unclean:{kernel_status}", {}, None
        forgetting = rep.get("spore_continuity_exam", {}).get("forgetting_count")
        if forgetting is not None and int(forgetting) != 0:
            return False, f"oaie_spore_forgetting:{forgetting}", {}, None
        falsification = rep.get("falsification")
        if isinstance(falsification, dict) and not falsification.get("all_falsification_probes_passed", True):
            return False, "oaie_falsification_failed", {}, None

        matched_ev: dict[str, Any] | None = None
        for gen in rep.get("generations", []):
            for task in gen.get("tasks", []):
                if str(task.get("task_id")) == tid:
                    matched_ev = task.get("ace_evolving", {})
                    break
        if matched_ev is None:
            return False, f"oaie_task_missing:{tid}", {}, None

        after_verified = bool(matched_ev.get("verified", False))
        after_cands = int(matched_ev.get("candidates", 0))
        metrics = {"solved": 1 if after_verified else 0, "candidates_generated": after_cands, "candidates": after_cands}
        if kind == "oaie_unsolved_task":
            if after_verified:
                return True, "finding_resolved", metrics, rep
            return False, f"finding_unresolved:{finding['finding_key']}", metrics, None
        if after_verified and after_cands <= 80_000:
            return True, "finding_resolved", metrics, rep
        return False, f"oaie_high_search_cost_unresolved:{tid}:verified={after_verified}:cands={after_cands}", metrics, None

    def _verify_missing_unit_test_resolved(
        self,
        target_path: Path,
        target_rel: str,
        changed_files: list[str],
        auditor: RealRepoAuditor,
    ) -> tuple[bool, str, dict[str, Any]]:
        companion = target_path.parent / f"test_{target_path.name}"
        alt = target_path.parent / f"{target_path.stem}_test.py"
        found_test = companion if companion.is_file() else (alt if alt.is_file() else None)
        if found_test is None:
            return False, f"missing_companion_test:{target_rel}", {}
        comp_rel = found_test.relative_to(self.repo_root).as_posix()
        if comp_rel not in changed_files:
            return False, f"companion_test_not_updated:{comp_rel}", {}
        try:
            t = ast.parse(found_test.read_text(encoding="utf-8"), filename=comp_rel)
        except SyntaxError as exc:
            return False, f"syntax_error:{comp_rel}:{exc.lineno}", {}
        if _find_trivial_test_assertions(t):
            return False, f"trivial_test_assertion:{comp_rel}", {}
        assert_cnt = _count_test_assertions(t)
        method_cnt = _count_unittest_methods(t)
        if assert_cnt < 2 or method_cnt < 1:
            return False, f"weak_companion_test:{comp_rel}:asserts={assert_cnt}:methods={method_cnt}", {}
        after_items = auditor._audit_single_python_file(target_path)
        if any(item.kind == "missing_unit_test" for item in after_items):
            return False, f"finding_unresolved:missing_unit_test::{target_rel}", {}
        return True, "finding_resolved", {"companion_test": comp_rel, "assertions": assert_cnt, "methods": method_cnt}

    def _eval_static_metric_progress(
        self,
        kind: str,
        before_m: dict[str, Any],
        after_m: dict[str, Any],
    ) -> bool:
        if kind == "unguarded_verified_true":
            return after_m["unguarded_verified_true_count"] < before_m["unguarded_verified_true_count"]
        if kind == "silent_except_pass":
            return after_m["silent_except_count"] < before_m["silent_except_count"]
        if kind == "trivial_test_assertion":
            return after_m["trivial_assertion_count"] < before_m["trivial_assertion_count"]
        if kind == "complex_function":
            return (
                after_m["loc"] < before_m["loc"]
                or after_m["branches"] < before_m["branches"]
                or after_m["max_nesting"] < before_m["max_nesting"]
            )
        if kind == "test_failure":
            return True
        return False

    def _check_finding_resolved(
        self,
        order: dict[str, Any],
        auditor: RealRepoAuditor,
        changed_files: list[str],
    ) -> tuple[bool, str, dict[str, Any], dict[str, Any] | None]:
        finding = order["finding"]
        fkey = finding["finding_key"]
        kind = finding["kind"]
        target_rel = finding["file_path"]
        target_path = self.repo_root / target_rel
        if not target_path.is_file():
            return False, f"target_missing:{target_rel}", {}, None

        if kind in {"oaie_unsolved_task", "oaie_high_search_cost"}:
            return self._verify_oaie_finding_resolved(order, finding)
        if kind == "missing_unit_test":
            ok, note, metrics = self._verify_missing_unit_test_resolved(target_path, target_rel, changed_files, auditor)
            return ok, note, metrics, None

        after_items = auditor._audit_single_python_file(target_path)
        matching = next((item for item in after_items if item.finding_key == fkey), None)
        if matching is None:
            return True, "finding_resolved", {"resolved": True}, None

        improved = self._eval_static_metric_progress(kind, finding["measured_metrics"], matching.measured_metrics)
        if improved:
            return True, "metric_strictly_improved", matching.measured_metrics, None
        return False, f"finding_unresolved:{fkey}", matching.measured_metrics, None

    def _run_acceptance_checks(
        self,
        order: dict[str, Any],
        extra_checks: list[str] | None,
        changed_files: list[str],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen_cmds: set[str] = set()
        all_cmds = list(order.get("acceptance_checks", [])) + list(extra_checks or [])
        for rel in changed_files:
            if not (rel.startswith("code/") and rel.endswith(".py") and (self.repo_root / rel).is_file()):
                continue
            mod = _infer_unittest_module(self.repo_root, rel)
            if mod:
                all_cmds.append(f"PYTHONPATH=code {sys.executable} -m unittest {mod} -v")
        if (self.repo_root / "tools" / "verify_sources.py").is_file():
            all_cmds.append(f"{sys.executable} tools/verify_sources.py")

        env = {**os.environ, "PYTHONPATH": str(self.repo_root / "code"), "PYTHONDONTWRITEBYTECODE": "1"}
        for cmd in all_cmds:
            if cmd in seen_cmds:
                continue
            seen_cmds.add(cmd)
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            results.append(
                {
                    "command": cmd,
                    "returncode": proc.returncode,
                    "passed": proc.returncode == 0,
                    "output_tail": (proc.stdout + "\n" + proc.stderr).strip()[-600:],
                }
            )
        return results

    def _quarantine_failure(self, order: dict[str, Any], reasons: list[str], extra: dict[str, Any]) -> dict[str, Any]:
        order_id = order["order_id"]
        attempt_tick = f"verify_fail_{order_id}_{self.supervisor.state['cycle_count'] + 1}"
        tick = self.supervisor.run_single_tick(
            {
                "task_id": attempt_tick,
                "expected_benefit": 1.0,
                "estimated_dt": 0.2,
                "remaining_budget_ratio": 1.0,
            },
            executor_fn=lambda _: {
                "verified": False,
                "failure_reason": "; ".join(reasons),
                "order_id": order_id,
            },
        )
        state = self._load_state_or_init()
        state["rejected_count"] = int(state.get("rejected_count", 0)) + 1
        atomic_write_verified(self.state_path, json.dumps(state, indent=2, sort_keys=True))
        if self.memory_root is not None and self._recalled_memory:
            # Close the memory loop on the reject exit too:
            # recalled procedural records take the failure.
            record_event_outcomes(self.memory_root, self._recalled_memory,
                                  context=order_id, success=False)
        return {
            "schema": "ace.passive_evolution_verify.v1",
            "order_id": order_id,
            "accepted": False,
            "status": "REJECTED_AND_QUARANTINED",
            "reasons": reasons,
            "dag_tick_status": tick["status"],
            "dag_chain_valid": self.supervisor.dag.verify_chain(),
            **extra,
        }

    def _load_state_or_init(self) -> dict[str, Any]:
        if self.state_path.is_file():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "schema": "ace.passive_evolution_state.v1",
            "generation_seq": 0,
            "ratified_count": 0,
            "rejected_count": 0,
            "completed_finding_keys": {},
            "ratified_history": [],
        }

    def _ratify_passing_evolution(
        self,
        *,
        order: dict[str, Any],
        changed_files: list[str],
        check_results: list[dict[str, Any]],
        resolution_note: str,
        after_metrics: dict[str, Any],
        refreshed_comp_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        order_id = order["order_id"]
        prev_proofs = self.supervisor.dag.nodes("proof_pheromone")
        parent_ids = (prev_proofs[-1].node_id,) if prev_proofs else ()
        post_hashes = {
            rel: _sha256_file(self.repo_root / rel)
            for rel in sorted(set(order.get("target_files", [])) | set(changed_files))
            if (self.repo_root / rel).is_file()
        }
        all_passed = bool(changed_files) and all(c["passed"] for c in check_results)
        tick = self.supervisor.run_single_tick(
            {
                "task_id": f"ratify_{order_id}",
                "expected_benefit": 2.0,
                "estimated_dt": 0.3,
                "remaining_budget_ratio": 1.0,
            },
            executor_fn=lambda _: {
                "verified": all_passed,
                "order_id": order_id,
                "finding_key": order["finding"]["finding_key"],
                "changed_files": changed_files,
                "post_hashes": post_hashes,
                "resolution_note": resolution_note,
                "after_metrics": after_metrics,
                "parent_ids": parent_ids,
            },
        )
        spore = SubstrateSpore.export_spore(
            spore_path=self.spore_path,
            dag=self.supervisor.dag,
            certified_skills=self.supervisor.state["certified_skills"],
            checkpoint_state=self.supervisor.state,
        )
        exam = SubstrateSpore.import_and_verify_spore(
            spore_path=self.spore_path,
            target_workspace=self.workspace / "continuity_probe",
            expected_ancestor_skills=["core_stage2_guard"],
            antibody_probes=[],
        )

        comp_raw = order.get("compositional_report_path")
        comp_abs: Path | None = None
        refreshed_written = False
        if comp_raw:
            rp = Path(comp_raw)
            comp_abs = rp if rp.is_absolute() else (self.repo_root / rp).resolve()
            if refreshed_comp_report is not None and comp_abs.is_relative_to(self.workspace):
                atomic_write_verified(comp_abs, json.dumps(refreshed_comp_report, indent=2, sort_keys=True))
                refreshed_written = True

        state = self._load_state_or_init()
        state["ratified_count"] = int(state.get("ratified_count", 0)) + 1
        completed = state.setdefault("completed_finding_keys", {})
        fkey = order["finding"]["finding_key"]
        fkind = order["finding"]["kind"]
        if resolution_note == "metric_strictly_improved":
            target_rel = order["finding"]["file_path"]
            completed[fkey] = post_hashes.get(target_rel, "")
        elif fkind.startswith("oaie_") and not refreshed_written and comp_abs is not None and comp_abs.is_file():
            completed[fkey] = _sha256_file(comp_abs)
        else:
            completed.pop(fkey, None)
        state.setdefault("ratified_history", []).append(
            {
                "order_id": order_id,
                "finding_key": order["finding"]["finding_key"],
                "resolution_note": resolution_note,
                "changed_files": changed_files,
                "spore_sha256": spore["spore_sha256"],
            }
        )
        atomic_write_verified(self.state_path, json.dumps(state, indent=2, sort_keys=True))
        accepted = all_passed and exam["forgetting_count"] == 0
        memory_record_id: str | None = None
        closed_record_id: str | None = None
        if self.memory_root is not None:
            # Memory write-back (design §3–§4): a ratification
            # is a verified event; the spore file is its
            # evidence. Outcomes close on the recalled records
            # either way; the episodic record is written only
            # when the ratification itself stands.
            record_event_outcomes(self.memory_root, self._recalled_memory,
                                  context=order_id, success=accepted)
            if accepted:
                memory_record_id = record_verified_event(
                    self.memory_root,
                    event="mission_ratified",
                    summary=(f"Mission {order_id} ratified: "
                             f"{resolution_note}; finding {fkey}; "
                             f"spore {spore['spore_sha256'][:16]}"),
                    evidence_bytes=self.spore_path.read_bytes(),
                )
                # Memory write-back (write-path design S3,
                # EVO 0009 milestone 5): ratifying the fix for
                # a HIGH finding closes that finding - the same
                # verified event point, the same spore evidence.
                if order["finding"].get("severity") == "HIGH":
                    closed_record_id = record_verified_event(
                        self.memory_root,
                        event="finding_high_closed",
                        summary=(f"HIGH finding closed: {fkey} "
                                 f"by ratified mission {order_id}; "
                                 f"spore "
                                 f"{spore['spore_sha256'][:16]}"),
                        evidence_bytes=self.spore_path.read_bytes(),
                        content_extra={"finding_key": fkey},
                    )
        result = {
            "schema": "ace.passive_evolution_verify.v1",
            "order_id": order_id,
            "accepted": accepted,
            "status": "VERIFIED_AND_RATIFIED",
            "resolution_note": resolution_note,
            "changed_files": changed_files,
            "check_results": check_results,
            "after_metrics": after_metrics,
            "dag_tick_status": tick["status"],
            "dag_chain_valid": self.supervisor.dag.verify_chain(),
            "parent_ids": list(parent_ids),
            "spore_sha256": spore["spore_sha256"],
            "forgetting_count": exam["forgetting_count"],
        }
        if self.memory_root is not None:
            result["memory_writeback"] = {
                "recalled": len(self._recalled_memory),
                "record_id": memory_record_id,
                "closed_record_id": closed_record_id,
            }
        return result

    def verify_and_ratify_evolution(self, *, extra_checks: list[str] | None = None) -> dict[str, Any]:
        """Execute fail-closed verification of edits and ratify into StigmergicDAG + Spore."""
        order = self._load_order()
        # Memory read side (design §5): before this cycle
        # decides, surface past verified outcomes on the same
        # finding context; the decision closes the loop with
        # record_event_outcomes at either exit.
        self._recalled_memory = []
        if self.memory_root is not None:
            finding = order.get("finding", {})
            self._recalled_memory = recall_context(
                self.memory_root,
                f"{finding.get('kind', '')} {finding.get('file_path', '')} "
                f"{finding.get('finding_key', '')}",
            )
        scan_subpath = order.get("scan_subpath", "code")
        auditor = RealRepoAuditor(self.repo_root, scan_subpath=scan_subpath)

        changed_files, touched_forbidden = self._detect_changes(order)
        reasons: list[str] = []
        if touched_forbidden:
            reasons.append(f"forbidden_paths_modified:{touched_forbidden}")
        if not changed_files:
            reasons.append("no_target_changes_detected")
        target_changed = [f for f in order.get("target_files", []) if f in changed_files]
        if changed_files and not target_changed:
            reasons.append("target_files_unchanged")
        ast_violations = self._check_ast_anti_cheat(order, changed_files)
        if ast_violations:
            reasons.append(f"ast_anti_cheat_violations:{ast_violations}")
        if reasons:
            return self._quarantine_failure(
                order,
                reasons,
                {"changed_files": changed_files, "touched_forbidden": touched_forbidden, "check_results": []},
            )

        self._purge_stale_pyc(changed_files)
        check_results = self._run_acceptance_checks(order, extra_checks, changed_files)
        failed_checks = [c["command"] for c in check_results if not c["passed"]]
        if failed_checks:
            reasons.append(f"acceptance_checks_failed:{failed_checks}")

        resolved_ok, resolution_note, after_metrics, refreshed_comp = self._check_finding_resolved(
            order, auditor, changed_files
        )
        if not resolved_ok:
            reasons.append(resolution_note)
        # Fail-closed evidence floor (gap_1654ad7ff3): a non-OAIE patch
        # must not be ratified on the static resolution re-audit alone.
        # _run_acceptance_checks legitimately returns [] when the order
        # declares no checks, no changed code/*.py has a sibling test
        # module, and tools/verify_sources.py is absent — and all([]) is
        # True, so _ratify_passing_evolution would accept with zero
        # executed checks. OAIE findings are exempt: their evidence is
        # the subprocess-measured metrics from _check_finding_resolved.
        if not check_results and not str(
            order.get("finding", {}).get("kind", "")
        ).startswith("oaie_"):
            reasons.append("no_acceptance_checks_executed")
        if reasons:
            return self._quarantine_failure(
                order,
                reasons,
                {
                    "changed_files": changed_files,
                    "touched_forbidden": [],
                    "check_results": check_results,
                    "after_metrics": after_metrics,
                },
            )
        return self._ratify_passing_evolution(
            order=order,
            changed_files=changed_files,
            check_results=check_results,
            resolution_note=resolution_note,
            after_metrics=after_metrics,
            refreshed_comp_report=refreshed_comp,
        )


def _render_user_mission_markdown(order: dict[str, Any]) -> str:
    """Render an AI-agnostic User Mission brief stored in `.ace_evolution/user_missions/`."""
    checks_md = "\n".join(f"- `{cmd}`" for cmd in order["acceptance_checks"]) or "- `(auto-inferred tests + tools/verify_sources.py)`"
    targets_md = "\n".join(f"- `{t}`" for t in order["target_files"])
    forbidden_md = "\n".join(f"- `{p}`" for p in order["forbidden_paths"])
    criteria_md = "\n".join(f"- {c}" for c in order.get("criteria", [])) or "- Implement real, verified behavior with companion unit tests."
    return (
        f"# ACE User Mission Work Order: `{order['order_id']}`\n\n"
        f"- **Mission Sequence**: `{order['mission_seq']}`\n"
        f"- **Title**: {order['title']}\n"
        f"- **Order SHA-256**: `{order['order_sha256']}`\n\n"
        f"## 1. Objective\n{order['goal']}\n\n"
        f"## 2. Success Criteria\n{criteria_md}\n\n"
        f"## 3. Target Files\n{targets_md}\n\n"
        f"## 4. Strictly Forbidden Custody & Upstream Paths\n{forbidden_md}\n\n"
        f"## 5. Acceptance Verification Commands\n{checks_md}\n\n"
        f"Then ratify cleanly without clobbering `EVOLUTION_WORK_ORDER.json` via:\n"
        f"```bash\n"
        f"PYTHONPATH=code python3 -m ace_operational.oaie_cli "
        f"--workspace \"{order['workspace']}\" mission-verify "
        f"--mission-id \"{order['order_id']}\" --repo-root \"{order['repo_root']}\"\n"
        f"```\n"
    )


class UserMissionCoordinator:
    """Manages human-directed ACE evolution missions alongside the static audit backlog."""

    _ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$")

    def __init__(
        self,
        workspace: str | Path,
        repo_root: str | Path,
        *,
        scan_subpath: str = "code",
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.repo_root = Path(repo_root).resolve()
        self.scan_subpath = scan_subpath.strip("/")
        self.missions_dir = self.workspace / "user_missions"
        self.missions_dir.mkdir(parents=True, exist_ok=True)
        self.current_json_path = self.missions_dir / "CURRENT_USER_MISSION.json"
        self.current_md_path = self.missions_dir / "CURRENT_USER_MISSION.md"
        self.state_path = self.workspace / "evolution_state.json"
        self.auditor = RealRepoAuditor(self.repo_root, scan_subpath=self.scan_subpath)
        self.protected_paths = load_protected_upstream_paths(self.repo_root)

    def _validate_mission_id(self, mission_id: str) -> str:
        clean = str(mission_id or "").strip()
        if not clean or ".." in clean or not self._ID_RE.fullmatch(clean):
            raise ValueError(f"Invalid mission_id: {mission_id!r}")
        return clean

    def _normalize_target_files(self, target_files: list[str]) -> list[str]:
        norm_targets: list[str] = []
        for raw in target_files:
            rel = str(raw).replace("\\", "/").lstrip("./").strip("/")
            if not rel or ".." in Path(rel).parts:
                raise ValueError(f"Invalid target_file path: {raw!r}")
            if is_forbidden_path(rel, self.protected_paths):
                raise ValueError(f"Forbidden protected target file: {rel}")
            if rel not in norm_targets:
                norm_targets.append(rel)
        if not norm_targets:
            raise ValueError("At least one editable target_file is required")
        return norm_targets

    def _snapshot_audit_details(self, files: list[str]) -> dict[str, dict[str, Any]]:
        details: dict[str, dict[str, Any]] = {}
        for rel in files:
            fpath = self.repo_root / rel
            if not fpath.is_file() or not rel.endswith(".py"):
                continue
            items = self.auditor._audit_single_python_file(fpath)
            details[rel] = {
                "counts_by_kind": self._count_findings_by_kind(items),
                "complex_symbols": {
                    it.symbol: dict(it.measured_metrics)
                    for it in items
                    if it.kind == "complex_function"
                },
            }
        return details

    @staticmethod
    def _count_findings_by_kind(items: list[AuditFinding]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
        return counts

    def _audit_modified_existing_file(
        self,
        *,
        rel: str,
        after_items: list[AuditFinding],
        before_detail: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        before_counts = before_detail.get("counts_by_kind", {})
        after_counts = self._count_findings_by_kind(after_items)
        for kind in ("syntax_error", "unguarded_verified_true", "silent_except_pass", "trivial_test_assertion", "missing_module_docstring"):
            if after_counts.get(kind, 0) > int(before_counts.get(kind, 0)):
                reasons.append(f"audit_regression:{rel}:{kind}:{before_counts.get(kind, 0)}->{after_counts.get(kind, 0)}")

        before_complex = before_detail.get("complex_symbols", {})
        for item in after_items:
            if item.kind != "complex_function":
                continue
            prev = before_complex.get(item.symbol)
            if prev is None:
                reasons.append(f"new_complex_function:{rel}:{item.symbol}")
                continue
            cur = item.measured_metrics
            if (
                int(cur["loc"]) > int(prev["loc"])
                or int(cur["branches"]) > int(prev["branches"])
                or int(cur["max_nesting"]) > int(prev["max_nesting"])
            ):
                reasons.append(f"worsened_complex_function:{rel}:{item.symbol}")
        return reasons

    def _audit_mission_changes(
        self,
        order: dict[str, Any],
        changed_files: list[str],
    ) -> list[str]:
        reasons: list[str] = []
        snap_hashes = order.get("snapshot_file_hashes", {})
        before_details = order.get("before_target_audit_details", {})
        for rel in changed_files:
            fpath = self.repo_root / rel
            if not fpath.is_file() or not rel.endswith(".py"):
                continue
            after_items = self.auditor._audit_single_python_file(fpath)
            if rel not in snap_hashes:
                if after_items:
                    kinds = [it.kind for it in after_items]
                    reasons.append(f"new_file_audit_findings:{rel}:{kinds}")
                continue
            reasons.extend(
                self._audit_modified_existing_file(
                    rel=rel,
                    after_items=after_items,
                    before_detail=before_details.get(rel, {}),
                )
            )
        return reasons

    def _load_order(self, mission_id: str | None) -> dict[str, Any]:
        if mission_id:
            clean = self._validate_mission_id(mission_id)
            path = self.missions_dir / f"{clean}.json"
        else:
            path = self.current_json_path
        if not path.is_file():
            raise FileNotFoundError(f"Missing user mission work order at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        claimed = raw.get("order_sha256", "")
        body = {k: v for k, v in raw.items() if k != "order_sha256"}
        recomputed = _sha256_bytes(_canonical_json(body).encode("utf-8"))
        if claimed != recomputed:
            raise ValueError(f"User mission SHA-256 mismatch (tampered {path.name})")
        return raw

    def plan_user_mission(
        self,
        *,
        mission_id: str,
        title: str,
        goal: str,
        target_files: list[str],
        acceptance_checks: list[str] | None = None,
        criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        """Snapshot repository baseline and emit a sealed User Mission without disturbing static backlog."""
        clean_id = self._validate_mission_id(mission_id)
        norm_targets = self._normalize_target_files(target_files)
        planner = PassiveEvolutionPlanner(self.workspace, self.repo_root, scan_subpath=self.scan_subpath)
        state = planner._load_state()
        next_seq = int(state.get("user_mission_seq", 0)) + 1
        state["user_mission_seq"] = next_seq
        planner._save_state(state)

        snap_hashes, snap_asserts, snap_trivial = _snapshot_repo_state(self.repo_root, self.scan_subpath)
        before_target_audit = planner._snapshot_before_ast_counts(norm_targets)
        existing_code_files = [rel for rel in snap_hashes if rel.endswith(".py") and not is_forbidden_path(rel, self.protected_paths)]
        before_audit_details = self._snapshot_audit_details(sorted(set(existing_code_files) | set(norm_targets)))

        order_body: dict[str, Any] = {
            "schema": "ace.user_mission_order.v1",
            "order_id": clean_id,
            "mission_seq": next_seq,
            "title": str(title).strip() or clean_id,
            "goal": str(goal).strip(),
            "criteria": [str(c) for c in (criteria or []) if str(c).strip()],
            "workspace": _portable_path(self.workspace, self.repo_root),
            "repo_root": _portable_path(self.repo_root, self.repo_root),
            "scan_subpath": self.scan_subpath,
            "target_files": norm_targets,
            "before_hashes": {rel: snap_hashes.get(rel, "") for rel in norm_targets},
            "before_target_ast_counts": before_target_audit,
            "before_target_audit_details": before_audit_details,
            "forbidden_paths": sorted(list(FROZEN_CUSTODY_PREFIXES) + list(FROZEN_EXACT_PATHS)),
            "acceptance_checks": [str(c) for c in (acceptance_checks or []) if str(c).strip()],
            "snapshot_file_hashes": snap_hashes,
            "snapshot_test_assert_counts": snap_asserts,
            "snapshot_test_trivial_counts": snap_trivial,
        }
        order_sha = _sha256_bytes(_canonical_json(order_body).encode("utf-8"))
        order = {**order_body, "order_sha256": order_sha}
        order_json = json.dumps(order, indent=2, sort_keys=True)
        order_md = _render_user_mission_markdown(order)

        mission_json_path = self.missions_dir / f"{clean_id}.json"
        mission_md_path = self.missions_dir / f"{clean_id}.md"
        atomic_write_verified(mission_json_path, order_json)
        atomic_write_verified(mission_md_path, order_md)
        atomic_write_verified(self.current_json_path, order_json)
        atomic_write_verified(self.current_md_path, order_md)

        return {
            "schema": "ace.user_mission_plan.v1",
            "status": "USER_MISSION_EMITTED",
            "order_id": clean_id,
            "mission_seq": next_seq,
            "order_sha256": order_sha,
            "target_files": norm_targets,
            "mission_json_path": str(mission_json_path),
            "mission_md_path": str(mission_md_path),
        }

    def _ratify_user_mission(
        self,
        *,
        verifier: EvolutionPatchVerifier,
        order: dict[str, Any],
        changed_files: list[str],
        check_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        order_id = order["order_id"]
        prev_proofs = verifier.supervisor.dag.nodes("proof_pheromone")
        parent_ids = (prev_proofs[-1].node_id,) if prev_proofs else ()
        post_hashes = {
            rel: _sha256_file(self.repo_root / rel)
            for rel in sorted(set(order.get("target_files", [])) | set(changed_files))
            if (self.repo_root / rel).is_file()
        }
        all_passed = bool(changed_files) and bool(check_results) and all(c["passed"] for c in check_results)
        tick = verifier.supervisor.run_single_tick(
            {
                "task_id": f"ratify_mission_{order_id}",
                "expected_benefit": 2.5,
                "estimated_dt": 0.4,
                "remaining_budget_ratio": 1.0,
            },
            executor_fn=lambda _: {
                "verified": all_passed,
                "order_id": order_id,
                "mission_type": "user_mission",
                "title": order["title"],
                "changed_files": changed_files,
                "post_hashes": post_hashes,
                "parent_ids": parent_ids,
            },
        )
        spore = SubstrateSpore.export_spore(
            spore_path=verifier.spore_path,
            dag=verifier.supervisor.dag,
            certified_skills=verifier.supervisor.state["certified_skills"],
            checkpoint_state=verifier.supervisor.state,
        )
        exam = SubstrateSpore.import_and_verify_spore(
            spore_path=verifier.spore_path,
            target_workspace=self.workspace / "continuity_probe",
            expected_ancestor_skills=["core_stage2_guard"],
            antibody_probes=[],
        )

        state = verifier._load_state_or_init()
        state["ratified_count"] = int(state.get("ratified_count", 0)) + 1
        entry = {
            "order_id": order_id,
            "mission_seq": order["mission_seq"],
            "title": order["title"],
            "changed_files": changed_files,
            "post_hashes": post_hashes,
            "spore_sha256": spore["spore_sha256"],
            "forgetting_count": exam["forgetting_count"],
        }
        state.setdefault("ratified_user_missions", []).append(entry)
        state.setdefault("ratified_history", []).append(
            {
                "order_id": order_id,
                "mission_type": "user_mission",
                "resolution_note": "user_mission_verified",
                "changed_files": changed_files,
                "spore_sha256": spore["spore_sha256"],
            }
        )
        atomic_write_verified(verifier.state_path, json.dumps(state, indent=2, sort_keys=True))
        receipt = {
            "schema": "ace.user_mission_verify.v1",
            "order_id": order_id,
            "accepted": all_passed and exam["forgetting_count"] == 0,
            "status": "VERIFIED_AND_RATIFIED",
            "changed_files": changed_files,
            "post_hashes": post_hashes,
            "check_results": check_results,
            "dag_tick_status": tick["status"],
            "dag_chain_valid": verifier.supervisor.dag.verify_chain(),
            "parent_ids": list(parent_ids),
            "spore_sha256": spore["spore_sha256"],
            "forgetting_count": exam["forgetting_count"],
        }
        atomic_write_verified(
            self.missions_dir / f"{order_id}.ratified.json",
            json.dumps(receipt, indent=2, sort_keys=True),
        )
        return receipt

    def verify_user_mission(
        self,
        *,
        mission_id: str | None = None,
        extra_checks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Verify a User Mission fail-closed and ratify into StigmergicDAG + SubstrateSpore."""
        order = self._load_order(mission_id)
        verifier = EvolutionPatchVerifier(self.workspace, self.repo_root)
        changed_files, touched_forbidden = verifier._detect_changes(order)
        reasons: list[str] = []
        if touched_forbidden:
            reasons.append(f"forbidden_paths_modified:{touched_forbidden}")
        if not changed_files:
            reasons.append("no_target_changes_detected")
        if changed_files and not any(f in changed_files for f in order.get("target_files", [])):
            reasons.append("target_files_unchanged")
        ast_violations = verifier._check_ast_anti_cheat(order, changed_files)
        if ast_violations:
            reasons.append(f"ast_anti_cheat_violations:{ast_violations}")
        audit_violations = self._audit_mission_changes(order, changed_files)
        if audit_violations:
            reasons.append(f"static_audit_regressions:{audit_violations}")
        if reasons:
            return verifier._quarantine_failure(
                order,
                reasons,
                {"changed_files": changed_files, "touched_forbidden": touched_forbidden, "check_results": []},
            )

        verifier._purge_stale_pyc(changed_files)
        check_results = verifier._run_acceptance_checks(order, extra_checks, changed_files)
        failed_checks = [c["command"] for c in check_results if not c["passed"]]
        if failed_checks:
            return verifier._quarantine_failure(
                order,
                [f"acceptance_checks_failed:{failed_checks}"],
                {"changed_files": changed_files, "touched_forbidden": [], "check_results": check_results},
            )
        return self._ratify_user_mission(
            verifier=verifier,
            order=order,
            changed_files=changed_files,
            check_results=check_results,
        )

