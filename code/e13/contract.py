"""Validate the versioned JSON boundary shared by the solver and evaluator."""

import json
import re
from dataclasses import dataclass


class ContractError(ValueError):
    """Input does not conform to the E1.3 development contract."""


@dataclass(frozen=True)
class Edge:
    start: int
    end: int
    label: int
    cost: int


@dataclass(frozen=True)
class Graph:
    nodes: int
    start: int
    goal: int
    edges: tuple[Edge, ...]


Input = tuple[int, ...] | Graph
Output = tuple[int, ...] | int | None
MAX_FUEL = 100_000
MAX_FIT_BYTES = 32_768
MAX_TOKENS = 64


@dataclass(frozen=True)
class Example:
    input: Input
    output: Output


@dataclass(frozen=True)
class FitRequest:
    task_id: str
    family: str
    seed: int
    fuel: int
    source: tuple[Example, ...]
    target: tuple[Example, ...]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key")
        result[key] = value
    return result


def read_json(raw, max_bytes):
    if type(raw) is not bytes or len(raw) > max_bytes:
        raise ContractError("expected bounded JSON bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as error:
        raise ContractError("invalid JSON") from error


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def require_fields(value, *keys):
    if type(value) is not dict or value.keys() != set(keys):
        raise ContractError("unexpected object fields")


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError("integer outside contract")
    return value


def array(value, minimum, maximum):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ContractError("array size outside contract")
    return value


def _tokens(value):
    return tuple(integer(token, 0, 15) for token in array(value, 0, MAX_TOKENS))


def input_value(family, value) -> Input:
    if family == "S":
        return _tokens(value)

    require_fields(value, "nodes", "start", "goal", "edges")
    nodes = integer(value["nodes"], 1, 16)
    edges = []
    for edge in array(value["edges"], 0, 64):
        start, end, label, cost = array(edge, 4, 4)
        edges.append(Edge(integer(start, 0, nodes - 1), integer(end, 0, nodes - 1),
                          integer(label, 0, 3), integer(cost, 0, 15)))
    return Graph(nodes, integer(value["start"], 0, nodes - 1),
                 integer(value["goal"], 0, nodes - 1), tuple(edges))


def _examples(family, values):
    result = []
    for value in array(values, 1, 16):
        require_fields(value, "input", "output")
        output = value["output"]
        if family == "S":
            output = _tokens(output)
        elif output is not None:
            output = integer(output, 0, 960)
        result.append(Example(input_value(family, value["input"]), output))
    return tuple(result)


def parse_fit_request(raw: bytes) -> FitRequest:
    value = read_json(raw, max_bytes=MAX_FIT_BYTES)
    require_fields(value, "version", "task_id", "family", "seed", "fuel", "source", "target")
    integer(value["version"], 1, 1)
    task_id, family = value["task_id"], value["family"]
    if type(task_id) is not str or not re.fullmatch("[0-9a-f]{32}", task_id):
        raise ContractError("expected opaque task ID")
    if family not in ("S", "G"):
        raise ContractError("unknown family")
    return FitRequest(
        task_id, family, integer(value["seed"], 0, 2**32 - 1),
        integer(value["fuel"], 1, MAX_FUEL),
        _examples(family, value["source"]), _examples(family, value["target"]),
    )
