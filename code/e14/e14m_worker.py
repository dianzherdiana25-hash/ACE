"""Bounded active falsification from observed negative windows."""

import random
import resource
import sys
from collections import Counter, defaultdict
from fractions import Fraction

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14g_worker import WIRE_BYTES, _features
from .e14j_worker import LENGTHS, fit, merit, render
from .e14k_worker import events_of

MODES = ("adjudicate", "random", "falsify")
QUERY_LENGTH = 9
CAP = 8
LABEL_CAP = 4


def windows(events, length):
    return {events[i:i+length] for i in range(len(events)-length+1)}


def blank_windows(family, demos, length):
    out = set()
    for row in demos:
        label = row["output"]
        is_blank = not any(label) if family == "S" else label is None
        if is_blank:
            out.update(windows(events_of(family, row["input"]), length))
    return out


def negative_paths(sixes):
    successors = defaultdict(list)
    for word in sorted(sixes):
        successors[word[:-1]].append(word[-1])
    paths = sorted(sixes)
    for _ in range(QUERY_LENGTH-6):
        paths = [(*path, event) for path in paths for event in successors.get(path[-5:], ())]
    return paths


def offer(family, mode, demos, exact, symbols, seed):
    rng = random.Random(seed)
    seen = {events_of(family, d["input"]) for d in demos}
    past = blank_windows(family, demos, 7)
    if mode == "random":
        stream = [tuple(rng.choice(symbols) for _ in range(QUERY_LENGTH)) for _ in range(64)]
        return list(dict.fromkeys(q for q in stream if q not in seen))[:CAP], len(stream), past
    words = exact[5]+exact[6]
    guided = [word + tuple(rng.choice(symbols) for _ in range(QUERY_LENGTH-len(word)))
              for word in rng.choices(words, k=24)]
    guided = list(dict.fromkeys(q for q in guided if q not in seen))[:CAP//2]
    paths = negative_paths(blank_windows(family, demos, 6))
    rng.shuffle(paths)
    attempts = 24+len(paths)
    fresh_paths = sorted((q for q in paths if q not in seen and windows(q, 7)-past),
                         key=lambda q: -len(windows(q, 7)-past))
    return guided + [q for q in fresh_paths if q not in guided][:CAP//2], attempts, past


def characterize(family, raw, exact):
    blank = () if family == "S" else None
    counts = Counter()
    for length in LENGTHS:
        _, hits = _features(family, raw, length)
        counts.update(hits.get(word, blank) for word in exact[length])
    blank_consensus = set(counts) == {blank}
    if all(exact.values()):
        worst = merit(family, raw, exact)[0]
    else:
        worst = Fraction(max(counts.values()), sum(counts.values()))
    return blank_consensus, worst


def select(mode, offers):
    if mode == "random":
        return 0 if offers else None
    scores = []
    for i, q in enumerate(offers):
        worst = Fraction(*q["worst"])
        if mode == "adjudicate" and worst < 1:
            scores.append((worst, i))
        elif mode == "falsify" and q["blank_consensus"] and q["novel_sevens"]:
            scores.append((-q["novel_sevens"], i))
    return min(scores)[-1] if scores else None


def solve(raw):
    packet = read_json(raw, WIRE_BYTES)
    require_fields(packet, "family", "mode", "seed", "demos")
    family, mode = packet["family"], packet["mode"]
    if family not in ("S", "G") or mode not in MODES:
        raise ContractError("unknown family or policy")
    demos = array(packet["demos"], 32, 32+LABEL_CAP)
    seed = integer(packet["seed"], 0, 2**32-1)
    for row in demos:
        require_fields(row, "input", "output")
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    _, exact = fit(family, demos, symbols)
    offers, attempts = [], 0
    if any(exact.values()) and len(demos) < 32+LABEL_CAP:
        proposed, attempts, past = offer(family, mode, demos, exact, symbols, seed)
        for events in proposed:
            query = render(family, events)
            consensus, worst = characterize(family, query, exact)
            offers.append({"input": query, "blank_consensus": consensus, "novel_sevens": len(windows(events, 7)-past),
                           "worst": [worst.numerator, worst.denominator]})
    return {"exact_classes": [exact[l] for l in LENGTHS], "offers": offers, "choice": select(mode, offers),
            "proposal_attempts": attempts, "candidate_checks": len(offers)*sum(map(len, exact.values())),
            "demo_comparisons": len(demos)*sum(len(symbols)**l for l in LENGTHS)}


def main():
    result = solve(sys.stdin.buffer.read(WIRE_BYTES+1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000*(usage.ru_utime+usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
