"""Experimental typed motif grammar expansion from observed graph labels.

Unlike the mapped-only control, this enumerates motifs absent from its original
length-7..9 grammar. It is a *bounded predefined extension* to lengths 5 and 6,
NOT arbitrary representation invention or open-ended scientific discovery.
"""
from __future__ import annotations

from itertools import product

from .e14_integrated_graph import graph_routes
from .e14_shared_budget import BudgetContractError

BASE_LENGTHS = (7,8,9)
EXTENDED_LENGTHS = (5,6,7,8,9)
MAX_EXAMPLES = 8
MAX_FITS = sum(2**n for n in EXTENDED_LENGTHS)


def _validate_demos(demos):
    if type(demos) is not list or not 1 <= len(demos) <= MAX_EXAMPLES:
        raise BudgetContractError("invalid graph demonstrations")
    features = []
    for demo in demos:
        if type(demo) is not dict or set(demo) != {"input","output"}:
            raise BudgetContractError("invalid demonstration fields")
        label = demo["output"]
        if label is not None and (type(label) is not int or not 0 <= label <= 960):
            raise BudgetContractError("invalid observed label")
        routes, _ = graph_routes(demo["input"])
        features.append((routes, label))
    return features


def predict(routes, motif):
    target = tuple(motif)
    return min((cost for events,cost in routes
                if any(events[i:i+len(target)] == target
                       for i in range(len(events)-len(target)+1))),default=None)


def version_space(demos, *, extend=False):
    """All exactly consistent motifs, with explicit fit-work accounting."""
    evidence = _validate_demos(demos)
    lengths = EXTENDED_LENGTHS if extend else BASE_LENGTHS
    selected = []
    fits = 0
    for n in lengths:
        for word in product((1,2),repeat=n):
            fits += 1
            if all(predict(routes,word) == label for routes,label in evidence):
                selected.append(word)
    return {"motifs":selected,"candidate_fits":fits,
            "grammar":"extended-5-9" if extend else "base-7-9",
            "new_lengths": [5,6] if extend else []}


def diagnosis(demos):
    base = version_space(demos,extend=False)
    if base["motifs"]:
        return {"trigger":False,"base":base,"extended":None,"status":"base_consistent"}
    expanded = version_space(demos,extend=True)
    return {"trigger":True,"base":base,"extended":expanded,
            "status":"extended_consistent" if expanded["motifs"] else "unresolved"}


def selective_prediction(motifs, graph):
    """Accept a probe prediction only if every surviving motif agrees."""
    if type(motifs) is not list or not motifs:
        return {"covered":False,"prediction":None}
    routes, _ = graph_routes(graph)
    outputs = {predict(routes,m) for m in motifs}
    return {"covered":len(outputs)==1,
            "prediction":next(iter(outputs)) if len(outputs)==1 else None}
