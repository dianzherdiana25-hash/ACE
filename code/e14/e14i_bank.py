"""Build a public bank of ambiguous grammar pairs before scoring."""

import random
from itertools import product

from e13.contract import canonical_json

from .e14g_audit import verify
from .e14g_bank import FAMILIES, LENGTHS, _cover, _fresh, _negative_trace, alphabet, natural_inputs, sha
from .e14g_run import HISTORY, REPO, frozen
from .e14h_route import load_bank, prior_index, read

SEEDS = (142301, 142302, 142303, 142304, 142305)
SLOTS = range(6)


def history_index():
    previous, _, _ = frozen()
    latest, _, _, _ = load_bank()
    historical = prior_index(previous, read(REPO / HISTORY))
    return prior_index(latest, historical)


def diagnostic(family, slot, short, prefix, rng, used):
    long = (prefix, *short)
    verify(long[:5] != short, "the short motif must occur just once in the shared positive")
    witness = (*short, prefix)
    verify(witness != long, "short-only witness must exclude the long motif")
    negatives = _cover(family, 5, (short,))
    verify(len(negatives) <= 31, "negative cover must leave room for a positive demo")

    def neutral(size=6):
        return _negative_trace(family, 5, (short,), size, rng)

    def render(events):
        return [_fresh(family, row, rng, used) for row in events]

    demos = [long, *negatives, *(neutral(10) for _ in range(31 - len(negatives)))]
    base_pool = [long, long, *(neutral() for _ in range(6))]
    witness_slots = rng.sample(range(2, 8), 2)
    with_witness = [witness if i in witness_slots else row for i, row in enumerate(base_pool)]
    order = rng.sample(range(8), 8)
    # The two conditions share six pool inputs, not just matching render distributions.
    without_pool = render(base_pool)
    enriched = render([with_witness[i] for i in witness_slots])
    with_pool = without_pool.copy()
    for i, raw in zip(witness_slots, enriched, strict=True):
        with_pool[i] = raw
    probes = [witness] * 4 + [long] * 2 + [neutral(), neutral()]
    rng.shuffle(probes)
    return {
        "family": family, "slot": slot, "words": [short, long],
        "demos": render(demos), "probes": render(probes),
        "pools": {"witness": [with_pool[i] for i in order],
                  "no_witness": [without_pool[i] for i in order]},
    }


def build():
    used = history_index()
    natural, motif_rng, pair_rng, render_rng = map(random.Random, SEEDS[:4])
    slots = [(f, length, slot) for f in FAMILIES for length in LENGTHS for slot in SLOTS]
    allocated = {(f, length, slot): natural_inputs(f, natural, used[f]) for f, length, slot in slots}
    blocks = []
    for family in FAMILIES:
        symbols = alphabet(family)
        for length in LENGTHS:
            words = motif_rng.sample(list(product(symbols, repeat=length)), len(SLOTS))
            for slot, word in enumerate(words):
                raw = allocated[family, length, slot].copy()
                pool = raw.pop("pool")
                blocks.append({"family": family, "slot": slot, "words": [word],
                               "pools": {"natural": pool}, **raw})
        options = [word for word in product(symbols, repeat=5) if len(set(word)) > 1]
        for slot, short in enumerate(pair_rng.sample(options, len(SLOTS))):
            blocks.append(diagnostic(family, slot, short, pair_rng.choice(symbols), render_rng, used[family]))
    return {"version": 1, "seeds": SEEDS, "blocks": blocks}


def distinct_inputs(block):
    """Count shared condition inputs once within a single block."""
    pools = {canonical_json(raw): raw for pool in block["pools"].values() for raw in pool}
    return [*block["demos"], *block["probes"], *pools.values()]


def raw_digest(bank):
    return sha(canonical_json(bank))
