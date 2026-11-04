"""Public fixtures and reference implementations on the evaluator side."""

from dataclasses import dataclass

from .contract import Output, canonical_json


@dataclass(frozen=True)
class Probe:
    input: bytes
    expected: Output


@dataclass(frozen=True)
class Fixture:
    fit_request: bytes
    probes: tuple[Probe, ...]


def _symbols_reference(values, rule):
    if rule == "eq":
        return tuple(int(values[i] == values[i - 1]) for i in range(1, len(values)))
    return tuple(int(values[i] > values[i - 1]) for i in range(1, len(values)))


def _graph_reference(value, rule):
    # Bounded relaxation provides a separate reference from heap-based inference.
    distances = {(value["start"], None): 0}
    for _ in range(4 * value["nodes"]):
        updated = distances.copy()
        for start, end, label, cost in value["edges"]:
            for previous in (None, 0, 1, 2, 3):
                known = distances.get((start, previous))
                if known is None or (rule == "different" and previous == label):
                    continue
                state = (end, label)
                if state not in updated or known + cost < updated[state]:
                    updated[state] = known + cost
        if updated == distances:
            break
        distances = updated
    return min((cost for (node, _), cost in distances.items()
                if node == value["goal"]), default=None)


def _graph(nodes, start, goal, edges):
    return {"nodes": nodes, "start": start, "goal": goal, "edges": edges}


def _fixture(family, task_id, source, target, probes, reference, source_rule, target_rule):
    request = canonical_json({
        "version": 1, "family": family, "task_id": task_id, "seed": 13, "fuel": 2_000,
        "source": [{"input": case, "output": reference(case, source_rule)} for case in source],
        "target": [{"input": case, "output": reference(case, target_rule)} for case in target],
    })
    return Fixture(request, tuple(Probe(canonical_json(case), reference(case, target_rule))
                                  for case in probes))


def public_fixtures():
    return (
        _fixture(
            "S", "f394dc9d0e2340e6899dd0fa27cee987",
            [[4, 4, 1, 1]], [[2, 4, 4, 1, 6]],
            [[], [8], [7, 2, 3, 3, 9, 1]],
            _symbols_reference, "eq", "lt",
        ),
        _fixture(
            "G", "d0e5e30aa6794dcbba6823f073aab2b1",
            [_graph(4, 0, 3, [[0, 1, 0, 1], [1, 3, 0, 1]])],
            [_graph(4, 0, 3, [[0, 1, 0, 1], [1, 3, 0, 1],
                              [0, 2, 1, 4], [2, 3, 0, 3]])],
            [_graph(3, 0, 2, [[0, 1, 1, 1], [1, 2, 1, 1]]),
             _graph(1, 0, 0, []),
             _graph(4, 0, 3, [[0, 1, 0, 0], [1, 2, 1, 1],
                              [2, 1, 2, 1], [1, 3, 0, 1]])],
            _graph_reference, "any", "different",
        ),
    )
