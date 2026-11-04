"""Isolated candidate that packs compatible motifs into bounded queries."""

import random
import resource
import sys
from itertools import pairwise, permutations

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14g_worker import WIRE_BYTES
from .e14j_worker import CAP, LENGTHS, fit, merit, offer, render

MODES = ("short", "random", "compound")
LONG = 12


def events_of(family, raw):
    if family == "S":
        return tuple(0 if a < b else 1 if a == b else 2 for a, b in pairwise(raw))
    edges = sorted(raw["edges"], key=lambda edge: edge[0])
    return tuple(1 if a[2] == b[2] else 2 for a, b in pairwise(edges))


def pack(words, symbols, rng):
    result = ()
    for word in words:
        if any(result[i:i + len(word)] == word for i in range(len(result) - len(word) + 1)):
            continue
        overlap = max((n for n in range(1, min(len(result), len(word)) + 1)
                       if result[-n:] == word[:n]), default=0)
        if len(result) + len(word) - overlap <= LONG:
            result += word[overlap:]
    return result + tuple(rng.choice(symbols) for _ in range(LONG - len(result)))


def propose(family, mode, exact, symbols, seed, seen):
    if mode == "short":
        return offer(family, "guided", [], exact, symbols, seed, seen)
    rng = random.Random(seed)
    if mode == "random":
        stream = [tuple(rng.choice(symbols) for _ in range(LONG)) for _ in range(64)]
    else:
        short, long = (exact[l] for l in LENGTHS)
        small = list(permutations(short)) if len(short) <= 3 else []
        rng.shuffle(small)
        # Put every ordering of a small short class first, then explore both classes.
        orderings = small + [tuple(rng.sample(short, min(len(short), 3))) + (rng.choice(long),)
                             for _ in range(32 - len(small))]
        stream = [pack(words, symbols, rng) for words in orderings]
    unseen = list(dict.fromkeys(events for events in stream if events not in seen))[:CAP]
    return [render(family, events) for events in unseen], len(stream)


def solve(raw):
    packet = read_json(raw, WIRE_BYTES)
    require_fields(packet, "family", "mode", "seed", "demos")
    family, mode = packet["family"], packet["mode"]
    if family not in ("S", "G") or mode not in MODES:
        raise ContractError("unknown family or mode")
    seed = integer(packet["seed"], 0, 2**32 - 1)
    demos = array(packet["demos"], 32, 34)
    for demo in demos:
        require_fields(demo, "input", "output")
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    best, exact = fit(family, demos, symbols)
    compatible = [l for l in LENGTHS if exact[l]]
    diagnosis = compatible[0] if len(compatible) == 1 else None
    offers, ranking, attempts = [], [], 0
    if len(compatible) == 2 and len(demos) < 34:
        seen = {events_of(family, d["input"]) for d in demos}
        proposals, attempts = propose(family, mode, exact, symbols, seed, seen)
        for i, raw_input in enumerate(proposals):
            worst, exclusive = merit(family, raw_input, exact)
            events = events_of(family, raw_input)
            covered = [len({events[j:j+l] for j in range(len(events)-l+1)} & set(exact[l]))
                       for l in LENGTHS]
            offers.append({"input": raw_input, "worst": [worst.numerator, worst.denominator],
                           "exclusive": [exclusive.numerator, exclusive.denominator], "covered": covered})
            if worst < 1:
                ranking.append((worst, len(events), -exclusive, i))
    return {"diagnosis": diagnosis, "word": best[diagnosis or 5],
            "compatible": [len(exact[l]) for l in LENGTHS], "offers": offers,
            "choice": min(ranking)[-1] if ranking else None, "proposal_attempts": attempts,
            "demo_comparisons": sum(len(symbols)**l for l in LENGTHS) * len(demos),
            "candidate_checks": sum(map(len, exact.values())) * len(offers)}


def main():
    result = solve(sys.stdin.buffer.read(WIRE_BYTES + 1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000 * (usage.ru_utime + usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
