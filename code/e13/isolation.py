"""Run the fixed development solver with an isolated, bounded JSON transport."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

from .contract import (
    ContractError, canonical_json, integer, parse_fit_request, read_json,
    require_fields,
)
from .dsl import Program, compile_ast


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


_SOLVER_FILES = ("__init__.py", "baseline.py", "beam.py", "blind.py", "contract.py", "dsl.py", "worker.py")
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


def fit_isolated(raw: bytes, *, policy="catalog") -> IsolatedFit:
    if policy not in ("fixed", "catalog", "blind", "beam"):
        raise ValueError("unknown isolated fit policy")
    request = parse_fit_request(raw)
    with tempfile.TemporaryDirectory(prefix="ace-e13-solver-") as temp:
        root = Path(temp)
        _stage_solver(root)
        output, wall_us = _sandbox_python(
            ["-c", "import sys; sys.path.insert(0, '/solver'); "
             "from e13.worker import main; main(sys.argv[1])", policy],
            raw, solver=root,
        )
    try:
        value = read_json(output, max_bytes=2_048)
        require_fields(value, "program", "candidates", "steps", "status", "cpu_us", "rss_kib")
        if value["status"] not in ("fit", "fallback", "fuel_exhausted"):
            raise ContractError("unexpected fit status")
        program = compile_ast(canonical_json(value["program"]))
        if program.family != request.family:
            raise ContractError("unexpected worker program family")
        return IsolatedFit(
            program, integer(value["candidates"], 1, request.fuel),
            integer(value["steps"], 1, request.fuel),
            WorkerMetrics(integer(value["cpu_us"], 0, 1_000_000), wall_us,
                          integer(value["rss_kib"], 1, _MEMORY_BYTES // 1024)),
            value["status"],
        )
    except ContractError as error:
        raise WorkerError("invalid isolated fit result") from error
