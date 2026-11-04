"""Run the grammar-informed control without revealing the true hypothesis or probes."""

import json
import shutil
import tempfile
from pathlib import Path

from ..contract import ContractError, canonical_json, integer, parse_fit_request, read_json, require_fields
from ..dsl import compile_ast
from ..isolation import (
    READY_MARKER, IsolatedFit, WorkerError, WorkerMetrics, _sandbox_python, _stage_solver,
)
from .selection_budget import evaluate_arm

POLICY = "structured_oracle"


def _fit(raw, hypotheses):
    request = parse_fit_request(raw)
    payload = canonical_json({"fit": json.loads(raw), "hypotheses": hypotheses})
    with tempfile.TemporaryDirectory(prefix="ace-e13-informed-") as temp:
        root = Path(temp)
        _stage_solver(root)
        source = Path(__file__).resolve().parents[1] / "informed_reference.py"
        shutil.copyfile(source, root / "e13" / source.name)
        script = ("import sys; sys.path.insert(0, '/solver'); "
                  "from e13.informed_reference import main; "
                  f"sys.stderr.buffer.write({READY_MARKER!r}); sys.stderr.flush(); main()")
        output, wall = _sandbox_python(["-c", script], payload, solver=root)
    try:
        row = read_json(output, 2_048)
        require_fields(row, "program", "candidates", "steps", "status", "cpu_us", "rss_kib")
        program = compile_ast(canonical_json(row["program"]), allow_extension=True)
        if (program.family != request.family or program.ast not in {canonical_json(ast) for ast in hypotheses}
                or row["status"] not in ("fit", "fallback", "fuel_exhausted")):
            raise ContractError("invalid informed response")
        return IsolatedFit(program, integer(row["candidates"], 1, len(hypotheses)),
                           integer(row["steps"], 1, request.fuel),
                           WorkerMetrics(integer(row["cpu_us"], 0, 1_000_000), wall,
                                         integer(row["rss_kib"], 1, 128 * 1024)), row["status"])
    except ContractError as error:
        # An invalid evaluator-owned hypothesis or response holds the run.
        raise WorkerError("invalid informed-reference response") from error


def evaluate_reference(episode, hypotheses):
    def fit(raw, *, policy):
        return _fit(raw, hypotheses)

    return evaluate_arm(episode, POLICY, fit_policy=fit, reference_extension=True)
