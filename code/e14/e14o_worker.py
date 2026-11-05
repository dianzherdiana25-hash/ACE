"""Isolated typed pipeline for falsification and selective active repair."""

import random
import resource
import sys
from collections import Counter

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14g_worker import WIRE_BYTES, _features
from .e14j_worker import LENGTHS, fit, render
from .e14k_worker import events_of
from .e14m_worker import characterize, offer, select, windows
from .e14n_worker import EXPANSION_LENGTHS, contexts, nonblank, search

MODES = ("active", "passive", "random")
LABEL_CAP = 4
CAP = 8


def recovery_offers(mode, words, symbols, seed, seen):
    if mode == "passive" or len(words) <= 1:
        return []
    rng = random.Random(seed)
    ordered = rng.sample(words, len(words))
    if mode == "random":
        ordered = [tuple(rng.choice(symbols) for _ in range(len(word))) for word in ordered]
    return list(dict.fromkeys(x for x in ordered if x not in seen))[:CAP]


def rank_partition(family, raw, words):
    blank = () if family == "S" else None
    tables = {l: _features(family, raw, l)[1] for l in EXPANSION_LENGTHS}
    groups = Counter(tables[len(w)].get(w, blank) for w in words)
    return sum(n*n for n in groups.values())


def solve(raw):
    packet = read_json(raw, WIRE_BYTES)
    require_fields(packet, "family", "demos", "mode", "seed")
    family, mode = packet["family"], packet["mode"]
    if family not in ("S", "G") or mode not in MODES:
        raise ContractError("invalid family or strategy")
    seed = integer(packet["seed"], 0, 2**32-1)
    known = array(packet["demos"], 32, 32+LABEL_CAP)
    for row in known:
        require_fields(row, "input", "output")
    symbols = (0, 1, 2) if family == "S" else (1, 2)
    _, old = fit(family, known, symbols)
    classes = [old[l] for l in LENGTHS]
    trigger = not any(classes)
    remaining = len(known) < 32+LABEL_CAP
    choices, attempts, checks, anchor_checks = [], 0, 0, 0
    choice = None
    if not trigger and remaining:
        events, attempts, past = offer(family, "falsify", known, old, symbols, seed)
        for q in events:
            raw_input = render(family, q)
            blank, worst = characterize(family, raw_input, old)
            choices.append({"input": raw_input, "blank_consensus": blank, "worst": [worst.numerator, worst.denominator],
                            "novel_sevens": len(windows(q, 7)-past)})
        choice = select("falsify", choices)
    elif trigger:
        anchor = next((i for i, row in enumerate(known) if nonblank(family, row["output"])), None)
        classes = [[], [], []]
        if anchor is not None:
            info = search(family, "directed", contexts(family, known, anchor), symbols)
            classes, checks, anchor_checks = info["classes"], info["attempted"], info["anchor_checks"]
        words = [word for group in classes for word in group]
        if remaining:
            seen = {events_of(family, row["input"]) for row in known}
            questions = recovery_offers(mode, words, symbols, seed, seen)
            attempts = len(questions)
            rendered = [render(family, q) for q in questions]
            choices = [{"input": q, "collision": rank_partition(family, q, words)} for q in rendered]
            if choices:
                if mode == "random":
                    choice = 0
                else:
                    best = min(range(len(choices)), key=lambda i: choices[i]["collision"])
                    choice = best if choices[best]["collision"] < len(words)**2 else None
    return {"classes": classes, "trigger": trigger, "offers": choices, "choice": choice,
            "offer_attempts": attempts, "expansion_fits": checks, "anchor_checks": anchor_checks,
            "model_checks": len(choices)*sum(map(len, classes)),
            "base_comparisons": len(known)*sum(len(symbols)**l for l in LENGTHS)}


def main():
    result = solve(sys.stdin.buffer.read(WIRE_BYTES+1))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000*(usage.ru_utime+usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
