"""Run the fixed development solver with an isolated, bounded JSON transport."""

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

from .contract import (
    ContractError, array, canonical_json, integer, parse_fit_request, read_json,
    require_fields,
)
from .dsl import Program, compile_ast
from .extension import POLICIES, definition_from_program, parse_definition


class WorkerError(RuntimeError):
    """The isolated fit did not return a valid result."""


@dataclass(frozen=True)
class WorkerMetrics:
    cpu_us: int
    wall_us: int
    rss_kib: int


@dataclass(frozen=True)
class IsolatedFit:
    program: Program
    candidates: int
    steps: int
    metrics: WorkerMetrics
    status: str = "fit"
    trace: dict | None = None


_SOLVER_FILES = ("__init__.py", "baseline.py", "beam.py", "blind.py", "contract.py",
                 "dsl.py", "extension.py", "worker.py")
_WALL_SECONDS = 3
_MEMORY_BYTES = 128 * 1024 * 1024


def _sandbox_python(args, raw=b"", *, solver=None):
    python = str(Path("/usr/bin/python3").resolve())
    # The outer process creates a fresh network namespace with no configured
    # interfaces. Bubblewrap retains that namespace without setting up loopback.
    command = [
        "/usr/bin/prlimit", "--cpu=1:1", f"--as={_MEMORY_BYTES}:{_MEMORY_BYTES}", "--",
        "/usr/bin/unshare", "--user", "--map-root-user", "--net", "--",
        "/usr/bin/bwrap", "--unshare-all", "--share-net", "--unshare-user",
        "--disable-userns", "--clearenv", "--die-with-parent", "--new-session",
        "--ro-bind", "/usr/lib", "/usr/lib", "--ro-bind-try", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64", "--ro-bind", python, python,
        "--tmpfs", "/tmp", "--chdir", "/tmp",
    ]
    if solver is not None:
        command.extend(("--ro-bind", str(solver), "/solver"))
    started = perf_counter_ns()
    try:
        result = subprocess.run(
            [*command, python, "-I", "-B", "-S", *args],
            input=raw, capture_output=True, timeout=_WALL_SECONDS, check=False,
            env={"LANG": "C"}, close_fds=True,
        )
    except subprocess.TimeoutExpired as error:
        raise WorkerError("fit worker exceeded the wall limit") from error
    except OSError as error:
        raise WorkerError("isolated fit runtime unavailable") from error
    if result.returncode != 0:
        raise WorkerError(f"isolated fit worker failed (exit {result.returncode})")
    return result.stdout, (perf_counter_ns() - started) // 1_000


def _stage_solver(root):
    package = root / "e13"
    package.mkdir()
    for name in _SOLVER_FILES:
        shutil.copyfile(Path(__file__).with_name(name), package / name)


def _proposals(value, maximum_score):
    digests, scores = [], []
    for item in array(value, 0, 106):
        digest, score = array(item, 2, 2)
        if type(digest) is not str or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ContractError("invalid proposal digest")
        digests.append(digest)
        scores.append(integer(score, 0, maximum_score))
    if len(set(digests)) != len(digests):
        raise ContractError("duplicate proposal digest")
    return digests, scores


def _validate_trace(trace, request, policy, program, candidates, steps, inherited):
    require_fields(trace, "source", "target", "source_selected", "source_definition",
                   "source_steps", "source_exhausted", "sham_shift", "sham_unchanged",
                   "parent", "target_definition", "target_steps")
    source, scores = _proposals(trace["source"], len(request.source))
    target, target_scores = _proposals(trace["target"], len(request.target))
    source_steps = integer(trace["source_steps"], 0, request.fuel // 2)
    target_steps = integer(trace["target_steps"], 1, request.fuel - request.fuel // 2)
    if (source_steps + target_steps != steps or candidates != max(1, len(source) + len(target))
            or len(source) > source_steps or len(target) > target_steps):
        raise ContractError("inconsistent fit accounting")
    if type(trace["source_exhausted"]) is not bool or type(trace["sham_unchanged"]) is not bool:
        raise ContractError("invalid trace flag")
    sham = policy == "c_sham" and len(source) > 1
    shift = integer(trace["sham_shift"], int(sham), len(source) - 1 if sham else 0)
    shifted = scores[shift:] + scores[:shift]
    expected = source[shifted.index(max(shifted))] if source else None
    if trace["source_selected"] != expected or trace["sham_unchanged"] != (scores == shifted):
        raise ContractError("inconsistent source selection")
    raw_definition = trace["source_definition"]
    selected = None if raw_definition is None else parse_definition(raw_definition)
    if ((selected is None) != (expected is None)
            or (selected and (selected.family != request.family or selected.sha256 != expected
                              or (policy == "c_no_extend" and len(selected.table) > 4)))):
        raise ContractError("invalid source definition")
    parent = expected if policy in ("c_extend", "c_no_extend", "c_sham") else inherited
    if (trace["parent"] != parent or (parent is not None and target and target[0] != parent)
            or (policy == "replay" and (source or source_steps or trace["source_exhausted"]))):
        raise ContractError("invalid inheritance trace")
    target_definition = definition_from_program(program).sha256
    if (trace["target_definition"] != target_definition
            or (target and target[target_scores.index(max(target_scores))] != target_definition)):
        raise ContractError("invalid target definition")


def fit_isolated(raw: bytes, *, policy="catalog") -> IsolatedFit:
    if policy not in ("fixed", "catalog", "blind", "beam", *POLICIES):
        raise ValueError("unknown isolated fit policy")
    return _fit_isolated(raw, parse_fit_request(raw), policy)


def replay_isolated(raw: bytes, definition) -> IsolatedFit:
    """Replay target fit in a new worker carrying only the serialized definition."""
    request = parse_fit_request(raw)
    parent = None if definition is None else parse_definition(definition)
    if parent is not None and parent.family != request.family:
        raise ContractError("inherited definition has the wrong family")
    fit = json.loads(raw)
    fit["source"] = fit["target"][:1]  # Preserve schema v1 while withholding source examples.
    envelope = canonical_json({"fit": fit, "definition": definition})
    return _fit_isolated(envelope, request, "replay", None if parent is None else parent.sha256)


def _fit_isolated(raw, request, policy, inherited=None):
    with tempfile.TemporaryDirectory(prefix="ace-e13-solver-") as temp:
        root = Path(temp)
        _stage_solver(root)
        output, wall_us = _sandbox_python(
            ["-c", "import sys; sys.path.insert(0, '/solver'); "
             "from e13.worker import main; main(sys.argv[1])", policy],
            raw, solver=root,
        )
    try:
        with_trace = policy in (*POLICIES, "replay")
        value = read_json(output, max_bytes=32_768 if with_trace else 2_048)
        fields = ("program", "candidates", "steps", "status", "cpu_us", "rss_kib")
        require_fields(value, *fields, *(("trace",) if with_trace else ()))
        if value["status"] not in ("fit", "fallback", "fuel_exhausted"):
            raise ContractError("unexpected fit status")
        program = compile_ast(canonical_json(value["program"]),
                              allow_extension=with_trace and policy != "c_no_extend")
        if program.family != request.family or (with_trace and not program.table):
            raise ContractError("unexpected worker program family")
        candidates = integer(value["candidates"], 1, request.fuel)
        steps = integer(value["steps"], 1, request.fuel)
        trace = value.get("trace")
        if with_trace:
            _validate_trace(trace, request, policy, program, candidates, steps, inherited)
        return IsolatedFit(
            program, candidates, steps,
            WorkerMetrics(integer(value["cpu_us"], 0, 1_000_000), wall_us,
                          integer(value["rss_kib"], 1, _MEMORY_BYTES // 1024)),
            value["status"], trace,
        )
    except ContractError as error:
        raise WorkerError("invalid isolated fit result") from error
