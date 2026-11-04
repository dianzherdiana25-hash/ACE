"""Fresh public inputs for compound coverage experiments."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, _cover, _fresh, _random_trace, alphabet, sha, windows
from .e14j_bank import absent, inventory, nonoverlap
from .e14j_run import frozen

SEEDS = (142501, 142502, 142503, 142504, 142505)
CONDITIONS = ("natural", "packable", "ceiling")
N = 6


def prior_inputs():
    used = inventory()
    previous, _, _ = frozen()
    for b in previous["blocks"]:
        for role in ("demos", "pool", "probes"):
            used[b["family"]].update(sha(canonical_json(x)) for x in b[role])
    return used


def packable(family, rng):
    symbols = alphabet(family)
    for _ in range(512):
        certificate = tuple(rng.choice(symbols) for _ in range(12))
        words = [certificate[i:i+5] for i in (0, 3, 7)]
        if len(set(words)) != 3 or not nonoverlap(words):
            continue
        extensions = {(*word, extra) for word in words for extra in symbols}
        extensions |= {(extra, *word) for word in words for extra in symbols}
        long = sorted(extensions - windows(certificate, 6))
        if long:
            return words, rng.choice(long), certificate
    raise ValueError("could not construct compound certificate")


def diagnostic(family, condition, slot, rng, used):
    symbols = alphabet(family)
    if condition == "packable":
        short, long, certificate = packable(family, rng)
    else:
        short = rng.sample(list(product(symbols, repeat=5)), 9)
        long = (rng.choice(symbols), *short[0])
        certificate = None
    demo_events = _cover(family, 5, tuple(short))
    verify(len(demo_events) <= 32, "cover exhausted demo budget")
    demo_events.extend(absent(family, 10, short, rng) for _ in range(32 - len(demo_events)))
    probes = []
    for prefix in [short[0]] * 4 + [long] * 2:
        for _ in range(512):
            events = prefix + tuple(rng.choice(symbols) for _ in range(14 - len(prefix)))
            if len(prefix) == 6 or long not in windows(events, 6):
                probes.append(events)
                break
        else:
            raise ValueError("could not construct a diagnostic probe")
    probes.extend(absent(family, 14, short, rng) for _ in range(2))
    rng.shuffle(probes)
    return {"family": family, "condition": condition, "slot": slot, "words": [short[0], long],
            "certificate": certificate,
            "demos": [_fresh(family, events, rng, used) for events in demo_events],
            "probes": [_fresh(family, events, rng, used) for events in probes]}


def build():
    used = prior_inputs()
    draw, motifs, fixtures, seeds = map(random.Random, SEEDS[:4])
    natural = []
    for family in FAMILIES:
        for length in LENGTHS:
            for slot in range(N):
                probes = [tuple(draw.choice(alphabet(family)) for _ in range(14)) for _ in range(8)]
                natural.append({"family": family, "condition": "natural", "length": length, "slot": slot,
                                "demos": [_fresh(family, _random_trace(family, draw), draw, used[family])
                                          for _ in range(32)],
                                "probes": [_fresh(family, e, draw, used[family]) for e in probes]})
    for family in FAMILIES:
        for length in LENGTHS:
            words = motifs.sample(list(product(alphabet(family), repeat=length)), N)
            for b, word in zip((b for b in natural if (b["family"], b["length"]) == (family, length)),
                               words, strict=True):
                b["words"] = [word]
    engineered = [diagnostic(family, condition, slot, fixtures, used[family]) for family in FAMILIES
                  for condition in CONDITIONS[1:] for slot in range(N)]
    blocks = natural + engineered
    for b in blocks:
        b["seed"] = seeds.randrange(2**32)
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}
