"""Construct and interpret a single diagnostic receipt for a typed artifact."""

import resource
import sys

from e13.contract import ContractError, canonical_json, integer, read_json, require_fields

from .e14p_worker import graph_features, word_of

MODES = ("passive", "chain", "packed")


def mappings(word):
    return word, (*word[:-1], 3 - word[-1]), (*word[:-2], 3 - word[-2], word[-1])


def witness(words):
    """Use three tail edges per route after the shared prefix."""
    head_edges = len(words[0]) - 2
    goal = head_edges + 2 * len(words) + 1
    edges = []
    for branch, word in enumerate(words):
        colors = [0]
        for event in word:
            colors.append(colors[-1] ^ (event == 2))
        if branch == 0:
            edges.extend([i, i + 1, colors[i], 1] for i in range(head_edges))
        a = head_edges + 1 + 2 * branch
        edges.extend([
            [head_edges, a, colors[head_edges], 1],
            [a, a + 1, colors[head_edges + 1], 1],
            [a + 1, goal, colors[head_edges + 2], 1 + 4 * branch],
        ])
    return {"nodes": goal + 1, "start": 0, "goal": goal, "edges": edges}


def solve(packet):
    require_fields(packet, "artifact", "mode", "observed", "label")
    word = word_of(packet["artifact"])
    mode = packet["mode"]
    if mode not in MODES or type(packet["observed"]) is not bool:
        raise ContractError("invalid calibration packet")
    label = packet["label"]
    if label is not None:
        integer(label, 1, 960)
    if mode == "passive":
        return {"graph": None, "selected": [word] if packet["observed"] and label is None else []}
    candidates = mappings(word)
    graph = witness(candidates if mode == "packed" else candidates[:1])
    selected = []
    if packet["observed"] and label is not None:
        features = graph_features(graph)
        selected = [candidate for candidate in candidates if features.get(candidate) == label]
    return {"graph": graph, "selected": selected if len(selected) == 1 else []}


def main():
    result = solve(read_json(sys.stdin.buffer.read(65_537), 65_536))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_us=round(1_000_000 * (usage.ru_utime + usage.ru_stime)), rss_kib=usage.ru_maxrss)
    sys.stdout.buffer.write(canonical_json(result))
