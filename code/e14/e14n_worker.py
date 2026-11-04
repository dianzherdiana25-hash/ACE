"""Propose bounded, typed contiguous-word expansions after contradiction."""

import resource
import sys
from itertools import product
from time import process_time_ns

from e13.contract import ContractError, array, canonical_json, read_json, require_fields

from .e14g_worker import WIRE_BYTES, _features, _label
from .e14j_worker import LENGTHS, fit

MODES = ("hold", "fixed7", "enumerate", "directed")
EXPANSION_LENGTHS = (7, 8, 9)
LABEL_CAP = 4
CANDIDATE_CAP = 30_000


def nonblank(family, label):
    return any(label) if family == "S" else label is not None


def contexts(family, demos, anchor):
    return {length: [(_features(family, row["input"], length), row["output"])
                     for row in (demos[anchor], *demos[:anchor], *demos[anchor+1:])]
            for length in EXPANSION_LENGTHS}


def search(family, mode, features, symbols):
    start = process_time_ns()
    blank = () if family == "S" else None
    groups, attempted, compared, anchor_checks = [], 0, 0, 0
    for length, rows in features.items():
        labeled = [(hits, _label(family, y, count)) for (count, hits), y in rows]
        if mode == "fixed7" and length != 7:
            candidates = ()
        elif mode == "directed":
            hits, y = labeled[0]
            candidates = sorted(word for word, predicted in hits.items() if predicted == y)
            anchor_checks += len(hits)
        else:
            candidates = product(symbols, repeat=length)
        accepted = []
        for word in candidates:
            attempted += 1
            if attempted > CANDIDATE_CAP:
                raise ContractError("fixed expansion exceeded candidate cap")
            for hits, expected in labeled:
                compared += 1
                if hits.get(word, blank) != expected:
                    break
            else:
                accepted.append(word)
        groups.append(accepted)
    return {"classes": groups, "attempted": attempted, "comparisons": compared, "anchor_checks": anchor_checks,
            "cpu_us": (process_time_ns()-start)//1000}


def solve(raw):
    packet = read_json(raw, WIRE_BYTES)
    require_fields(packet, "family", "demos")
    family = packet["family"]
    if family not in ("S", "G"):
        raise ContractError("unknown family")
    demos = array(packet["demos"], 32, 32+LABEL_CAP)
    for row in demos:
        require_fields(row, "input", "output")
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    _, old = fit(family, demos, symbols)
    base = [old[l] for l in LENGTHS]
    anchor = None
    expansions = {}
    if not any(base):
        anchor = next((i for i, row in enumerate(demos) if nonblank(family, row["output"])), None)
        if anchor is not None:
            features = contexts(family, demos, anchor)
            expansions = {mode: search(family, mode, features, symbols) for mode in MODES if mode != "hold"}
    return {"base": base, "anchor": anchor, "expansions": expansions,
            "base_comparisons": len(demos)*sum(len(symbols)**l for l in LENGTHS)}


def main():
    result = solve(sys.stdin.buffer.read(WIRE_BYTES+1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000*(usage.ru_utime+usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
