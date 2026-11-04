"""Fixed sandbox worker that synthesizes queries from compatible words."""

import random
import resource
import sys
from collections import Counter
from fractions import Fraction
from itertools import product

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14g_worker import WIRE_BYTES, _features, _label

LENGTHS = (5, 6)
MODES = ("guided", "fixed", "random")
CAP = 8


def query_trace(family, raw):
    count, _ = _features(family, raw, 5)
    if count not in LENGTHS:
        raise ContractError("query must contain five or six events")
    if family == "S":
        return tuple(0 if a < b else 1 if a == b else 2 for a, b in zip(raw, raw[1:]))
    edges = sorted(raw["edges"], key=lambda edge: edge[0])
    return tuple(1 if a[2] == b[2] else 2 for a, b in zip(edges, edges[1:]))


def render(family, events):
    if family == "S":
        values = [0]
        for event in events:
            values.append(values[-1] + (1, 0, -1)[event])
        low = min(values)
        return [value - low + 3 for value in values]
    labels = [0]
    for event in events:
        labels.append(labels[-1] ^ (event == 2))
    return {"nodes": len(labels) + 1, "start": 0, "goal": len(labels),
            "edges": [[i, i + 1, label, 1] for i, label in enumerate(labels)]}


def fit(family, demos, symbols):
    fallback = () if family == "S" else None
    best = {}
    exact = {}
    for length in LENGTHS:
        parsed = [(_features(family, d["input"], length), d["output"]) for d in demos]
        labeled = [(hits, _label(family, output, n)) for (n, hits), output in parsed]
        scores = [(sum(hits.get(word, fallback) == output for hits, output in labeled), word)
                  for word in product(symbols, repeat=length)]
        highest = max(score for score, _ in scores)
        best[length] = min(word for score, word in scores if score == highest)
        exact[length] = [word for score, word in scores if score == len(demos)]
    return best, exact


def offer(family, mode, pool, exact, symbols, seed, seen):
    if mode == "fixed":
        offers = {}
        for raw in pool:
            events = query_trace(family, raw)
            if events not in seen:
                offers.setdefault(events, raw)
        return list(offers.values()), len(pool)
    rng = random.Random(seed)
    if mode == "guided":
        queues = [rng.sample(exact[length], min(len(exact[length]), CAP)) for length in LENGTHS]
        proposals = [queue[i] for i in range(CAP) for queue in queues if i < len(queue)]
    else:
        lengths = [rng.choice(LENGTHS) for _ in range(8 * CAP)]
        proposals = [tuple(rng.choice(symbols) for _ in range(length)) for length in lengths]
    unseen = list(dict.fromkeys(p for p in proposals if p not in seen))[:CAP]
    return [render(family, events) for events in unseen], len(proposals)


def merit(family, raw, exact):
    blank = () if family == "S" else None
    support = []
    for length in LENGTHS:
        _, hits = _features(family, raw, length)
        support.append(Counter(hits.get(word, blank) for word in exact[length]))
    a, b = (len(exact[length]) for length in LENGTHS)
    short, long = support
    labels = short.keys() | long.keys()
    worst = max(min(Fraction(short[y], a), Fraction(long[y], b)) for y in labels)
    exclusive = sum(Fraction(short[y], 2*a) if y not in long else Fraction(long[y], 2*b)
                    for y in labels if y not in short or y not in long)
    return worst, exclusive


def solve(raw):
    packet = read_json(raw, WIRE_BYTES)
    require_fields(packet, "family", "mode", "seed", "demos", "pool")
    family, mode = packet["family"], packet["mode"]
    if family not in ("S", "G") or mode not in MODES:
        raise ContractError("unknown family or mode")
    seed = integer(packet["seed"], 0, 2**32 - 1)
    demos = array(packet["demos"], 32, 34)
    pool = array(packet["pool"], 8 if mode == "fixed" else 0, 8 if mode == "fixed" else 0)
    for demo in demos:
        require_fields(demo, "input", "output")
    seen = set()
    for demo in demos:
        n, _ = _features(family, demo["input"], 5)
        if n in LENGTHS:
            seen.add(query_trace(family, demo["input"]))
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    best, exact = fit(family, demos, symbols)
    compatible = [length for length in LENGTHS if exact[length]]
    diagnosis = compatible[0] if len(compatible) == 1 else None
    offers = []
    choice = None
    attempts = 0
    if len(compatible) == 2 and len(demos) < 34:
        proposed, attempts = offer(family, mode, pool, exact, symbols, seed, seen)
        ranking = []
        for i, question in enumerate(proposed):
            worst, exclusive = merit(family, question, exact)
            offers.append({"input": question, "worst": [worst.numerator, worst.denominator],
                           "exclusive": [exclusive.numerator, exclusive.denominator]})
            if worst < 1:
                ranking.append((worst, len(query_trace(family, question)), -exclusive, i))
        if ranking:
            choice = min(ranking)[-1]
    return {"diagnosis": diagnosis, "word": best[diagnosis or 5],
            "compatible": [len(exact[length]) for length in LENGTHS], "offers": offers, "choice": choice,
            "demo_comparisons": sum(len(symbols)**length for length in LENGTHS) * len(demos),
            "candidate_checks": sum(len(exact[length]) for length in LENGTHS) * len(offers),
            "proposal_attempts": attempts}


def main():
    result = solve(sys.stdin.buffer.read(WIRE_BYTES + 1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000 * (usage.ru_utime + usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
