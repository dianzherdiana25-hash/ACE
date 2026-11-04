"""Separate structural and enumerative development baselines on closed tables."""

from itertools import combinations

from .baseline import FitResult
from .blind import _graph_fit, _machine, _symbol_fit
from .contract import parse_fit_request
from .dsl import Fuel, FuelExhausted, execute
from .extension import Definition, _definitions, _graph_constraints, _graph_score, _program

POLICIES = ("structured", "enumerative")


def _graph_structured(request, fuel):
    best = _machine("G", ((0, 0, 0),), (0,))
    best_score, proposals = -1, 0
    status = "fallback"
    try:
        for definition in _definitions("G", 4):
            fuel.spend()
            constraints = _graph_constraints(definition.table, request.target, fuel)
            allowed = (1 << len(definition.table)) - 1
            for reject, _, _ in constraints:
                allowed &= ~reject

            # No allowed state makes any reachable answer cheaper than its label.
            # For each requested cost, select one eligible state attaining it.
            mask = 0
            for _, accept, _ in constraints:
                eligible = accept & allowed
                mask |= eligible & -eligible
            score = _graph_score(mask, constraints)
            proposals += 1
            if score > best_score:
                best_score = score
                accepts = tuple((mask >> state) & 1 for state in range(len(definition.table)))
                best = _program(definition, accepts)
            if score == len(request.target):
                status = "fit"
                break
    except FuelExhausted:
        status = "fuel_exhausted"
    return FitResult(best, max(1, proposals), fuel.used, status)


def _symbol_programs():
    definitions = _definitions("S", 4)
    for bits in range(13):
        for definition in definitions:
            cells = 3 * len(definition.table)
            for active in combinations(range(cells), bits):
                readout = [0] * cells
                for cell in active:
                    readout[cell] = 1
                yield definition, tuple(tuple(readout[i:i + 3]) for i in range(0, cells, 3))


def _symbol_enumerative(request, fuel):
    best = _program(Definition("S", ((0, 0, 0),)), ((0, 0, 0),))
    expected = tuple(demo.output for demo in request.target)
    best_score, proposals = -1, 0
    behaviors = set()
    status = "fallback"
    try:
        for definition, readout in _symbol_programs():
            fuel.spend()
            program = _program(definition, readout)
            predictions = tuple(execute(program, demo.input, fuel) for demo in request.target)
            proposals += 1
            if predictions in behaviors:
                continue
            behaviors.add(predictions)
            score = sum(actual == label for actual, label in zip(predictions, expected, strict=True))
            if score > best_score:
                best_score, best = score, program
            if predictions == expected:
                status = "fit"
                break
    except FuelExhausted:
        status = "fuel_exhausted"
    return FitResult(best, max(1, proposals), fuel.used, status)


def fit_comparator(raw, policy):
    request = parse_fit_request(raw)
    fuel = Fuel(request.fuel)
    fuel.spend()
    if request.family == "S":
        if policy == "enumerative":
            return _symbol_enumerative(request, fuel)
        table, attempts, status = _symbol_fit(request.target, fuel)
        return FitResult(_machine("S", table), max(attempts, 1), fuel.used, status)
    if policy == "structured":
        return _graph_structured(request, fuel)
    table, accepts, attempts, status = _graph_fit(request.target, fuel)
    return FitResult(_machine("G", table, accepts), attempts, fuel.used, status)
