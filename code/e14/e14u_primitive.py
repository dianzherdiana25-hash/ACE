"""E1.4u development: typed, graph-global two-path conjunction primitive.

A path-local contiguous motif sees each route independently.  A branch-pair
primitive requires TWO DISTINCT root-to-goal paths, one matching each motif.
This is a deliberately bounded new DSL constructor, not open-ended invention.
No sealed or hidden targets are imported by this module.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations, product

from .e14_integrated_graph import graph_routes
from .e14_shared_budget import BudgetContractError

ALPHABET = (1, 2)
PAIR_LENGTH = 3
BASE_LENGTHS = (3, 4, 5)
PAIR_WORDS = tuple(product(ALPHABET, repeat=PAIR_LENGTH))
PAIR_SPACE = tuple(combinations(PAIR_WORDS, 2))
SINGLE_SPACE = tuple(word for n in BASE_LENGTHS for word in product(ALPHABET, repeat=n))


def _word(value, *, exact=None):
    if type(value) not in (list, tuple) or len(value) not in BASE_LENGTHS:
        raise BudgetContractError("invalid motif length")
    if exact is not None and len(value) != exact:
        raise BudgetContractError("unexpected motif length")
    if any(type(e) is not int or e not in ALPHABET for e in value):
        raise BudgetContractError("invalid motif symbols")
    return tuple(value)


def program(kind, words):
    if kind == "single-path":
        if type(words) not in (list, tuple) or len(words) != 1:
            raise BudgetContractError("single-path arity")
        return (kind, (_word(words[0]),))
    if kind == "branch-pair":
        if type(words) not in (list, tuple) or len(words) != 2:
            raise BudgetContractError("branch-pair arity")
        a, b = (_word(w, exact=PAIR_LENGTH) for w in words)
        if a == b:
            raise BudgetContractError("pair requires distinct motifs")
        return (kind, tuple(sorted((a, b))))
    raise BudgetContractError("unknown representation constructor")


def _matches(events, word):
    return any(events[i:i+len(word)] == word
               for i in range(len(events)-len(word)+1))


def predict(routes, candidate):
    kind, words = candidate
    if kind == "single-path":
        return min((cost for events, cost in routes if _matches(events, words[0])), default=None)
    if kind == "branch-pair":
        a, b = words
        return min((max(ci, cj) for i, (ei, ci) in enumerate(routes)
                    for j, (ej, cj) in enumerate(routes)
                    if i != j and _matches(ei, a) and _matches(ej, b)), default=None)
    raise BudgetContractError("invalid representation constructor")


def oracle(graph, candidate):
    return predict(graph_routes(graph)[0], candidate)


def graph_from_routes(words, tolls=None):
    """Create <=4 distinguishable branches of a forward typed weighted DAG."""
    if type(words) not in (list, tuple) or not 1 <= len(words) <= 4:
        raise BudgetContractError("invalid route count")
    paths = [_word(w) for w in words]
    if len(set(map(len, paths))) != 1:
        raise BudgetContractError("all route depths must match")
    n = len(paths[0])
    if tolls is None:
        tolls = [0] * len(paths)
    if type(tolls) not in (list, tuple) or len(tolls) != len(paths):
        raise BudgetContractError("invalid toll vector")
    if any(type(x) is not int or not 0 <= x <= 14 for x in tolls):
        raise BudgetContractError("invalid toll")
    goal = len(paths)*n + 1
    edges = []
    for branch, (word, toll) in enumerate(zip(paths, tolls, strict=True)):
        intermediate = [1 + branch*n + k for k in range(n)]
        vertices = [0, *intermediate, goal]
        colors = [0]
        for e in word:
            colors.append(colors[-1] ^ int(e == 2))
        for idx, (a, b) in enumerate(zip(vertices, vertices[1:])):
            edges.append([a, b, colors[idx], (1+toll) if idx == n else 1])
    graph = {"nodes": goal+1, "start": 0, "goal": goal, "edges": edges}
    graph_routes(graph)  # independently validate physical graph limits
    return graph


def _evidence(demos):
    if type(demos) is not list or not 1 <= len(demos) <= 8:
        raise BudgetContractError("invalid demonstration count")
    rows = []
    for row in demos:
        if type(row) is not dict or set(row) != {"input", "output"}:
            raise BudgetContractError("invalid demonstration record")
        y = row["output"]
        if y is not None and (type(y) is not int or not 0 <= y <= 960):
            raise BudgetContractError("invalid demonstration label")
        rows.append((graph_routes(row["input"])[0], y))
    return rows


def fit(demos, *, extended=False):
    """Enumerate exact version space: no model selection from held-out probes."""
    records = _evidence(demos)
    space = (tuple(program("branch-pair", p) for p in PAIR_SPACE)
             if extended else tuple(program("single-path", (w,)) for w in SINGLE_SPACE))
    survivors = [c for c in space if all(predict(routes, c) == y for routes, y in records)]
    return {"grammar": "branch-pair" if extended else "single-path",
            "candidates": survivors, "candidate_fits": len(space)}


def diagnose(demos):
    original = fit(demos)
    if original["candidates"]:
        return {"trigger": False, "status": "single-consistent", "base": original,
                "extended": None}
    extended = fit(demos, extended=True)
    return {"trigger": True, "status": "pair-consistent" if extended["candidates"]
            else "unresolved", "base": original, "extended": extended}


def query_pool():
    """Public fixed pool; all 4-route graphs comply with 16-edge cap."""
    offers = []
    for idx, words in enumerate(combinations(PAIR_WORDS, 4)):
        tolls = (0, 2, 5, 9) if idx % 2 == 0 else (9, 5, 2, 0)
        offers.append(graph_from_routes(words, tolls))
    return tuple(offers)


def select_query(candidates, purchased, *, mode="active", seed=0):
    """One-policy step, deterministic and oracle-blind; no truth access."""
    if type(candidates) is not list or not candidates:
        return None
    if mode not in ("active", "fixed", "random"):
        raise BudgetContractError("unknown query design mode")
    if type(seed) is not int or seed < 0:
        raise BudgetContractError("invalid selector seed")
    known = {tuple(sorted(map(tuple, g["edges"]))) for g in purchased}
    feasible = []
    for graph in query_pool():
        identity = tuple(sorted(map(tuple, graph["edges"])))
        if identity in known:
            continue
        predicted = [oracle(graph, c) for c in candidates]
        parts = Counter(predicted)
        if len(parts) < 2:
            continue
        feasible.append((graph, parts))
    if not feasible:
        return None
    if mode == "fixed":
        return feasible[0][0]
    if mode == "random":
        return feasible[seed % len(feasible)][0]
    return min(feasible, key=lambda x: (sum(n*n for n in x[1].values()),
                                        max(x[1].values()),
                                        len(x[0]["edges"]),
                                        x[0]["edges"]))[0]


def guarded_predict(candidates, graph):
    if type(candidates) is not list or not candidates:
        return {"covered": False, "prediction": None}
    routes = graph_routes(graph)[0]
    outputs = {predict(routes, c) for c in candidates}
    return {"covered": len(outputs) == 1,
            "prediction": next(iter(outputs)) if len(outputs) == 1 else None}
