"""Score-independent public E1.4g bank and evaluator-side oracle."""

import argparse
import gzip
import hashlib
import json
import random
from itertools import pairwise, product
from pathlib import Path

from e13.contract import canonical_json

SEEDS = {"natural": 142101, "motifs": 142102, "enriched": 142103}
FAMILIES = ("S", "G")
LENGTHS = (5, 6)
BLOCKS = 6
DEMO_N = 32
QUERY_N = PROBE_N = 8


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def alphabet(family):
    return (0, 1, 2) if family == "S" else (1, 2)


def windows(events, length):
    return {events[i:i + length] for i in range(len(events) - length + 1)}


def trace(family, raw):
    if family == "S":
        return tuple(0 if a < b else 1 if a == b else 2 for a, b in pairwise(raw))
    return tuple(1 if a[2] == b[2] else 2 for a, b in pairwise(raw["edges"]))


def oracle(family, word, raw):
    events = trace(family, raw)
    if family == "G":
        return sum(edge[3] for edge in raw["edges"]) if word in windows(events, len(word)) else None
    return [int(end >= len(word) and events[end - len(word):end] == word)
            for end in range(1, len(events) + 1)]


def _tokens(events, rng):
    values = [0]
    varying = rng.sample(range(len(events)), k=rng.randrange(4)) if len(events) > 14 else ()
    for i, event in enumerate(events):
        step = rng.randint(1, 3) if len(events) <= 14 else 1 + (i in varying)
        values.append(values[-1] + (step, 0, -step)[event])
    low, high = -min(values), 15 - max(values)
    if low > high:
        return None
    offset = rng.randint(low, high)
    return [value + offset for value in values]


def _chain(events, rng):
    labels = [rng.randrange(4)]
    for event in events:
        labels.append(labels[-1] if event == 1 else (labels[-1] + rng.randint(1, 3)) % 4)
    return {"nodes": len(labels) + 1, "start": 0, "goal": len(labels),
            "edges": [[i, i + 1, label, rng.randint(1, 15)] for i, label in enumerate(labels)]}


def _fresh(family, events, rng, used):
    encode = _tokens if family == "S" else _chain
    for _ in range(512):
        value = encode(events, rng)
        if value is None:
            continue
        key = sha(canonical_json(value))
        if key not in used:
            used.add(key)
            return value
    raise ValueError(f"could not encode a fresh {family} input of {len(events)} events")


def _random_trace(family, rng):
    return tuple(rng.choice(alphabet(family)) for _ in range(rng.randint(9, 14)))


def natural_inputs(family, rng, used):
    """The natural inputs are allocated before the motif RNG is opened."""
    def sample(n):
        return [_fresh(family, _random_trace(family, rng), rng, used) for _ in range(n)]

    return {"pool": sample(QUERY_N), "probes": sample(PROBE_N), "demos": sample(DEMO_N)}


def _debruijn(symbols, length):
    """A cyclic word visiting each length-L word once."""
    work = [0] * (len(symbols) * length)
    result = []

    def generate(t, p):
        if t > length:
            if length % p == 0:
                result.extend(symbols[x] for x in work[1:p + 1])
            return
        work[t] = work[t - p]
        generate(t + 1, p)
        for j in range(work[t - p] + 1, len(symbols)):
            work[t] = j
            generate(t + 1, t)

    generate(1, 1)
    return tuple(result)


def _legal(family, events):
    if family == "G":
        return len(events) <= 14
    if len(events) > 63:
        return False
    current = low = high = 0
    for event in events:
        current += (1, 0, -1)[event]
        low, high = min(low, current), max(high, current)
    return high - low <= 13


def _cover(family, length, twins):
    cycle = _debruijn(alphabet(family), length)
    sequence = cycle + cycle[:length - 1]
    result = []
    i = 0
    while i < len(cycle):
        if sequence[i:i + length] in twins:
            i += 1
            continue
        end = i
        while (end + 1 < len(cycle) and sequence[end + 1:end + 1 + length] not in twins
               and _legal(family, sequence[i:end + 1 + length])):
            end += 1
        result.append(sequence[i:end + length])
        i = end + 1
    expected = set(product(alphabet(family), repeat=length)) - set(twins)
    observed = set().union(*(windows(events, length) for events in result))
    if observed != expected or len(result) > DEMO_N:
        raise ValueError(f"incomplete negative cover: {family}/{length}/{len(result)}")
    return result


def _graph_twins(forbidden):
    groups = {}
    selected = []
    taken = set(forbidden)
    for events in product((1, 2), repeat=12):
        key = frozenset(windows(events, 5))
        previous = groups.setdefault(key, [])
        current6 = windows(events, 6)
        for rival, old6 in previous:
            a = sorted(current6 - old6 - taken)
            b = sorted(old6 - current6 - taken)
            if a and b:
                words = (a[0], b[0])
                selected.append((words, (events, rival)))
                taken.update(words)
                if len(selected) == BLOCKS:
                    return selected
                break
        previous.append((events, current6))
    raise ValueError("insufficient distinct graph twins")


def _pairs(family, length, forbidden, rng):
    if family == "G" and length == 6:
        return _graph_twins(forbidden)
    if family == "S" and length == 6:
        options = [((0, *tail), (2, *tail)) for tail in product((0, 1, 2), repeat=5)
                   if (0, *tail) not in forbidden and (2, *tail) not in forbidden]
        rng.shuffle(options)
        return [(pair, pair) for pair in options[:BLOCKS]]
    words = [word for word in product(alphabet(family), repeat=length) if word not in forbidden]
    rng.shuffle(words)
    return [(tuple(words[i:i + 2]), tuple(words[i:i + 2])) for i in range(0, 2 * BLOCKS, 2)]


def _negative_trace(family, length, twins, size, rng):
    for _ in range(512):
        value = tuple(rng.choice(alphabet(family)) for _ in range(size))
        if not windows(value, length).intersection(twins):
            return value
    raise ValueError("could not draw a negative trace")


def _enriched(family, length, twins, witnesses, rng, used):
    for i, word in enumerate(twins):
        if word not in windows(witnesses[i], length) or word in windows(witnesses[1 - i], length):
            raise ValueError("invalid positive witness")
    demos = _cover(family, length, twins)
    demos.extend(_negative_trace(family, length, twins, 10, rng)
                 for _ in range(DEMO_N - len(demos)))
    witness_len = len(witnesses[0])
    queries = [*witnesses, *(_negative_trace(family, length, twins, witness_len, rng)
                            for _ in range(QUERY_N - 2))]
    rng.shuffle(queries)
    probes = [witnesses[i % 2] for i in range(PROBE_N)]
    return {role: [_fresh(family, events, rng, used) for events in raw]
            for role, raw in (("demos", demos), ("pool", queries), ("probes", probes))}


def build(history):
    used = {family: set(history[family]) for family in FAMILIES}
    natural, motifs, enriched = (random.Random(SEEDS[name]) for name in ("natural", "motifs", "enriched"))
    coordinates = [(family, length, slot) for family in FAMILIES
                   for length in LENGTHS for slot in range(BLOCKS)]
    allocated = {(family, length, slot): natural_inputs(family, natural, used[family])
                 for family, length, slot in coordinates}
    result = []
    for family in FAMILIES:
        for length in LENGTHS:
            words = motifs.sample(list(product(alphabet(family), repeat=length)), BLOCKS)
            for slot, word in enumerate(words):
                result.append({"distribution": "natural", "family": family, "length": length,
                               "block": slot, "words": [word], **allocated[family, length, slot]})
            for slot, (twins, witnesses) in enumerate(_pairs(family, length, words, motifs)):
                twins = tuple(sorted(twins))
                witnesses = tuple(next(events for events in witnesses if word in windows(events, length))
                                  for word in twins)
                inputs = _enriched(family, length, twins, witnesses, enriched, used[family])
                result.append({"distribution": "opportunity", "family": family, "length": length,
                               "block": slot, "words": twins, **inputs})
    return {"version": 1, "seeds": SEEDS, "historical_index_sha256": sha(canonical_json(history)),
            "historical_inputs": {f: len(history[f]) for f in FAMILIES}, "blocks": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = build(json.loads(args.history.read_text()))
    raw = canonical_json(data)
    args.output.write_bytes(gzip.compress(raw, mtime=0))
    print(json.dumps({"bank_sha256": sha(raw), "blocks": len(data["blocks"]),
                      "history_sha256": data["historical_index_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
