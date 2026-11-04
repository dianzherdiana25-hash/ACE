"""Sandbox-only finite pattern learner. The wire never includes evaluation labels."""

import resource
import sys
from collections import Counter, defaultdict
from itertools import pairwise, product

from e13.contract import (
    ContractError, array, canonical_json, input_value, integer, read_json, require_fields,
)

WIRE_BYTES = 65_536


def _features(family, raw, length):
    value = input_value(family, raw)
    if family == "S":
        events = tuple(0 if a < b else 1 if a == b else 2 for a, b in pairwise(value))
        hits = defaultdict(list)
        for end in range(length, len(events) + 1):
            hits[events[end - length:end]].append(end - 1)
        return len(events), {word: tuple(places) for word, places in hits.items()}

    edges = sorted(value.edges, key=lambda edge: edge.start)
    if (not edges or len(edges) + 1 != value.nodes or value.start != 0
            or value.goal != len(edges)
            or any((edge.start, edge.end) != (i, i + 1) for i, edge in enumerate(edges))):
        raise ContractError("E1.4g graph must be a single forward chain")
    events = tuple(1 if a.label == b.label else 2 for a, b in pairwise(edges))
    cost = sum(edge.cost for edge in edges)
    return len(events), {events[i:i + length]: cost for i in range(len(events) - length + 1)}


def _label(family, value, count):
    if family == "S":
        return tuple(i for i, bit in enumerate(array(value, count, count)) if integer(bit, 0, 1))
    return None if value is None else integer(value, 0, 240)


def solve(raw, length):
    request = read_json(raw, WIRE_BYTES)
    require_fields(request, "family", "operation", "demos", "inputs")
    family, operation = request["family"], request["operation"]
    if family not in ("S", "G") or operation not in ("select", "predict") or length not in (5, 6):
        raise ContractError("invalid worker request")
    demos = []
    for demo in array(request["demos"], 32, 33):
        require_fields(demo, "input", "output")
        count, hits = _features(family, demo["input"], length)
        demos.append((hits, _label(family, demo["output"], count)))
    inputs = [_features(family, raw_input, length) for raw_input in array(request["inputs"], 8, 8)]
    default = () if family == "S" else None
    words = tuple(product((0, 1, 2) if family == "S" else (1, 2), repeat=length))
    scores = [sum(hits.get(word, default) == target for hits, target in demos) for word in words]
    matches = max(scores)
    candidates = tuple(word for word, score in zip(words, scores, strict=True) if score == matches)
    result = {"candidates": len(candidates), "fit_matches": matches,
              "fit_comparisons": len(words) * len(demos)}
    if operation == "select":
        if len(demos) != 32:
            raise ContractError("selection occurs before acquiring a label")
        result["partitions"] = [sorted(Counter(hits.get(word, default) for word in candidates).values())
                                for _, hits in inputs]
        result["prediction_calls"] = len(inputs) * len(candidates)
    else:
        chosen = candidates[0]
        result["word"] = chosen
        predictions = [hits.get(chosen, default) for _, hits in inputs]
        if family == "S":
            predictions = [[int(i in places) for i in range(count)]
                           for (count, _), places in zip(inputs, predictions, strict=True)]
        result["predictions"] = predictions
        result["prediction_calls"] = len(inputs)
    return result


def main(length):
    result = solve(sys.stdin.buffer.read(WIRE_BYTES + 1), length)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result["cpu_us"] = round(1_000_000 * (usage.ru_utime + usage.ru_stime))
    result["rss_kib"] = usage.ru_maxrss
    sys.stdout.buffer.write(canonical_json(result))
