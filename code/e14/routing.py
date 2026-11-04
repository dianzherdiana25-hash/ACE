"""Diagnose demo inconsistency, then select a bounded representation."""

import json
import resource
import sys
from dataclasses import dataclass
from itertools import product

from e13.contract import MAX_FIT_BYTES, canonical_json, parse_fit_request
from e13.dsl import Fuel, FuelExhausted, Program, compile_ast, execute
from e13.extension import _definitions, _evaluate, _program
from e13.patterns import pattern_ast

POLICIES = ("counter_only", "order_only", "adaptive")


@dataclass(frozen=True)
class Search:
    program: Program | None
    matches: int
    proposals: int
    capped: bool


def _counter(request, fuel):
    definitions = _definitions(request.family, 8)
    candidates, capped = _evaluate(request.family, request.target, definitions, fuel,
                                   stop_on_match=True)
    if not candidates:
        return Search(None, -1, 0, capped)
    best = max(candidates, key=lambda item: item.score)
    return Search(_program(best.definition, best.readout), best.score, len(candidates), capped)


def _order(request, fuel):
    best, matches, count = None, -1, 0
    try:
        for length in (1, 2, 3):
            for pattern in product(range(3), repeat=length):
                fuel.spend()
                program = compile_ast(canonical_json(pattern_ast(request.family, pattern)))
                score = sum(execute(program, demo.input, fuel) == demo.output for demo in request.target)
                count += 1
                if score > matches:
                    best, matches = program, score
                if score == len(request.target):
                    return Search(best, matches, count, False)
    except FuelExhausted:
        return Search(best, matches, count, True)
    return Search(best, matches, count, False)


def fit_routing(raw, policy):
    if policy not in POLICIES:
        raise ValueError("unknown routing policy")
    request = parse_fit_request(raw)
    fuel = Fuel(request.fuel)
    empty = Search(None, -1, 0, False)
    counter = _counter(request, fuel) if policy != "order_only" else empty
    limit = len(request.target)
    if policy == "counter_only":
        diagnosis = "counter_control"
    elif policy == "order_only":
        diagnosis = "order_control"
    elif counter.capped:
        diagnosis = "counter_budget_exhausted"
    elif counter.matches == limit:
        diagnosis = "counter_consistent"
    else:
        diagnosis = "counter_inconsistent"

    order = _order(request, fuel) if diagnosis in ("order_control", "counter_inconsistent") else empty
    route, chosen = ("order", order) if order.matches > counter.matches else ("counter", counter)
    if chosen.program is None:
        # A complete candidate is absent only if the cap stopped the first proposal.
        program = compile_ast(canonical_json(pattern_ast(request.family, (0,))))
        route = "budget_fallback"
    else:
        program = chosen.program
    capped = counter.capped or order.capped
    status = "fuel_exhausted" if capped else "fit" if chosen.matches == limit else "fallback"
    return {
        "program": json.loads(program.ast), "status": status, "steps": fuel.used,
        "proposals": max(1, counter.proposals + order.proposals),
        "trace": {"diagnosis": diagnosis, "route": route, "counter_matches": counter.matches,
                  "order_matches": order.matches, "demo_count": limit},
    }


def main(policy):
    response = fit_routing(sys.stdin.buffer.read(MAX_FIT_BYTES + 1), policy)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    response.update(cpu_us=round((usage.ru_utime + usage.ru_stime) * 1_000_000),
                    rss_kib=usage.ru_maxrss)
    sys.stdout.buffer.write(canonical_json(response))
