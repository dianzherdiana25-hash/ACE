"""Public evaluator for the one-question pilot. Query labels stay on this side."""

import hashlib
import json
import random
from dataclasses import dataclass
from itertools import pairwise, product

from e13.contract import canonical_json, input_value, parse_fit_request, read_json
from e13.evaluator.bank import Episode, _chain
from e13.evaluator.order_challenge import _fixture
from e13.evaluator.selection import input_key, public_inputs
from e13.public_bank import Probe

from .pilot_bank import bank as routing_bank

SEED = 141601
REGIMES = ("witness_pool", "low_information", "out_of_basis")
EXAMPLES = {
    "S": (
        ((0, 2, 1), (0, 2, 1), (2, 0, 1), (1,)),
        ((1, 0, 2), (1, 0, 2), (0, 1, 2), (2,)),
        ((2, 0, 2), (2, 0, 2), (0, 2, 2), (2,)),
    ),
    "G": (
        ((0, 1, 1), (0, 1, 1, 2), (0, 1, 2, 1), (0, 1, 2, 1, 1)),
        ((0, 2, 2), (0, 2, 2, 1), (0, 2, 1, 2), (0, 2, 1, 2, 2)),
        ((1, 2), (0, 1, 2, 1), (0, 2, 1, 1), (0, 2, 2, 1, 1)),
    ),
}


@dataclass(frozen=True)
class QueryCase:
    episode: Episode
    pool: tuple[bytes, ...]
    word: tuple[int, ...]


def _subwords(events, size):
    return {events[i:i + size] for i in range(len(events) - size + 1)}


def _signature(events):
    return (events.count(1), events[-2:],
            tuple(frozenset(_subwords(events, n)) for n in (1, 2, 3)))


def _graph_outside():
    groups = {}
    found = {}
    for events in product((1, 2), repeat=8):
        trace = (0,) + events
        previous = groups.setdefault(_signature(trace), [])
        for rival in previous:
            for word in sorted(_subwords(trace, 4) - _subwords(rival, 4)):
                if word[0] != 0:
                    found.setdefault(word, (word, trace, rival, (0, 1, 2)))
        previous.append(trace)
    if len(found) < 3:
        raise ValueError("missing graph representation witnesses")
    return tuple(found[word] for word in sorted(found)[:3])


def _outside(family):
    if family == "G":
        return _graph_outside()
    words = ((0, 1, 2, 1), (1, 2, 0, 2), (2, 0, 1, 0))
    return tuple((word, ((word[0] + 1) % 3,) + word,
                  (word[0], (word[0] + 1) % 3, *word[1:]), (word[-1],))
                 for word in words)


def oracle(family, word, value):
    """Decode raw input with the development rules, independently of the AST."""
    if family == "S":
        events = tuple(0 if left < right else 1 if left == right else 2
                       for left, right in pairwise(value))
        return tuple(int(i >= len(word) and events[i - len(word):i] == word)
                     for i in range(1, len(events) + 1))
    # The bank supplies only a single forward chain, with fixed start and goal.
    edges = sorted(value["edges"])
    if (value["start"] != 0 or value["goal"] != len(edges)
            or value["nodes"] != len(edges) + 1 or not edges
            or any(edge[:2] != [i, i + 1] for i, edge in enumerate(edges))):
        raise ValueError("graph query oracle requires a forward chain")
    labels = [edge[2] for edge in edges]
    events = (0,) + tuple(1 if a == b else 2 for a, b in pairwise(labels))
    return sum(edge[3] for edge in edges) if word in _subwords(events, len(word)) else None


def _encode(family, events, rng):
    if family == "S":
        values = [0]
        for event in events:
            values.append(values[-1] + (1, 0, -1)[event] * rng.randrange(1, 5))
        low, high = -min(values), 15 - max(values)
        if low > high:
            return None
        offset = rng.randint(low, high)
        return [x + offset for x in values]
    labels = [rng.randrange(4)]
    for event in events[1:]:
        labels.append(labels[-1] if event == 1 else (labels[-1] + rng.randrange(1, 4)) % 4)
    return _chain(labels, [rng.randrange(1, 16) for _ in labels])


def _take(family, events, rng, used):
    for _ in range(256):
        value = _encode(family, events, rng)
        if value is None:
            continue
        key = input_key(family, value)
        if key not in used:
            used.add(key)
            return key
    raise ValueError("could not generate a fresh input")


def _long_pair(family, word, positive, rival, extra, *, outside):
    if family == "S":
        return (1,) * extra + positive, (1,) * extra + rival
    for event in (1, 2):
        suffix = (event,) * extra
        longer = positive + suffix, rival + suffix
        if word not in _subwords(longer[1], len(word)) and (
            not outside or _signature(longer[0]) == _signature(longer[1])
        ):
            return longer
    raise ValueError("could not preserve graph order witness under extrapolation")


def _used_public():
    used = public_inputs()
    previous = [_fixture(family).fixture for family in ("S", "G")] + list(routing_bank())
    for episode in previous:
        for role in ("source", "target"):
            used[episode.family].update(input_key(episode.family, demo["input"])
                                       for demo in json.loads(episode.fit_request)[role])
        used[episode.family].update(input_key(episode.family, json.loads(p.input))
                                   for p in episode.in_distribution + episode.extrapolation)
    return used


def bank():
    rng = random.Random(SEED)
    used = _used_public()
    cases = []
    for family in ("S", "G"):
        for regime in REGIMES:
            specs = _outside(family) if regime == "out_of_basis" else EXAMPLES[family]
            for index, (word, positive, rival, negative) in enumerate(specs):
                inputs = [_take(family, events, rng, used[family]) for events in (positive, negative)]
                demos = [{"input": json.loads(raw), "output": oracle(family, word, json.loads(raw))}
                         for raw in inputs]
                words = [positive] * (8 if regime == "low_information" else 6)
                if regime != "low_information":
                    words += [rival, rival]
                rng.shuffle(words)
                pool = tuple(_take(family, events, rng, used[family]) for events in words)
                probes = []
                for pair in range(4):
                    traces = (positive, rival) if pair < 2 else _long_pair(
                        family, word, positive, rival, pair + 1, outside=regime == "out_of_basis",
                    )
                    for events in traces:
                        raw = _take(family, events, rng, used[family])
                        probes.append(Probe(raw, oracle(family, word, json.loads(raw))))
                request = canonical_json({
                    "version": 1, "family": family, "task_id": f"{rng.getrandbits(128):032x}",
                    "seed": rng.getrandbits(32), "fuel": 75_000, "source": demos[:1], "target": demos,
                })
                parse_fit_request(request)
                episode = Episode(family, regime, "unused", f"{family}-{regime}-{index}",
                                  request, tuple(probes[:4]), tuple(probes[4:]))
                cases.append(QueryCase(episode, pool, word))
    return tuple(cases)


def answer_query(case, index):
    if type(index) is not int or not 0 <= index < len(case.pool):
        raise ValueError("invalid selected question")
    value = read_json(case.pool[index], 4_096)
    input_value(case.episode.family, value)
    return {"input": value, "output": oracle(case.episode.family, case.word, value)}


def bank_digest(cases):
    data = [(c.episode.family, c.episode.regime, c.word, json.loads(c.episode.fit_request),
             [json.loads(raw) for raw in c.pool],
             [(json.loads(p.input), p.expected)
              for p in c.episode.in_distribution + c.episode.extrapolation]) for c in cases]
    return hashlib.sha256(canonical_json(data)).hexdigest()
