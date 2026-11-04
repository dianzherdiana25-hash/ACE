"""Exact candidate fit and shared query ranking without evaluator access."""

import resource
import sys
from fractions import Fraction

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14g_worker import WIRE_BYTES
from .e14j_worker import LENGTHS, fit, merit
from .e14k_worker import events_of, propose

MODES = ("minimax", "value", "gate")
CAP = 8
LABEL_COST = 6
FLOOR = Fraction(1, 36)


def proposals(family, exact, symbols, seed, seen):
    short, a = propose(family, "short", exact, symbols, seed, seen)
    long, b = propose(family, "compound", exact, symbols, seed, seen)
    return short[:CAP//2] + long[:CAP//2], a+b


def select(mode, offers):
    ranking = []
    for i, (worst, exclusive, length) in enumerate(offers):
        if worst == 1:
            continue
        utility = exclusive / (LABEL_COST + length)
        if mode == "gate" and utility < FLOOR:
            continue
        if mode == "minimax":
            ranking.append((worst, length, -exclusive, i))
        else:
            ranking.append((-utility, worst, length, i))
    return min(ranking)[-1] if ranking else None


def solve(raw):
    packet = read_json(raw, WIRE_BYTES)
    require_fields(packet, "family", "mode", "seed", "demos")
    family, mode = packet["family"], packet["mode"]
    if family not in ("S", "G") or mode not in MODES:
        raise ContractError("unknown family or mode")
    seed = integer(packet["seed"], 0, 2**32-1)
    demos = array(packet["demos"], 32, 34)
    for row in demos:
        require_fields(row, "input", "output")
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    best, exact = fit(family, demos, symbols)
    live = [length for length in LENGTHS if exact[length]]
    diagnosis = live[0] if len(live) == 1 else None
    offered, attempts, merits = [], 0, []
    if len(live) == 2 and len(demos) < 34:
        seen = {events_of(family, row["input"]) for row in demos}
        offered, attempts = proposals(family, exact, symbols, seed, seen)
        merits = [(*merit(family, q, exact), len(events_of(family, q))) for q in offered]
    return {
        "diagnosis": diagnosis, "word": best[diagnosis or 5],
        "exact_classes": [exact[length] for length in LENGTHS],
        "offers": [{"input": q, "worst": [w.numerator, w.denominator],
                    "exclusive": [e.numerator, e.denominator]}
                   for q, (w, e, _) in zip(offered, merits, strict=True)],
        "choice": select(mode, merits), "proposal_attempts": attempts,
        "demo_comparisons": sum(len(symbols)**length for length in LENGTHS)*len(demos),
        "candidate_checks": len(offered)*sum(map(len, exact.values())),
    }


def main():
    result = solve(sys.stdin.buffer.read(WIRE_BYTES+1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000*(usage.ru_utime+usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
