"""Qualify a positive graph receipt against all shorter compatible motifs."""

import resource
import sys

from e13.contract import ContractError, array, canonical_json, integer, read_json, require_fields

from .e14p_worker import word_of
from .e14r_worker import mappings, witness

MODES = ("receipt", "fixed", "active")
MIN_LENGTH = 5


def chain(word):
    color = 0
    edges = [[0, 1, color, 1]]
    for i, event in enumerate(word, 1):
        color ^= event == 2
        edges.append([i, i + 1, color, 1])
    return {"nodes": len(word) + 2, "start": 0, "goal": len(word) + 1, "edges": edges}


def subwords(word, length_limit):
    return {word[i:i + n] for n in range(MIN_LENGTH, length_limit)
            for i in range(len(word) - n + 1)}


def decide(word, mode, budget, labels):
    if not labels:
        return {"action": "query", "graph": witness(mappings(word))}
    candidates = mappings(word)
    costs = [len(word) + 1 + 4 * i for i in range(len(candidates))]
    if labels[0] not in costs or any(y is not None for y in labels[1:]):
        return {"action": "abstain"}
    index = costs.index(labels[0])
    candidate = candidates[index]
    if mode == "receipt":
        return {"action": "accept", "word": list(candidate)}

    aliases = subwords(candidate, len(candidate))
    for earlier in candidates[:index]:
        aliases.difference_update(subwords(earlier, len(candidate)))
    options = (candidate[:-1], candidate[1:])
    remaining = aliases
    for i in range(1, len(labels) + 1):
        if not remaining:
            return {"action": "accept", "word": list(candidate)}
        if i == budget:
            break
        hits = [remaining & subwords(option, len(candidate)) for option in options]
        relevant = [j for j, hit in enumerate(hits) if hit]
        if not relevant:
            break
        chosen = max(relevant, key=lambda j: len(hits[j])) if mode == "active" else relevant[0]
        if i == len(labels):
            return {"action": "query", "graph": chain(options[chosen])}
        remaining = remaining - hits[chosen]
    return {"action": "abstain"}


def solve(packet):
    require_fields(packet, "artifact", "mode", "budget", "labels")
    word = word_of(packet["artifact"])
    mode = packet["mode"]
    if mode not in MODES:
        raise ContractError("unknown qualification strategy")
    budget = integer(packet["budget"], 1, 3)
    labels = [integer(y, 1, 960) if y is not None else None
              for y in array(packet["labels"], 0, budget)]
    return decide(word, mode, budget, labels)


def main():
    result = solve(read_json(sys.stdin.buffer.read(65_537), 65_536))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_us=round(1_000_000 * (usage.ru_utime + usage.ru_stime)), rss_kib=usage.ru_maxrss)
    sys.stdout.buffer.write(canonical_json(result))
