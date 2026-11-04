"""A small blind enumerator for development checks."""

from dataclasses import dataclass

from .contract import canonical_json, parse_fit_request
from .dsl import Fuel, Program, compile_ast, execute


@dataclass(frozen=True)
class FitResult:
    program: Program
    candidates: int
    steps: int


def _catalog(family):
    if family == "S":
        root, rules = "pair_flags", ("eq", "lt", "gt")
    else:
        root, rules = "path_cost", ("any", "different", "same")
    for rule in rules:
        yield compile_ast(canonical_json({
            "family": family, "ast": {"op": root, "rule": {"op": rule}},
        }))


def fit(raw: bytes) -> FitResult:
    request = parse_fit_request(raw)
    fuel = Fuel(request.fuel)
    best_program = None
    best_score = (-1, -1)
    for count, program in enumerate(_catalog(request.family), 1):
        target_score = sum(execute(program, demo.input, fuel) == demo.output
                           for demo in request.target)
        source_score = sum(execute(program, demo.input, fuel) == demo.output
                           for demo in request.source)
        score = (target_score, source_score)
        if score > best_score:
            best_program, best_score = program, score

    assert best_program is not None
    return FitResult(best_program, count, fuel.used)
