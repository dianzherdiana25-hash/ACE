"""Fresh public ranking and model-misspecification worlds."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_bank import FAMILIES, LENGTHS, _fresh, _random_trace, alphabet, sha, windows
from .e14k_bank import diagnostic, prior_inputs
from .e14k_run import frozen

SEEDS = (142601, 142602, 142603, 142604, 142605)
CONDITIONS = ("natural", "packable", "ceiling", "outside")


def inventory():
    used = prior_inputs()
    bank, _, _ = frozen()
    for block in bank["blocks"]:
        for role in ("demos", "probes"):
            used[block["family"]].update(sha(canonical_json(x)) for x in block[role])
    return used


def outside(family, slot, rng, used):
    symbols = alphabet(family)
    motif = tuple(rng.choice(symbols) for _ in range(7))
    positive = motif + tuple(rng.choice(symbols) for _ in range(7))
    cover = sorted(windows(positive, 5) | windows(positive, 6))
    demos = cover + [tuple(rng.choice(symbols) for _ in range(6)) for _ in range(32-len(cover))]
    probes = [positive] * 4
    for _ in range(512):
        if len(probes) == 8:
            break
        sample = tuple(rng.choice(symbols) for _ in range(14))
        if motif not in windows(sample, 7):
            probes.append(sample)
    if len(probes) != 8:
        raise ValueError("could not render all out-of-model probes")
    rng.shuffle(probes)
    return {"family": family, "condition": "outside", "slot": slot, "words": [motif],
            "demos": [_fresh(family, x, rng, used) for x in demos],
            "probes": [_fresh(family, x, rng, used) for x in probes]}


def build():
    used = inventory()
    draw, motifs, fixtures, seeds = map(random.Random, SEEDS[:4])
    natural = []
    for family in FAMILIES:
        for length in LENGTHS:
            for slot in range(6):
                symbols = alphabet(family)
                natural.append({"family": family, "condition": "natural", "length": length, "slot": slot,
                                "demos": [_fresh(family, _random_trace(family, draw), draw, used[family])
                                          for _ in range(32)],
                                "probes": [_fresh(family, tuple(draw.choice(symbols) for _ in range(14)),
                                                  draw, used[family]) for _ in range(8)]})
    for family in FAMILIES:
        for length in LENGTHS:
            words = motifs.sample(list(product(alphabet(family), repeat=length)), 6)
            for block, word in zip((b for b in natural if (b["family"], b["length"]) == (family, length)),
                                   words, strict=True):
                block["words"] = [word]
    engineered = [diagnostic(family, condition, slot, fixtures, used[family]) for family in FAMILIES
                  for condition in ("packable", "ceiling") for slot in range(5)]
    shifted = [outside(f, i, fixtures, used[f]) for f in FAMILIES for i in range(4)]
    blocks = natural + engineered + shifted
    for block in blocks:
        block["seed"] = seeds.randrange(2**32)
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}
