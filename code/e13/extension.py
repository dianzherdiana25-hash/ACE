"""Development-only synthesis and transfer of typed event-monitor definitions."""

import hashlib
import json
import random
from dataclasses import dataclass

from .baseline import FitResult
from .blind import _graph_tables
from .contract import (
    MAX_FIT_BYTES, ContractError, array, canonical_json, integer, parse_fit_request, read_json,
    require_fields,
)
from .dsl import Fuel, FuelExhausted, compile_ast, graph_costs, symbol_event

POLICIES = ("c_extend", "c_no_extend", "c_no_transfer", "c_sham")
REPLAY_BYTES = MAX_FIT_BYTES + 1024


@dataclass(frozen=True)
class Definition:
    family: str
    table: tuple[tuple[int, ...], ...]

    @property
    def value(self):
        return {"version": 1, "family": self.family, "transitions": self.table}

    @property
    def sha256(self):
        return hashlib.sha256(canonical_json(self.value)).hexdigest()


def parse_definition(value):
    require_fields(value, "version", "family", "transitions")
    integer(value["version"], 1, 1)
    family = value["family"]
    if family not in ("S", "G"):
        raise ContractError("unknown definition family")
    rows = array(value["transitions"], 1, 8)
    minimum = 0 if family == "S" else -1
    return Definition(family, tuple(tuple(integer(cell, minimum, len(rows) - 1)
                                          for cell in array(row, 3, 3)) for row in rows))


def definition_from_program(program):
    transitions = program.table
    if program.family == "S":
        transitions = tuple(tuple(state for state, _ in row) for row in transitions)
    return Definition(program.family, transitions)


def _program(definition, readout):
    table = definition.table
    suffix = "extension" if len(table) > 4 else "machine"
    if definition.family == "S":
        ast = {"op": f"symbol_{suffix}", "table": [
            list(zip(row, readout[i], strict=True)) for i, row in enumerate(table)
        ]}
    else:
        ast = {"op": f"graph_{suffix}", "table": table, "accept": readout}
    return compile_ast(canonical_json({"family": definition.family, "ast": ast}),
                       allow_extension=len(table) > 4)


def _symbol_readout(table, demos, fuel):
    counts = [[[0, 0] for _ in row] for row in table]
    traces = []
    for demo in demos:
        if len(demo.output) != max(0, len(demo.input) - 1) or any(bit > 1 for bit in demo.output):
            continue
        state, visits = 0, []
        for left, right, bit in zip(demo.input, demo.input[1:], demo.output):
            fuel.spend()
            event = symbol_event(left, right)
            counts[state][event][bit] += 1
            visits.append((state, event))
            state = table[state][event]
        traces.append((visits, demo.output))

    readout = tuple(tuple(int(one > zero) for zero, one in row) for row in counts)
    score = 0
    for visits, expected in traces:
        outputs = []
        for state, event in visits:
            fuel.spend()
            outputs.append(readout[state][event])
        score += tuple(outputs) == expected
    return readout, score


def _graph_readout(table, demos, fuel):
    constraints = []
    for demo in demos:
        costs = graph_costs(demo.input, table, fuel)
        reject, accept = 0, 0
        for state, cost in enumerate(costs):
            if cost is None:
                continue
            if demo.output is None or cost < demo.output:
                reject |= 1 << state
            elif cost == demo.output:
                accept |= 1 << state
        constraints.append((reject, accept, demo.output is None))

    best_mask, best_score = 0, -1
    for mask in range(1 << len(table)):
        fuel.spend()
        score = sum(not mask & reject and (unreachable or bool(mask & accept))
                    for reject, accept, unreachable in constraints)
        if score > best_score:
            best_mask, best_score = mask, score
        if score == len(demos):
            break
    return tuple((best_mask >> state) & 1 for state in range(len(table))), best_score


@dataclass(frozen=True)
class Candidate:
    definition: Definition
    readout: tuple
    score: int


def _evaluate(family, demos, definitions, fuel, *, stop_on_match):
    candidates = []
    readout = _symbol_readout if family == "S" else _graph_readout
    try:
        for definition in definitions:
            fuel.spend()
            fitted, score = readout(definition.table, demos, fuel)
            candidates.append(Candidate(definition, fitted, score))
            if stop_on_match and score == len(demos):
                break
    except FuelExhausted:
        return candidates, True
    return candidates, False


def _definitions(family, max_states):
    return tuple(Definition(family, table)
                 for table in _graph_tables(max_states, allow_rejection=family == "G"))


def _source_selection(candidates, seed, sham):
    scores = [candidate.score for candidate in candidates]
    shift = random.Random(seed).randrange(1, len(scores)) if sham and len(scores) > 1 else 0
    selected_scores = scores[shift:] + scores[:shift]
    index = max(range(len(scores)), key=selected_scores.__getitem__, default=None)
    selected = candidates[index].definition if index is not None else None
    return selected, shift, scores == selected_scores


def _trace(candidates):
    return [[candidate.definition.sha256, candidate.score] for candidate in candidates]


def _fit_target(request, definitions, inherited, budget):
    if inherited is not None:
        # Move one definition to the front. Both policies have the same remaining order.
        definitions = (inherited,) + tuple(item for item in definitions if item != inherited)
    fuel = Fuel(budget)
    candidates, exhausted = _evaluate(request.family, request.target, definitions, fuel,
                                       stop_on_match=True)
    if candidates:
        selected = max(candidates, key=lambda item: item.score)
    else:
        blank = ((0, 0, 0),) if request.family == "S" else (0,)
        selected = Candidate(Definition(request.family, ((0, 0, 0),)), blank, 0)
    return selected, candidates, exhausted, fuel.used


@dataclass(frozen=True)
class SourceFit:
    candidates: tuple[Candidate, ...] = ()
    steps: int = 0
    exhausted: bool = False
    selected: Definition | None = None
    shift: int = 0
    unchanged: bool = True


def _result(request, source, parent, definitions):
    target, candidates, exhausted, steps = _fit_target(
        request, definitions, parent, request.fuel - request.fuel // 2,
    )
    trace = {
        "source": _trace(source.candidates), "target": _trace(candidates),
        "source_selected": None if source.selected is None else source.selected.sha256,
        "source_definition": None if source.selected is None else source.selected.value,
        "source_steps": source.steps, "source_exhausted": source.exhausted,
        "sham_shift": source.shift, "sham_unchanged": source.unchanged,
        "parent": None if parent is None else parent.sha256,
        "target_definition": target.definition.sha256, "target_steps": steps,
    }
    return FitResult(_program(target.definition, target.readout), max(1, len(source.candidates) + len(candidates)),
                     source.steps + steps, "fuel_exhausted" if exhausted else "fit", trace)


def fit_extension(raw, policy):
    request = parse_fit_request(raw)
    definitions = _definitions(request.family, 4 if policy == "c_no_extend" else 8)
    reserved = request.fuel // 2
    source, used, exhausted = [], 0, False
    if reserved:
        fuel = Fuel(reserved)
        source, exhausted = _evaluate(request.family, request.source, definitions, fuel,
                                      stop_on_match=False)
        used = fuel.used
    selected, shift, unchanged = _source_selection(source, request.seed, policy == "c_sham")
    parent = None
    if selected is not None and policy != "c_no_transfer":
        parent = parse_definition(json.loads(canonical_json(selected.value)))
    source_fit = SourceFit(tuple(source), used, exhausted, selected, shift, unchanged)
    return _result(request, source_fit, parent, definitions)


def replay_extension(raw):
    envelope = read_json(raw, REPLAY_BYTES)
    require_fields(envelope, "fit", "definition")
    request = parse_fit_request(canonical_json(envelope["fit"]))
    value = envelope["definition"]
    parent = None if value is None else parse_definition(value)
    if parent is not None and parent.family != request.family:
        raise ContractError("inherited definition has the wrong family")
    return _result(request, SourceFit(), parent, _definitions(request.family, 8))
