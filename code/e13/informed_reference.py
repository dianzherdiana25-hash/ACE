"""Isolated reference that fits a supplied grammar class using visible examples."""

import json
import resource
import sys

from .baseline import FitResult
from .contract import (
    ContractError, array, canonical_json, parse_fit_request, read_json,
    require_fields,
)
from .dsl import Fuel, FuelExhausted, compile_ast, execute

MAX_REFERENCE_BYTES = 100_000


def fit_reference(raw):
    value = read_json(raw, MAX_REFERENCE_BYTES)
    require_fields(value, "fit", "hypotheses")
    request = parse_fit_request(canonical_json(value["fit"]))
    programs = {}
    for ast in array(value["hypotheses"], 2, 64):
        program = compile_ast(canonical_json(ast), allow_extension=True)
        if program.family != request.family or program.sha256 in programs:
            raise ContractError("invalid hypothesis inventory")
        programs[program.sha256] = program

    ordered = [programs[key] for key in sorted(programs)]
    fuel = Fuel(request.fuel)
    best, best_score, attempts = ordered[0], -1, 0
    status = "fallback"
    try:
        for program in ordered:
            fuel.spend()
            attempts += 1
            score = sum(execute(program, demo.input, fuel) == demo.output for demo in request.target)
            if score > best_score:
                best, best_score = program, score
            if score == len(request.target):
                status = "fit"
                break
    except FuelExhausted:
        status = "fuel_exhausted"
    return FitResult(best, attempts, fuel.used, status)


def main():
    result = fit_reference(sys.stdin.buffer.read(MAX_REFERENCE_BYTES + 1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    sys.stdout.buffer.write(canonical_json({
        "program": json.loads(result.program.ast), "candidates": result.candidates,
        "steps": result.steps, "status": result.status,
        "cpu_us": round((usage.ru_utime + usage.ru_stime) * 1_000_000), "rss_kib": usage.ru_maxrss,
    }))
