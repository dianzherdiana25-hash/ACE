"""A bounded beam synthesizer over local mutations of typed state tables."""

from .baseline import FitResult
from .blind import _machine
from .contract import parse_fit_request
from .dsl import Fuel, FuelExhausted, execute


_WIDTH = 4
_MAX_PROPOSALS = 160
_MAX_ROUNDS = 6


def _initial(family):
    for states in range(1, 5):
        for advance in (False, True):
            successors = tuple((state + int(advance)) % states for state in range(states))
            if family == "S":
                yield tuple(((state, 0),) * 3 for state in successors), ()
            else:
                table = tuple((state,) * 3 for state in successors)
                yield table, (1,) * states
                yield table, (0,) + (1,) * (states - 1)


def _neighbors(family, model):
    table, accepts = model
    states = len(table)
    for i, row in enumerate(table):
        for j, value in enumerate(row):
            if family == "S":
                successor, bit = value
                replacements = [(successor, 1 - bit)]
                replacements.extend((state, bit) for state in range(states) if state != successor)
            else:
                replacements = [state for state in range(-1, states) if state != value]
            for replacement in replacements:
                updated = row[:j] + (replacement,) + row[j + 1:]
                yield table[:i] + (updated,) + table[i + 1:], accepts
    for i, bit in enumerate(accepts):
        yield table, accepts[:i] + (1 - bit,) + accepts[i + 1:]


def _score(program, demos, fuel):
    exact, partial = 0, 0
    for demo in demos:
        answer = execute(program, demo.input, fuel)
        exact += answer == demo.output
        if program.family == "S":
            partial += sum(a == b for a, b in zip(answer, demo.output))
    return exact, partial, -len(program.table)


def fit_beam(raw):
    request = parse_fit_request(raw)
    fuel = Fuel(request.fuel)
    fallback = next(_initial(request.family))
    best = _machine(request.family, *fallback)
    best_score = (-1, -1, 0)
    seen = set()
    candidates = 0

    def evaluate(models):
        nonlocal candidates, best, best_score
        ranked = []
        for model in models:
            if model in seen:
                continue
            if candidates >= _MAX_PROPOSALS:
                break
            seen.add(model)
            fuel.spend()
            candidates += 1
            program = _machine(request.family, *model)
            score = _score(program, request.target, fuel)
            ranked.append((score, model))
            if score > best_score:
                best, best_score = program, score
            if score[0] == len(request.target):
                break
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        return [model for _, model in ranked[:_WIDTH]]

    status = "fit"
    try:
        beam = evaluate(_initial(request.family))
        for _ in range(_MAX_ROUNDS):
            if not beam or best_score[0] == len(request.target) or candidates >= _MAX_PROPOSALS:
                break
            beam = evaluate(neighbor for model in beam
                            for neighbor in _neighbors(request.family, model))
    except FuelExhausted:
        status = "fuel_exhausted"
    return FitResult(best, candidates, fuel.used, status)
