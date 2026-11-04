"""Bounded blind development comparators for the two public I/O contracts."""

from itertools import product

from .baseline import FitResult
from .contract import canonical_json, parse_fit_request
from .dsl import Fuel, FuelExhausted, accepted_cost, compile_ast, graph_costs, symbol_event


def _machine(family, table, accepts=None):
    if family == "S":
        ast = {"op": "symbol_machine", "table": table}
    else:
        ast = {"op": "graph_machine", "table": table, "accept": accepts}
    return compile_ast(canonical_json({"family": family, "ast": ast}))


def _symbol_fit(demos, fuel):
    traces = []
    for example in demos:
        events = tuple(symbol_event(a, b) for a, b in zip(example.input, example.input[1:]))
        if len(events) != len(example.output) or any(bit not in (0, 1) for bit in example.output):
            return [[(0, 0)] * 3], 1, "fallback"
        traces.append(tuple(zip(events, example.output, strict=True)))

    attempts = 0
    for states in range(1, 5):
        table = {}

        def complete():
            nonlocal attempts
            fuel.spend()
            attempts += 1
            for trace in traces:
                state = 0
                for event, expected in trace:
                    fuel.spend()
                    key = (state, event)
                    if key not in table:
                        for successor in range(states):
                            table[key] = successor, expected
                            if complete():
                                return True
                        del table[key]
                        return False
                    state, bit = table[key]
                    if bit != expected:
                        return False
            return True

        try:
            if complete():
                return [[table.get((state, event), (0, 0)) for event in range(3)]
                        for state in range(states)], attempts, "fit"
        except FuelExhausted:
            return [[(0, 0)] * 3], attempts, "fuel_exhausted"
    return [[(0, 0)] * 3], attempts, "fallback"


def _graph_tables(max_states=4, *, allow_rejection=True):
    """Enumerate transition structures from event subsets and counter sizes."""
    yield ((0, 0, 0),)
    # One-state tables can forbid event types instead of tracking counts.
    if allow_rejection:
        for mask in range(1, 8):
            yield (tuple(-int(bool(mask & (1 << event))) for event in range(3)),)
    for states in range(2, max_states + 1):
        for wrap, event_mask in product((False, True), range(1, 8)):
            yield tuple(tuple(
                ((state + 1) % states if wrap else min(state + 1, states - 1))
                if event_mask & (1 << event) else state for event in range(3)
            ) for state in range(states))


def _graph_fit(demos, fuel):
    best_table, best_accepts = ((0, 0, 0),), (0,)
    best_score, attempts = -1, 0
    try:
        for table in _graph_tables():
            # Reuse paths across accepting masks, which change only the final readout.
            vectors = [graph_costs(demo.input, table, fuel) for demo in demos]
            equivalent = set()
            for mask in range(1 << len(table)):
                fuel.spend()
                accepts = tuple((mask >> state) & 1 for state in range(len(table)))
                predictions = tuple(accepted_cost(costs, accepts) for costs in vectors)
                if predictions in equivalent:
                    continue
                equivalent.add(predictions)
                attempts += 1
                score = sum(prediction == demo.output
                            for prediction, demo in zip(predictions, demos, strict=True))
                if score > best_score:
                    best_score, best_table, best_accepts = score, table, accepts
                if score == len(demos):
                    return table, accepts, attempts, "fit"
    except FuelExhausted:
        return best_table, best_accepts, max(1, attempts), "fuel_exhausted"
    return best_table, best_accepts, max(1, attempts), "fallback"


def fit_blind(raw):
    request = parse_fit_request(raw)
    fuel = Fuel(request.fuel)
    fuel.spend()
    if request.family == "S":
        table, attempts, status = _symbol_fit(request.target, fuel)
        return FitResult(_machine("S", table), max(attempts, 1), fuel.used, status)
    table, accepts, attempts, status = _graph_fit(request.target, fuel)
    return FitResult(_machine("G", table, accepts), attempts, fuel.used, status)
