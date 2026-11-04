"""Fresh examples for a conditional typed expansion experiment."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_bank import FAMILIES, LENGTHS, _fresh, _random_trace, alphabet, sha, windows
from .e14m_bank import draw, inventory as prior_inventory
from .e14m_run import frozen

SEEDS = (142801, 142802, 142803, 142804)
CONDITIONS = ("natural", "matched", "repair", "ambiguous", "no_trigger", "outside")


def inventory():
    used = prior_inventory()
    bank, _, _ = frozen()
    for block in bank["blocks"]:
        for role in ("demos", "probes"):
            used[block["family"]].update(sha(canonical_json(x)) for x in block[role])
    return used


def probe_shapes(symbols, word, rng):
    positive = [draw(symbols, offset, rng) + word + draw(symbols, 14-len(word)-offset, rng)
                for offset in range(4)]
    negative = []
    for i in range(4):
        partial = word[:-1] if i % 2 == 0 else word[1:]
        for _ in range(512):
            candidate = draw(symbols, i, rng) + partial + draw(symbols, 14-len(partial)-i, rng)
            if word not in windows(candidate, len(word)):
                negative.append(candidate)
                break
        else:
            raise ValueError("could not render a hard negative")
    probes = positive + negative
    rng.shuffle(probes)
    return probes


def stress(family, condition, slot, rng, used):
    symbols = alphabet(family)
    length = {"repair": 7+slot % 3, "ambiguous": 7+slot, "no_trigger": 8+slot % 2, "outside": 10}[condition]
    for _ in range(512):
        word = draw(symbols, length, rng)
        if word[:-1] != word[1:]:
            break
    else:
        raise ValueError("could not generate a nonconstant motif")
    offset = 2
    for _ in range(512):
        witness = draw(symbols, offset, rng) + word + draw(symbols, 12-offset-length, rng)
        if sum(witness[i:i+length] == word for i in range(13-length)) == 1:
            break
    else:
        raise ValueError("could not place a single activation in witness")

    width = 9 if condition == "outside" else 6
    demos = sorted(windows(witness, width))
    demos.extend(draw(symbols, 5+(i % 2), rng) for i in range(32-len(demos)))
    worlds = [{"condition": condition, "word": word}]
    if condition == "repair":
        evidence = list(dict.fromkeys(q for q in (witness, word, word[:-1], word[1:]) if q not in demos))
        if slot < 8:
            old_length = 5+slot % 2
            excluded = set().union(*(windows(x, old_length) for x in demos))
            matched = rng.choice(sorted(set(product(symbols, repeat=old_length))-excluded))
            worlds.append({"condition": "matched", "word": matched})
    elif condition == "no_trigger":
        for _ in range(512):
            negative = draw(symbols, 12, rng)
            if word not in windows(negative, length):
                evidence = [negative]
                break
        else:
            raise ValueError("could not generate non-triggering evidence")
    else:
        evidence = [witness]
    return {"family": family, "slot": slot, "worlds": worlds,
            "demos": [_fresh(family, x, rng, used) for x in demos],
            "observations": [_fresh(family, x, rng, used) for x in evidence],
            "probes": [_fresh(family, x, rng, used) for x in probe_shapes(symbols, word, rng)]}


def build():
    used = inventory()
    raw, motifs, fixtures = map(random.Random, SEEDS[:3])
    blocks = []
    for f in FAMILIES:
        for length in LENGTHS:
            cell = [{"family": f, "slot": slot,
                     "demos": [_fresh(f, _random_trace(f, raw), raw, used[f]) for _ in range(32)],
                     "probes": [_fresh(f, draw(alphabet(f), 14, raw), raw, used[f]) for _ in range(8)],
                     "observations": []} for slot in range(4)]
            words = motifs.sample(list(product(alphabet(f), repeat=length)), 4)
            for b, word in zip(cell, words, strict=True):
                b["worlds"] = [{"condition": "natural", "word": word}]
            blocks.extend(cell)
    sizes = {"repair": 9, "ambiguous": 3, "no_trigger": 4, "outside": 4}
    blocks.extend(stress(f, c, i, fixtures, used[f]) for f in FAMILIES
                  for c, n in sizes.items() for i in range(n))
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}
