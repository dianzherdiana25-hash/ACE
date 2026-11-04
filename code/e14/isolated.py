"""Stage only the experimental worker and trusted typed-DSL dependencies."""

import shutil
import tempfile
from pathlib import Path

from e13.contract import ContractError, canonical_json, integer, parse_fit_request, read_json, require_fields
from e13.dsl import compile_ast
from e13.isolation import READY_MARKER, IsolatedFit, WorkerError, WorkerMetrics, _sandbox_python, _stage_solver

from .routing import POLICIES


def fit_isolated(raw, *, policy):
    if policy not in POLICIES:
        raise ValueError("unknown isolated routing policy")
    request = parse_fit_request(raw)
    with tempfile.TemporaryDirectory(prefix="ace-e14-routing-") as temp:
        root = Path(temp)
        _stage_solver(root)
        source = Path(__file__).resolve().parent
        shutil.copyfile(source.parent / "e13" / "patterns.py", root / "e13" / "patterns.py")
        (root / "e14").mkdir()
        for name in ("__init__.py", "routing.py"):
            shutil.copyfile(source / name, root / "e14" / name)
        script = ("import sys; sys.path.insert(0, '/solver'); from e14.routing import main; "
                  f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main(sys.argv[1])")
        output, wall = _sandbox_python(["-c", script, policy], raw, solver=root)
    try:
        row = read_json(output, 2_048)
        require_fields(row, "program", "status", "steps", "proposals", "trace", "cpu_us", "rss_kib")
        program = compile_ast(canonical_json(row["program"]), allow_extension=True)
        if program.family != request.family or row["status"] not in ("fit", "fallback", "fuel_exhausted"):
            raise ContractError("invalid routing program")
        trace = row["trace"]
        require_fields(trace, "diagnosis", "route", "counter_matches", "order_matches", "demo_count")
        if trace["diagnosis"] not in (
            "counter_control", "order_control", "counter_consistent", "counter_inconsistent",
            "counter_budget_exhausted",
        ) or trace["route"] not in ("counter", "order", "budget_fallback"):
            raise ContractError("invalid routing trace")
        integer(trace["demo_count"], len(request.target), len(request.target))
        for name in ("counter_matches", "order_matches"):
            integer(trace[name], -1, len(request.target))
        return IsolatedFit(
            program, integer(row["proposals"], 1, request.fuel), integer(row["steps"], 1, request.fuel),
            WorkerMetrics(integer(row["cpu_us"], 0, 1_000_000), wall,
                          integer(row["rss_kib"], 1, 128 * 1024)), row["status"], trace,
        )
    except ContractError as error:
        raise WorkerError("invalid E1.4 routing response") from error
