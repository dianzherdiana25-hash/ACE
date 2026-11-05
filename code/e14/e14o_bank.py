"""New public bank for joint active falsification and recovery."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_bank import FAMILIES, LENGTHS, _fresh, alphabet, sha, windows
from .e14m_bank import draw
from .e14n_bank import inventory as prior_inventory, probe_shapes
from .e14n_run import frozen

SEEDS = (143101, 143102, 143103, 143104, 143105)
CONDITIONS = ("natural", "matched", "reachable", "rare")


def inventory():
    used = prior_inventory()
    bank, _, _ = frozen()
    for block in bank["blocks"]:
        for role in ("demos", "observations", "probes"):
            used[block["family"]].update(sha(canonical_json(x)) for x in block[role])
    return used


def clustered(symbols, length, rng):
    result = [rng.choice(symbols)]
    for _ in range(length-1):
        result.append(result[-1] if rng.randrange(4) == 0 else rng.choice(symbols))
    return tuple(result)


def stress(family, condition, slot, rng, used):
    symbols = alphabet(family)
    length = 7+slot % 3
    sources = [clustered(symbols, 9, rng) for _ in range(3)]
    observed = set().union(*(windows(x, 6) for x in sources))
    demos = sorted(observed) + [draw(symbols, 5, rng) for _ in range(32-len(observed))]
    if condition == "reachable":
        target = rng.choice(sorted(set().union(*(windows(x, length) for x in sources))))
    else:
        for _ in range(512):
            target = draw(symbols, length, rng)
            if not windows(target, 6) & observed:
                break
        else:
            raise ValueError("no rare target")
    worlds = [{"condition": condition, "word": target}]
    if condition == "reachable" and slot < 4:
        size = 5+slot % 2
        excluded = set().union(*(windows(x, size) for x in demos))
        matched = rng.choice(sorted(set(product(symbols, repeat=size))-excluded))
        worlds.append({"condition": "matched", "word": matched})
    return {"family": family, "slot": slot, "worlds": worlds,
            "demos": [_fresh(family, x, rng, used) for x in demos],
            "probes": [_fresh(family, x, rng, used) for x in probe_shapes(symbols, target, rng)]}


def build():
    used = inventory()
    raw, fixtures, motifs, seeds = map(random.Random, SEEDS[:4])
    blocks = []
    for f in FAMILIES:
        symbols = alphabet(f)
        for l in LENGTHS:
            for slot in range(4):
                demos = [_fresh(f, clustered(symbols, raw.randint(9, 14), raw), raw, used[f]) for _ in range(32)]
                probes = [_fresh(f, clustered(symbols, 14, raw), raw, used[f]) for _ in range(8)]
                blocks.append({"family": f, "slot": slot, "demos": demos, "probes": probes,
                               "worlds": [{"condition": "natural", "word": draw(symbols, l, motifs)}]})
        blocks.extend(stress(f, c, slot, fixtures, used[f]) for c, n in (("reachable", 9), ("rare", 3))
                      for slot in range(n))
    for block in blocks:
        block["seed"] = seeds.randrange(2**32)
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}
