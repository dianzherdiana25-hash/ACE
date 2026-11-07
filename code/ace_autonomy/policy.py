"""ExecutionPolicy, GoalPolicy, BudgetCeiling, and safe O_NOFOLLOW/O_NONBLOCK file I/O.

Remediates Red Team findings:
- RT-03: Rejects ancestor symlinks and intra-tree symlinks via ``openat`` ``O_NOFOLLOW``.
- RT-08: Rejects FIFOs, sockets, and device files via ``O_NONBLOCK`` + ``stat.S_ISREG``.
- RT-11 / RT-13: Strict Python type checks (``type(x) is int``, ``type(x) is bool``) and
  canonical JSON serialization without ``NaN``/``Infinity``.
"""
from __future__ import annotations

from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from .errors import PolicyError

GOAL_SCHEMAS = frozenset({"ace.goal.v01", "ace.goal.v1"})

DEFAULT_MAX_STEPS = 8
DEFAULT_MAX_CANDIDATES = 4
DEFAULT_MAX_RETRIES_PER_STEP = 1
DEFAULT_WALL_SECONDS = 180.0
DEFAULT_CPU_SECONDS = 60.0
MAX_FILE_BYTES = 64 * 1024
MAX_CANDIDATE_BYTES = 128 * 1024

ALL_TOOLS = frozenset({
    "inspect_file",
    "verify_upstream_sources",
    "run_trusted_suite",
    "stage_candidate",
    "ace_status",
    "ace_demo",
    "ace_enqueue_task",
    "ace_run_tasks",
    "ace_predict",
    "ace_evaluate",
    "ace_report",
    "abstain",
    "external_action",
})

LEGACY_V01_TOOLS = frozenset({"inspect_file", "ace_status", "ace_demo"})

TRUSTED_TEST_SUITES = frozenset({
    "ace_runtime.test_engine",
    "ace_runtime.test_cli",
    "ace_research_primitives.test_primitives",
    "ace_candidate_search.test_search",
    "ace_capability_evolution.test_pilot",
    "ace_capability_evolution.test_compositional",
})

REVIEW_POLICIES = frozenset({
    "complete",
    "draft-only-no-merge",
    "stage-for-review",
})

GOAL_STATES = frozenset({
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "STAGED_FOR_REVIEW",
    "ABSTAINED",
    "FAILED",
    "BUDGET_EXHAUSTED",
    "HALT_UNCERTAIN",
    "CANCELLED",
})

TERMINAL_STATES = GOAL_STATES - {"QUEUED", "RUNNING"}

ALLOWED_TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({"QUEUED"}),
    "QUEUED": frozenset({
        "RUNNING",
        "SUCCEEDED",
        "STAGED_FOR_REVIEW",
        "ABSTAINED",
        "FAILED",
        "BUDGET_EXHAUSTED",
        "HALT_UNCERTAIN",
        "CANCELLED",
    }),
    "RUNNING": frozenset({
        "RUNNING",
        "SUCCEEDED",
        "STAGED_FOR_REVIEW",
        "ABSTAINED",
        "FAILED",
        "BUDGET_EXHAUSTED",
        "HALT_UNCERTAIN",
        "CANCELLED",
    }),
    "HALT_UNCERTAIN": frozenset({"RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}),
    "SUCCEEDED": frozenset(),
    "STAGED_FOR_REVIEW": frozenset(),
    "ABSTAINED": frozenset(),
    "FAILED": frozenset(),
    "BUDGET_EXHAUSTED": frozenset(),
    "CANCELLED": frozenset(),
}


def is_strict_int(val: Any) -> bool:
    return type(val) is int


def is_strict_bool(val: Any) -> bool:
    return type(val) is bool


def is_strict_num(val: Any) -> bool:
    return type(val) in (int, float) and val == val and val not in (float("inf"), float("-inf"))


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BudgetCeiling:
    max_steps: int = DEFAULT_MAX_STEPS
    max_candidates: int = DEFAULT_MAX_CANDIDATES
    max_retries_per_step: int = DEFAULT_MAX_RETRIES_PER_STEP
    wall_seconds: float = DEFAULT_WALL_SECONDS
    cpu_seconds: float = DEFAULT_CPU_SECONDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_steps": self.max_steps,
            "max_candidates": self.max_candidates,
            "max_retries_per_step": self.max_retries_per_step,
            "wall_seconds": float(self.wall_seconds),
            "cpu_seconds": float(self.cpu_seconds),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> BudgetCeiling:
        if raw is None:
            return cls()
        if type(raw) is not dict:
            raise PolicyError("budget must be a mapping")
        allowed = {"max_steps", "max_candidates", "max_retries_per_step", "wall_seconds", "cpu_seconds"}
        if not set(raw).issubset(allowed):
            raise PolicyError("unknown budget field")
        max_steps = raw.get("max_steps", DEFAULT_MAX_STEPS)
        max_candidates = raw.get("max_candidates", DEFAULT_MAX_CANDIDATES)
        max_retries = raw.get("max_retries_per_step", DEFAULT_MAX_RETRIES_PER_STEP)
        wall_sec = raw.get("wall_seconds", DEFAULT_WALL_SECONDS)
        cpu_sec = raw.get("cpu_seconds", DEFAULT_CPU_SECONDS)
        if not is_strict_int(max_steps) or not 1 <= max_steps <= DEFAULT_MAX_STEPS:
            raise PolicyError("max_steps must be an int in 1..8")
        if not is_strict_int(max_candidates) or not 0 <= max_candidates <= DEFAULT_MAX_CANDIDATES:
            raise PolicyError("max_candidates must be an int in 0..4")
        if not is_strict_int(max_retries) or not 0 <= max_retries <= 2:
            raise PolicyError("max_retries_per_step must be an int in 0..2")
        if not is_strict_num(wall_sec) or not 0.001 <= float(wall_sec) <= DEFAULT_WALL_SECONDS:
            raise PolicyError("wall_seconds must be in (0, 180]")
        if not is_strict_num(cpu_sec) or not 0.001 <= float(cpu_sec) <= DEFAULT_CPU_SECONDS:
            raise PolicyError("cpu_seconds must be in (0, 60]")
        return cls(
            max_steps=max_steps,
            max_candidates=max_candidates,
            max_retries_per_step=max_retries,
            wall_seconds=float(wall_sec),
            cpu_seconds=float(cpu_sec),
        )


@dataclass(frozen=True)
class GoalPolicy:
    authorized_tools: tuple[str, ...]
    read_prefixes: tuple[str, ...]
    write_prefixes: tuple[str, ...]
    review_policy: str = "draft-only-no-merge"
    stop_on_uncertain_external_action: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorized_tools": list(self.authorized_tools),
            "read_prefixes": list(self.read_prefixes),
            "write_prefixes": list(self.write_prefixes),
            "review_policy": self.review_policy,
            "stop_on_uncertain_external_action": self.stop_on_uncertain_external_action,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None, *, schema: str) -> GoalPolicy:
        if schema == "ace.goal.v01":
            if raw is not None:
                raise PolicyError("ace.goal.v01 does not accept custom policy object")
            return cls(
                authorized_tools=tuple(sorted(LEGACY_V01_TOOLS)),
                read_prefixes=("",),
                write_prefixes=("candidates/",),
                review_policy="complete",
                stop_on_uncertain_external_action=True,
            )
        if raw is None:
            return cls(
                authorized_tools=tuple(sorted(ALL_TOOLS - {"external_action"})),
                read_prefixes=("",),
                write_prefixes=("candidates/",),
                review_policy="draft-only-no-merge",
                stop_on_uncertain_external_action=True,
            )
        if type(raw) is not dict:
            raise PolicyError("policy must be a mapping")
        allowed_keys = {
            "authorized_tools",
            "read_prefixes",
            "write_prefixes",
            "review_policy",
            "stop_on_uncertain_external_action",
        }
        if not set(raw).issubset(allowed_keys):
            raise PolicyError("unknown policy field")
        tools = raw.get("authorized_tools", sorted(ALL_TOOLS - {"external_action"}))
        if type(tools) is not list or not tools or any(type(t) is not str or t not in ALL_TOOLS for t in tools):
            raise PolicyError("invalid authorized_tools in policy")
        read_p = raw.get("read_prefixes", [""])
        if type(read_p) is not list or any(type(p) is not str for p in read_p):
            raise PolicyError("invalid read_prefixes in policy")
        for p in read_p:
            if p:
                validate_SafeRelPath(p, allow_empty=False)
        write_p = raw.get("write_prefixes", ["candidates/"])
        if type(write_p) is not list or any(type(p) is not str for p in write_p):
            raise PolicyError("invalid write_prefixes in policy")
        for p in write_p:
            if not p.startswith("candidates"):
                raise PolicyError("write_prefixes must remain confined to staging 'candidates/'")
        review_policy = raw.get("review_policy", "draft-only-no-merge")
        if type(review_policy) is not str or review_policy not in REVIEW_POLICIES:
            raise PolicyError("invalid review_policy")
        stop_unc = raw.get("stop_on_uncertain_external_action", True)
        if not is_strict_bool(stop_unc) or stop_unc is not True:
            raise PolicyError("stop_on_uncertain_external_action must be True")
        return cls(
            authorized_tools=tuple(sorted(set(tools))),
            read_prefixes=tuple(read_p),
            write_prefixes=tuple(write_p),
            review_policy=review_policy,
            stop_on_uncertain_external_action=True,
        )


def validate_SafeRelPath(rel_path: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if type(rel_path) is not str:
        raise PolicyError("path must be a string")
    if not rel_path:
        if allow_empty:
            return ()
        raise PolicyError("path must be non-empty")
    if "\x00" in rel_path or rel_path.startswith("/") or rel_path.startswith("\\") or "\\" in rel_path:
        raise PolicyError("absolute, backslash, or NUL path forbidden")
    parts = [p for p in rel_path.split("/") if p != ""]
    if not parts or any(p in (".", "..") for p in parts):
        raise PolicyError("traversal or degenerate path forbidden")
    return tuple(parts)


def path_matches_prefixes(rel_path: str, prefixes: tuple[str, ...]) -> bool:
    norm = "/".join(validate_SafeRelPath(rel_path))
    for pref in prefixes:
        if pref == "":
            return True
        clean = "/".join(validate_SafeRelPath(pref))
        if norm == clean or norm.startswith(clean + "/"):
            return True
    return False


def verify_no_ancestor_symlinks(target_path: Path) -> Path:
    """Verify every existing path component from '/' down to ``target_path`` is non-symlink."""
    raw = Path(os.path.abspath(os.fspath(target_path)))
    cur = Path("/")
    for part in raw.parts[1:]:
        cur = cur / part
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(st.st_mode):
            raise PolicyError(f"symlink component forbidden in path: {cur}")
    return raw


def safe_read_regular_file(base_dir: Path, rel_path: str, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    """Walk ``rel_path`` relative to ``base_dir`` via ``openat`` with ``O_NOFOLLOW | O_NONBLOCK``."""
    parts = validate_SafeRelPath(rel_path)
    verify_no_ancestor_symlinks(base_dir)
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)

    try:
        cur_fd = os.open(os.fspath(base_dir), dir_flags)
    except OSError as exc:
        raise PolicyError(f"cannot open base directory safely: {exc}") from exc

    try:
        for comp in parts[:-1]:
            try:
                next_fd = os.open(comp, dir_flags, dir_fd=cur_fd)
            except OSError as exc:
                raise PolicyError(f"unauthorized or symlinked directory '{comp}': {exc}") from exc
            os.close(cur_fd)
            cur_fd = next_fd

        leaf = parts[-1]
        try:
            file_fd = os.open(leaf, file_flags, dir_fd=cur_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise PolicyError(f"symlink forbidden: {rel_path}") from exc
            raise PolicyError(f"cannot open file '{rel_path}': {exc}") from exc

        try:
            st = os.fstat(file_fd)
            if not stat.S_ISREG(st.st_mode):
                raise PolicyError(f"non-regular file forbidden (FIFO/device/socket/dir): {rel_path}")
            if st.st_size > max_bytes:
                raise PolicyError("file size budget exceeded")
            chunks: list[bytes] = []
            total = 0
            while True:
                buf = os.read(file_fd, min(65536, max_bytes - total + 1))
                if not buf:
                    break
                total += len(buf)
                if total > max_bytes:
                    raise PolicyError("file size budget exceeded")
                chunks.append(buf)
            return b"".join(chunks)
        finally:
            os.close(file_fd)
    finally:
        os.close(cur_fd)


def safe_write_staged_file(staging_root: Path, rel_path: str, content_bytes: bytes) -> Path:
    """Safely write a non-executable staged candidate file inside ``staging_root``."""
    if len(content_bytes) > MAX_CANDIDATE_BYTES:
        raise PolicyError("candidate size budget exceeded")
    parts = validate_SafeRelPath(rel_path)
    verify_no_ancestor_symlinks(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)

    cur = staging_root
    for comp in parts[:-1]:
        cur = cur / comp
        if cur.exists() and os.path.islink(cur):
            raise PolicyError(f"symlink in staging directory forbidden: {cur}")
        cur.mkdir(exist_ok=True)
        if os.path.islink(cur):
            raise PolicyError(f"symlink race in staging directory: {cur}")

    target = cur / parts[-1]
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(os.fspath(target), flags, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise PolicyError("staging target is not a regular file")
        os.write(fd, content_bytes)
        os.fsync(fd)
    finally:
        os.close(fd)
    return target


def validate_step(item: Any, *, policy: GoalPolicy) -> None:
    if type(item) is not dict or type(item.get("tool")) is not str:
        raise PolicyError("unauthorized tool")
    tool = item["tool"]
    if tool not in ALL_TOOLS or tool not in policy.authorized_tools:
        raise PolicyError("unauthorized tool")

    if tool == "inspect_file":
        if set(item) != {"tool", "path"} or type(item["path"]) is not str or not item["path"]:
            raise PolicyError("inspect_file requires a relative path")
        validate_SafeRelPath(item["path"])
        if not path_matches_prefixes(item["path"], policy.read_prefixes):
            raise PolicyError("path outside policy read_prefixes")
    elif tool in {"ace_status", "ace_demo", "verify_upstream_sources"}:
        if set(item) != {"tool"}:
            raise PolicyError("unknown tool parameters")
    elif tool == "run_trusted_suite":
        if set(item) != {"tool", "suite"} or type(item["suite"]) is not str:
            raise PolicyError("run_trusted_suite requires 'suite'")
        if item["suite"] not in TRUSTED_TEST_SUITES:
            raise PolicyError(f"suite '{item['suite']}' is not in trusted test allowlist")
    elif tool == "stage_candidate":
        if set(item) != {"tool", "rel_path", "content", "kind"}:
            raise PolicyError("stage_candidate requires rel_path, content, and kind")
        if type(item["content"]) is not str or type(item["kind"]) is not str or not item["kind"]:
            raise PolicyError("stage_candidate content and kind must be strings")
        validate_SafeRelPath(item["rel_path"])
        full_rel = f"candidates/{'/'.join(validate_SafeRelPath(item['rel_path']))}"
        if not path_matches_prefixes(full_rel, policy.write_prefixes):
            raise PolicyError("candidate path outside policy write_prefixes")
        if len(item["content"].encode("utf-8")) > MAX_CANDIDATE_BYTES:
            raise PolicyError("candidate size budget exceeded")
    elif tool == "ace_enqueue_task":
        if set(item) != {"tool", "task"} or type(item["task"]) is not dict:
            raise PolicyError("ace_enqueue_task requires a task mapping")
    elif tool == "ace_run_tasks":
        allowed = {"tool", "max_tasks"}
        if not set(item).issubset(allowed):
            raise PolicyError("unknown ace_run_tasks parameters")
        if "max_tasks" in item and (not is_strict_int(item["max_tasks"]) or not 1 <= item["max_tasks"] <= 16):
            raise PolicyError("max_tasks must be an int in 1..16")
    elif tool == "ace_predict":
        if set(item) != {"tool", "task_id", "inputs"} or type(item["task_id"]) is not str or type(item["inputs"]) is not list:
            raise PolicyError("ace_predict requires task_id and inputs list")
        if not item["inputs"] or len(item["inputs"]) > 256 or any(type(x) is not str for x in item["inputs"]):
            raise PolicyError("invalid ace_predict inputs")
    elif tool == "ace_evaluate":
        if set(item) != {"tool", "task_id", "examples"} or type(item["task_id"]) is not str or type(item["examples"]) is not list:
            raise PolicyError("ace_evaluate requires task_id and examples list")
        if not item["examples"] or len(item["examples"]) > 512:
            raise PolicyError("invalid ace_evaluate examples")
    elif tool == "ace_report":
        if set(item) != {"tool", "task_id"} or type(item["task_id"]) is not str or not item["task_id"]:
            raise PolicyError("ace_report requires task_id")
    elif tool == "abstain":
        if set(item) != {"tool", "reason"} or type(item["reason"]) is not str or not 1 <= len(item["reason"]) <= 240:
            raise PolicyError("abstain requires a concise reason string")
    elif tool == "external_action":
        if set(item) != {"tool", "operation", "payload"} or type(item["operation"]) is not str or type(item["payload"]) is not dict:
            raise PolicyError("external_action requires operation and payload")
    else:
        raise PolicyError("unauthorized tool")


def validate_goal(goal: Any) -> str:
    """Validate ``ace.goal.v01`` or ``ace.goal.v1`` goal and return its SHA-256 ID."""
    if type(goal) is not dict:
        raise PolicyError("goal must be a dict")
    schema = goal.get("schema")
    if schema == "ace.goal.v01":
        if set(goal) != {"schema", "name", "steps"}:
            raise PolicyError("goal must have schema, name and steps only")
    elif schema == "ace.goal.v1":
        allowed = {"schema", "name", "steps", "objective", "policy", "budget"}
        if not set(goal).issubset(allowed) or "name" not in goal:
            raise PolicyError("invalid ace.goal.v1 keys")
        if ("steps" in goal) == ("objective" in goal):
            raise PolicyError("ace.goal.v1 requires exactly one of 'steps' or 'objective'")
    else:
        raise PolicyError("invalid goal schema or name")

    if type(goal.get("name")) is not str or not 1 <= len(goal["name"]) <= 80:
        raise PolicyError("invalid goal schema or name")

    budget = BudgetCeiling.from_dict(goal.get("budget"))
    policy = GoalPolicy.from_dict(goal.get("policy"), schema=schema)

    if "objective" in goal:
        from .planner import plan_objective

        steps = plan_objective(goal["objective"], policy=policy, budget=budget)
    else:
        steps = goal["steps"]

    if type(steps) is not list or not 1 <= len(steps) <= budget.max_steps:
        raise PolicyError("invalid step budget")

    staged_count = 0
    for item in steps:
        validate_step(item, policy=policy)
        if item["tool"] == "stage_candidate":
            staged_count += 1
    if staged_count > budget.max_candidates:
        raise PolicyError("goal exceeds max_candidates budget")

    return digest(goal)
