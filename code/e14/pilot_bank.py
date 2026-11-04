"""Fresh public development cases for representation routing."""

import hashlib
import json
import random

from e13.contract import canonical_json, parse_fit_request
from e13.evaluator.bank import Episode, _chain
from e13.evaluator.order_challenge import _answer, _fixture, _graph, _symbols
from e13.evaluator.selection import input_key, public_inputs
from e13.evaluator.transfer_bank import _exact_edges
from e13.public_bank import Probe

SEED = 141501
REGIMES = ("count", "order_witness", "order_ambiguous")
WORDS = {
    "S": ((2, 0, 1), (0, 2, 2), (1, 2, 0), (2, 1, 1), (1, 0, 0), (0, 1, 0)),
    "G": ((1, 2, 2), (2, 1, 2), (0, 1, 2), (2, 2, 1), (2, 1, 1), (0, 2, 1)),
}


def _contains(events, word):
    return any(events[i:i + len(word)] == word for i in range(len(events) - len(word) + 1))


def _case(family, word, events, settings):
    if family == "S":
        value = _symbols(events, *settings)
        output = _answer(family, events, value, word)
    else:
        value = _graph(events[1:], *settings)
        output = _answer(family, events, value, word)
    return value, output


def _ordered(family, word, index, witness):
    if family == "S":
        positive, rival = word, (word[1], word[0], word[2])
    elif word[0] == 0:
        positive, rival = word, (0, word[2], word[1])
    else:
        j = next(i for i in (0, 1) if word[i] != word[i + 1])
        swapped = list(word)
        swapped[j], swapped[j + 1] = swapped[j + 1], swapped[j]
        positive, rival = (0,) + word, (0, *swapped)

    demos = [_case(family, word, positive, (4 + index, 1) if family == "S" else (index, 6))]
    if witness:
        demos.append(_case(family, word, rival, (5 + index, 1) if family == "S" else (index, 6)))
    cases = []
    for pair in range(4):
        settings = ((7 + index + pair, 1) if family == "S"
                    else ((index + pair) % 4, 7 + index + pair))
        words = positive, rival
        if pair >= 2:
            if family == "S":
                words = (1,) * (pair + 3) + positive, (1,) * (pair + 3) + rival
            else:
                suffix = next((event,) * (pair + 2) for event in (1, 2)
                              if not _contains(rival + (event,) * (pair + 2), word))
                words = positive + suffix, rival + suffix
        cases.extend(_case(family, word, events, settings) for events in words)
    return demos, cases


def _counter_symbol(index):
    trigger, period = index, index + 2
    keep_balance = ((2,), (0, 2), (0,))[trigger]

    def case(count, origin):
        events = ((trigger,) + keep_balance) * count
        values = _symbols(events, origin, 1)
        used, expected = 0, []
        for event in events:
            used += event == trigger
            expected.append(int(event == trigger and used % period == 0))
        return values, tuple(expected)

    demos = [case(n, index + 2) for n in (period - 1, period, period + 1, 2 * period + 1)]
    counts = (period - 1, period, period + 1, 2 * period,
              2 * period + 1, 2 * period + 2, 3 * period, 3 * period + 1)
    return demos, [case(n, 7 + index + j % 3) for j, n in enumerate(counts)]


def _counter_graph(index, rng):
    length = index + 2

    def case(n, loop, demo=False):
        value = _chain([rng.randrange(4) for _ in range(n)],
                       [rng.randrange(1, 5) if demo else rng.randrange(5, 11) for _ in range(n)])
        if loop:
            value["edges"].append([0, 0, rng.randrange(4), rng.randrange(1, 8)])
        value["edges"].sort()
        return value, _exact_edges(value, length)

    demos = [case(n, False, demo=True) for n in range(1, length + 3)]
    cases = [case(n, loop) for n, loop in
             ((length - 1, False), (length, False), (length + 1, False), (length, True),
              (length - 1, True), (length + 2, True), (length, True), (length + 4, False))]
    return demos, cases


def _fresh(family, case, used, fixed_length=None):
    value, label = case
    numbers = value if family == "S" else [edge[3] for edge in value["edges"]]
    offsets = sorted(range(-min(numbers), 16 - max(numbers)), key=lambda x: (abs(x), x))
    for offset in offsets:
        if family == "S":
            updated, expected = [x + offset for x in value], label
        else:
            updated = {**value, "edges": [[a, b, event, cost + offset]
                                          for a, b, event, cost in value["edges"]]}
            length = fixed_length if fixed_length is not None else len(value["edges"])
            expected = None if label is None else label + offset * length
        key = input_key(family, updated)
        if key not in used:
            used.add(key)
            return updated, expected
    raise ValueError("no fresh input with the same event structure")

def bank():
    rng = random.Random(SEED)
    episodes = []
    used = public_inputs()
    for family in ("S", "G"):
        previous = _fixture(family).fixture
        used[family].update(input_key(family, json.loads(p.input))
                            for p in previous.in_distribution + previous.extrapolation)
        used[family].update(input_key(family, example["input"])
                            for example in json.loads(previous.fit_request)["target"])
        for regime in REGIMES:
            for index in range(3):
                if regime == "count":
                    demos, cases = (_counter_symbol(index) if family == "S"
                                    else _counter_graph(index, rng))
                else:
                    offset = 0 if regime == "order_witness" else 3
                    demos, cases = _ordered(family, WORDS[family][offset + index], index,
                                            regime == "order_witness")
                length = index + 2 if family == "G" and regime == "count" else None
                demos = [_fresh(family, case, used[family], length) for case in demos]
                cases = [_fresh(family, case, used[family], length) for case in cases]
                visible = [{"input": value, "output": label} for value, label in demos]
                request = canonical_json({
                    "version": 1, "family": family, "task_id": f"{rng.getrandbits(128):032x}",
                    "seed": rng.getrandbits(32), "fuel": 75_000,
                    "source": visible[:1], "target": visible,
                })
                parse_fit_request(request)
                probes = tuple(Probe(canonical_json(value), expected) for value, expected in cases)
                keys = {probe.input for probe in probes}
                if (len(keys) != 8 or keys.intersection(canonical_json(d["input"]) for d in visible)):
                    raise ValueError(f"development input overlap: {family} {regime} {index}")
                episodes.append(Episode(family, regime, "unused", f"{family}-{regime}-{index}",
                                        request, probes[:4], probes[4:]))
    return tuple(episodes)


def bank_sha256(episodes):
    return hashlib.sha256(canonical_json([
        (episode.family, episode.regime, episode.target_rule, json.loads(episode.fit_request),
         [(json.loads(probe.input), probe.expected)
          for probe in episode.in_distribution + episode.extrapolation])
        for episode in episodes
    ])).hexdigest()
