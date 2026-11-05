"""Evaluator oracle for minimum motif-constrained cost on a branching graph."""

from collections import defaultdict
from itertools import pairwise


def paths(raw):
    edges = defaultdict(list)
    for a,b,label,cost in raw["edges"]:
        edges[a].append((b,label,cost))

    def walk(node, labels, total):
        if node == raw["goal"]:
            yield tuple(1 if a == b else 2 for a,b in pairwise(labels)), total
            return
        for nxt,label,cost in edges[node]:
            if nxt <= node:
                raise ValueError("graph must be acyclic in vertex order")
            yield from walk(nxt, (*labels,label), total+cost)
    return tuple(walk(raw["start"], (), 0))


def minimum(routes, word):
    length = len(word)
    return min((cost for events,cost in routes if any(events[i:i+length] == word
                                                       for i in range(len(events)-length+1))), default=None)
