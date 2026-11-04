"""Public bank with structural one-query, two-query, and out-of-budget strata."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, _cover, _fresh, _random_trace, alphabet, sha, windows
from .e14i_bank import distinct_inputs, history_index
from .e14i_run import frozen

SEEDS = (142401, 142402, 142403, 142404, 142405)
COUNTS = {"natural": 6, "single": 4, "sequence": 4, "beyond": 4}


def inventory():
    used = history_index()
    previous, _, _ = frozen()
    for block in previous["blocks"]:
        used[block["family"]].update(sha(canonical_json(x)) for x in distinct_inputs(block))
    return used


def absent(family, size, excluded, rng):
    symbols = alphabet(family)
    for _ in range(512):
        events = tuple(rng.choice(symbols) for _ in range(size))
        if not set(excluded) & windows(events, 5):
            return events
    raise ValueError("could not sample a neutral trace")


def nonoverlap(words):
    return all(a == b or a[1:] != b[:-1] for a in words for b in words)


def motif_group(family, size, rng):
    options = [word for word in product(alphabet(family), repeat=5) if len(set(word)) > 1]
    for _ in range(512):
        group = rng.sample(options, size)
        if nonoverlap(group):
            return group
    raise ValueError("could not draw nonoverlapping motifs")


def diagnostic(family, condition, slot, rng, used):
    k = {"single": 1, "sequence": 2, "beyond": 3}[condition]
    short = motif_group(family, k, rng)
    long = (rng.choice(alphabet(family)), *short[0])
    demos = ([long] if k == 1 else []) + _cover(family, 5, tuple(short))
    verify(len(demos) <= 32, "negative cover exceeded demo budget")
    demos.extend(absent(family, 10, short, rng) for _ in range(32 - len(demos)))
    pool = [absent(family, rng.choice(LENGTHS), short, rng) for _ in range(8)]
    probes = []
    for prefix in [short[0]] * 4 + [long] * 2:
        for _ in range(512):
            events = prefix + tuple(rng.choice(alphabet(family)) for _ in range(8 - len(prefix)))
            if len(prefix) == 6 or long not in windows(events, 6):
                probes.append(events)
                break
        else:
            raise ValueError("could not sample a short-only probe")
    probes.extend(absent(family, 8, short, rng) for _ in range(2))
    rng.shuffle(probes)
    return {"family": family, "condition": condition, "slot": slot, "words": [short[0], long],
            **{role: [_fresh(family, events, rng, used) for events in values]
               for role, values in (("demos", demos), ("pool", pool), ("probes", probes))}}


def build():
    used = inventory()
    draw, motifs, engineered, seed_rng = map(random.Random, SEEDS[:4])
    blocks = []
    # Draw natural raw inputs before opening the target motif stream.
    for family in FAMILIES:
        for length in LENGTHS:
            for slot in range(COUNTS["natural"]):
                demos, probes = ([_fresh(family, _random_trace(family, draw), draw, used[family])
                                 for _ in range(n)] for n in (32, 8))
                pool = [_fresh(family, absent(family, draw.choice(LENGTHS), (), draw), draw, used[family])
                        for _ in range(8)]
                blocks.append({"family": family, "length": length, "condition": "natural", "slot": slot,
                               "demos": demos, "probes": probes, "pool": pool})
    for family in FAMILIES:
        for length in LENGTHS:
            words = motifs.sample(list(product(alphabet(family), repeat=length)), COUNTS["natural"])
            for block, word in zip((b for b in blocks if (b["family"], b["length"]) == (family, length)),
                                   words, strict=True):
                block["words"] = [word]
    for family in FAMILIES:
        for condition in ("single", "sequence", "beyond"):
            for slot in range(COUNTS[condition]):
                blocks.append(diagnostic(family, condition, slot, engineered, used[family]))
    for block in blocks:
        block["seed"] = seed_rng.randrange(2**32)
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}
