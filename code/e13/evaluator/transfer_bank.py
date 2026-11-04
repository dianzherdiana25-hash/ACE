"""Open engineering cases for synthesis and reuse of event-monitor definitions."""

import random
from itertools import pairwise

from ..contract import canonical_json
from ..public_bank import Probe
from .bank import Episode, _chain
from .oracle import graph


def _symbol_case(count, rng, mixed):
    if not mixed:
        offset = rng.randrange(16 - count)
        return list(range(offset + count, offset - 1, -1))
    values = [rng.randrange(8, 16)]
    for _ in range(count):
        low, high = rng.randrange(8), rng.randrange(8, 16)
        values.extend((low, high, high))
    return values


def _symbol_reference(value, period, phase, rise=False):
    count = 0
    outputs = []
    for left, right in pairwise(value):
        event = left < right if rise else left > right
        count += event
        outputs.append(int(event and count % period == phase))
    return tuple(outputs)


def _exact_edges(value, length):
    """Reference shortest walk of one fixed length via layer-by-layer relaxation."""
    costs = {value["start"]: 0}
    for _ in range(length):
        following = {}
        for start, end, _, cost in value["edges"]:
            if start in costs:
                total = costs[start] + cost
                following[end] = min(total, following.get(end, total))
        costs = following
    return costs.get(value["goal"])


def _graph_case(length, rng, branched):
    value = _chain([rng.randrange(4) for _ in range(length)],
                   [rng.randrange(1, 8) for _ in range(length)])
    if branched:
        for _ in range(length):
            value["edges"].append([rng.randrange(value["nodes"]), rng.randrange(value["nodes"]),
                                   rng.randrange(4), rng.randrange(8)])
    value["edges"].sort()
    return value


def _examples(inputs, oracle):
    return [{"input": value, "output": oracle(value)} for value in inputs]


def _symbol_inputs(period, rng, regime):
    def source_rule(value):
        return _symbol_reference(value, period, 0)

    def target_rule(value):
        if regime == "unrelated":
            return _symbol_reference(value, 2, 0, rise=True)
        return _symbol_reference(value, period, 0 if regime == "capacity" else 2)

    source = [_symbol_case(2 * period + extra, rng, mixed)
              for extra, mixed in ((0, False), (1, True), (2, True))]
    counts = (2 * period, 2 * period + 1) if regime == "capacity" else (2, 3)
    target = [_symbol_case(count, rng, mixed)
              for count in counts for mixed in (False, True)]
    ordinary = [_symbol_case(n, rng, bool(i % 2))
                for i, n in enumerate((period, period + 1, period + 2, period + 3))]
    extrapolation = [_symbol_case(n, rng, True)
                     for n in (2 * period, 2 * period + 1, 2 * period + 2, 3 * period)]
    return source, target, ordinary, extrapolation, source_rule, target_rule


def _graph_inputs(period, rng, regime):
    def source_rule(value):
        return _exact_edges(value, period)

    def target_rule(value):
        if regime == "unrelated":
            return graph("repeat_odd", value)
        return _exact_edges(value, period if regime == "capacity" else 3)

    source = [_graph_case(n, rng, False) for n in range(period + 3)]
    source += [_graph_case(n, rng, True) for n in (period - 1, period, period + 1)]
    counts = range(period + 3) if regime == "capacity" else (1, 2, 3, 4)
    target = [_graph_case(n, rng, False) for n in counts]
    ordinary = [_graph_case(n, rng, True) for n in (2, 3, period, period + 1)]
    extrapolation = [_graph_case(n, rng, True)
                     for n in (period + 3, period + 4, period + 5, period + 6)]
    return source, target, ordinary, extrapolation, source_rule, target_rule


def transfer_bank(seed=131503):
    rng = random.Random(seed)
    episodes = []
    for family, build in (("S", _symbol_inputs), ("G", _graph_inputs)):
        for period in (5, 6):
            for regime in ("capacity", "related", "unrelated"):
                source, target, ordinary, extrapolation, source_rule, target_rule = build(
                    period, rng, regime,
                )
                used = {canonical_json(value) for value in source + target}
                probes = []
                for cases in (ordinary, extrapolation):
                    suite = []
                    for value in cases:
                        raw = canonical_json(value)
                        if raw in used:
                            raise ValueError("duplicate demonstration or probe")
                        used.add(raw)
                        suite.append(Probe(raw, target_rule(value)))
                    probes.append(tuple(suite))
                payload = canonical_json({
                    "version": 1, "family": family, "task_id": f"{rng.getrandbits(128):032x}",
                    "seed": rng.getrandbits(32), "fuel": 100_000,
                    "source": _examples(source, source_rule), "target": _examples(target, target_rule),
                })
                episodes.append(Episode(family, regime, f"{family}:source:{period}",
                                        f"{family}:{regime}:{period}", payload, *probes))
    return tuple(episodes)
