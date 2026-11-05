"""Cold graph successor consuming at most one inert typed predecessor artifact."""

import re
import resource
import sys
from collections import defaultdict
from itertools import pairwise, product

from e13.contract import ContractError, array, canonical_json, input_value, integer, read_json, require_fields

LENGTHS = (7,8,9)


def graph_features(raw):
    graph = input_value("G",raw)
    by_start = defaultdict(list)
    for edge in graph.edges:
        if edge.start >= edge.end:
            raise ContractError("expected forward edges")
        by_start[edge.start].append(edge)
    stack = [(graph.start, (), 0)]
    table = {}
    completed = 0
    while stack:
        node, labels, cost = stack.pop()
        if node != graph.goal:
            stack.extend((e.end,(*labels,e.label),cost+e.cost) for e in by_start[node])
            if len(stack)>64:
                raise ContractError("graph exploration exceeded cap")
            continue
        completed += 1
        if completed>16:
            raise ContractError("graph path budget exceeded")
        events = tuple(1 if a == b else 2 for a,b in pairwise(labels))
        for length in LENGTHS:
            for i in range(len(events)-length+1):
                word = events[i:i+length]
                table[word] = min(cost,table.get(word,cost))
    return table


def word_of(artifact):
    require_fields(artifact,"kind","word","source_sha256")
    if (artifact["kind"] != "edge-relative-word-v1" or type(artifact["source_sha256"]) is not str
            or not re.fullmatch("[0-9a-f]{64}",artifact["source_sha256"])):
        raise ContractError("invalid typed inheritance artifact")
    return tuple(integer(x,1,2) for x in array(artifact["word"],7,9))


def solve(raw):
    packet = read_json(raw,65_536)
    require_fields(packet,"demos","artifact")
    records = []
    for entry in array(packet["demos"],4,5):
        require_fields(entry,"input","output")
        output = entry["output"]
        if output is not None:
            output = integer(output,0,960)
        records.append((graph_features(entry["input"]),output))
    word = None if packet["artifact"] is None else word_of(packet["artifact"])
    used = word is not None and all(features.get(word)==gold for features,gold in records)
    if used:
        selected = [word]
        cost = 1
    else:
        selected = [candidate for length in LENGTHS for candidate in product((1,2),repeat=length)
                    if all(features.get(candidate)==gold for features,gold in records)]
        cost = sum(2**length for length in LENGTHS) + int(word is not None)
    return {"selected":selected,"artifact_used":used,"candidate_fits":cost}


def main():
    result = solve(sys.stdin.buffer.read(65_537))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result.update(cpu_us=round(1_000_000*(usage.ru_utime+usage.ru_stime)),rss_kib=usage.ru_maxrss)
    sys.stdout.buffer.write(canonical_json(result))
