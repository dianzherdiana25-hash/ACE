"""Fresh counterexample bank with paired in-model and out-of-model worlds."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_bank import FAMILIES, LENGTHS, _fresh, _random_trace, alphabet, sha, windows
from .e14l_bank import inventory as prior_inventory
from .e14l_run import frozen

SEEDS = (142701, 142702, 142703, 142704, 142705)
CONDITIONS = ("natural", "matched", "reachable", "rare")


def inventory():
    used = prior_inventory()
    bank, _, _ = frozen()
    for block in bank["blocks"]:
        for role in ("demos", "probes"):
            used[block["family"]].update(sha(canonical_json(x)) for x in block[role])
    return used


def draw(symbols, length, rng):
    return tuple(rng.choice(symbols) for _ in range(length))


def stress(family, condition, slot, rng, used):
    symbols = alphabet(family)
    sources = [draw(symbols, 9, rng) for _ in range(3)]
    seeded_sixes = set().union(*(windows(x, 6) for x in sources))
    demos = sorted(seeded_sixes) + [draw(symbols, 6, rng) for _ in range(4)]
    demos += [draw(symbols, 5, rng) for _ in range(32-len(demos))]
    observed = {x for x in demos if len(x) == 6}
    if condition == "reachable":
        target = rng.choice(sorted(set().union(*(windows(x, 7) for x in sources))))
    else:
        rare = [w for w in product(symbols, repeat=7) if w[:6] not in observed and w[1:] not in observed]
        target = rng.choice(rare)
    worlds = [{"condition": condition, "word": target}]
    if condition == "reachable":
        length = 5+slot % 2
        excluded = set().union(*(windows(x, length) for x in demos))
        alternative = rng.choice(sorted(set(product(symbols, repeat=length))-excluded))
        worlds.append({"condition": "matched", "word": alternative})
    probes = [target + draw(symbols, 7, rng) for _ in range(4)]
    for _ in range(512):
        if len(probes) == 8:
            break
        events = draw(symbols, 14, rng)
        if target not in windows(events, 7):
            probes.append(events)
    if len(probes) != 8:
        raise ValueError("could not render all negative probes")
    rng.shuffle(demos)
    rng.shuffle(probes)
    return {"family": family, "slot": slot, "worlds": worlds,
            "demos": [_fresh(family, x, rng, used) for x in demos],
            "probes": [_fresh(family, x, rng, used) for x in probes]}


def build():
    used = inventory()
    raw, motifs, fixtures, seeds = map(random.Random, SEEDS[:4])
    natural = []
    for f in FAMILIES:
        for length in LENGTHS:
            for slot in range(6):
                natural.append({"family": f, "length": length, "slot": slot,
                                "demos": [_fresh(f, _random_trace(f, raw), raw, used[f]) for _ in range(32)],
                                "probes": [_fresh(f, draw(alphabet(f), 14, raw), raw, used[f]) for _ in range(8)]})
    for f in FAMILIES:
        for length in LENGTHS:
            words = motifs.sample(list(product(alphabet(f), repeat=length)), 6)
            for b, word in zip((b for b in natural if (b["family"], b["length"]) == (f, length)), words, strict=True):
                b["worlds"] = [{"condition": "natural", "word": word}]
    blocks = natural + [stress(f, c, slot, fixtures, used[f]) for f in FAMILIES
                        for c in ("reachable", "rare") for slot in range(8)]
    for b in blocks:
        b["seed"] = seeds.randrange(2**32)
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}
