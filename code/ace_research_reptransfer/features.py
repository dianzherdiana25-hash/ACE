"""Representation dictionaries: learned state features, unchanged base hand library, and extended C2.

A feature is an object with ``name``, ``apply(s) -> bool``, and ``cost(s) -> int`` (symbols read).
Learned features are extracted from admitted DFAs produced by the unchanged R1 learner.
"""
from __future__ import annotations

import itertools
from typing import Callable, Sequence

from ace_research_primitives import primitive_discovery as r1
from .tasks import ALPHABET, SOURCE_REL, SOURCE_IRR, truth

# Probe set for behaviour deduplication (all 511 strings of length <= 8).
DEDUPE_UNIVERSE = tuple("".join(x) for n in range(9) for x in itertools.product(ALPHABET, repeat=n))


class Feature:
    __slots__ = ("name", "apply", "cost")

    def __init__(self, name: str, apply: Callable[[str], bool], cost: Callable[[str], int] | None = None):
        self.name = name
        self.apply = apply
        self.cost = cost if cost is not None else (lambda s: len(s))

    def fingerprint(self) -> int:
        v = 0
        for i, s in enumerate(DEDUPE_UNIVERSE):
            if self.apply(s):
                v |= 1 << i
        return v


def deduplicate(features: Sequence[Feature]) -> list[Feature]:
    seen, out = set(), []
    for f in features:
        fp = f.fingerprint()
        if fp not in seen:
            seen.add(fp)
            out.append(f)
    return out


def learn_dfa(spec) -> tuple[r1.Automaton, int]:
    """Train R1 on exhaustive strings of length 0-5; assert 100% on validation strings 6-12."""
    tr_words = [s for n in range(6) for s in ("".join(x) for x in itertools.product(ALPHABET, repeat=n))]
    va_words = [s for n in range(6, 13) for s in ("".join(x) for x in itertools.product(ALPHABET, repeat=n))]
    train = [(s, truth(spec, s)) for s in tr_words]
    m, attempts = r1.infer(train)
    for s in va_words:
        if m.run(s) != truth(spec, s):
            raise RuntimeError(f"source admission failed for {spec!r}")
    return m, attempts


def features_from_dfa(name: str, automaton: r1.Automaton) -> list[Feature]:
    """One feature per reachable state q: True iff the DFA halts in state q."""
    m = automaton

    def step(s: str) -> int:
        q = m.find(0)
        for c in s:
            dest = m.edges[q].get(c)
            if dest is None:
                return -1
            q = m.find(dest)
        return q

    # Discover reachable states via full walk over the dedupe universe.
    reachable = sorted({step(s) for s in DEDUPE_UNIVERSE} - {-1})
    features = []
    for q in reachable:
        # State q indicator: True iff reading s halts at canonical state q.
        pred = lambda s, q=q: step(s) == q
        features.append(Feature(f"{name}:state{q}", pred, cost=lambda s: len(s)))
    return features


def learned_dictionary(source_tasks) -> tuple[list[Feature], dict[str, int]]:
    """Build a learned dictionary from a sequence of (name, spec) tasks."""
    features, merge_counts = [], {}
    for name, spec in source_tasks:
        dfa, attempts = learn_dfa(spec)
        merge_counts[name] = attempts
        features.extend(features_from_dfa(name, dfa))
    return deduplicate(features), merge_counts


def base_hand_library() -> list[Feature]:
    """Unchanged repo fixed-predicate library, deduplicated."""
    raw = [Feature(name, pred, cost=lambda s: len(s)) for name, pred in r1.fixed_predicates()]
    return deduplicate(raw)


def extended_hand_library() -> list[Feature]:
    """Base hand library + mod residues for m in 2..6, both symbols, and length mods."""
    feats = list(base_hand_library())
    for letter in ALPHABET:
        for mod in (2, 3, 4, 5, 6):
            for res in range(mod):
                pred = lambda s, letter=letter, mod=mod, res=res: s.count(letter) % mod == res
                feats.append(Feature(f"count:{letter}%{mod}=={res}", pred, cost=lambda s: len(s)))
    for mod in (2, 3, 4, 5, 6):
        for res in range(mod):
            pred = lambda s, mod=mod, res=res: len(s) % mod == res
            feats.append(Feature(f"len%{mod}=={res}", pred, cost=lambda s: len(s)))
    return deduplicate(feats)
