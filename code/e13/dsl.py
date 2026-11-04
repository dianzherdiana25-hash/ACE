"""Interpret a closed set of typed ASTs with a step budget."""

import hashlib
import heapq
import operator
from dataclasses import dataclass

from .contract import (
    MAX_FUEL, ContractError, Graph, Input, Output, canonical_json, input_value,
    integer, read_json, require_fields,
)


class FuelExhausted(RuntimeError):
    """Evaluation stopped at the step limit."""


class Fuel:
    def __init__(self, limit: int):
        self.limit = integer(limit, 1, MAX_FUEL)
        self.used = 0

    def spend(self):
        if self.used >= self.limit:
            raise FuelExhausted("DSL step limit reached")
        self.used += 1


_PREDICATES = {"eq": operator.eq, "lt": operator.lt, "gt": operator.gt}
_TRANSITIONS = {"any": lambda previous, current: True,
                "different": operator.ne, "same": operator.eq}


@dataclass(frozen=True)
class Program:
    family: str
    ast: bytes
    option: str

    @property
    def sha256(self):
        return hashlib.sha256(self.ast).hexdigest()


def compile_ast(raw: bytes) -> Program:
    value = read_json(raw, max_bytes=1024)
    require_fields(value, "family", "ast")
    family, ast = value["family"], value["ast"]
    require_fields(ast, "op", "rule")
    rule = ast["rule"]
    require_fields(rule, "op")
    option = rule["op"]
    if type(option) is not str:
        raise ContractError("expected an operation name")
    if family == "S" and ast["op"] == "pair_flags" and option in _PREDICATES:
        return Program(family, canonical_json(value), option)
    if family == "G" and ast["op"] == "path_cost" and option in _TRANSITIONS:
        return Program(family, canonical_json(value), option)
    raise ContractError("operation does not match the family or vocabulary")


def _path_cost(graph: Graph, option: str, fuel: Fuel) -> int | None:
    adjacency = [[] for _ in range(graph.nodes)]
    for edge in graph.edges:
        fuel.spend()
        adjacency[edge.start].append(edge)

    initial = (graph.start, -1)
    best = {initial: 0}
    queue = [(0, *initial)]
    transition = _TRANSITIONS[option]
    while queue:
        fuel.spend()
        cost, node, previous = heapq.heappop(queue)
        if cost != best[(node, previous)]:
            continue
        if node == graph.goal:
            return cost

        for edge in adjacency[node]:
            fuel.spend()
            if previous != -1 and not transition(previous, edge.label):
                continue
            state = (edge.end, edge.label)
            distance = cost + edge.cost
            if state not in best or distance < best[state]:
                best[state] = distance
                heapq.heappush(queue, (distance, *state))
    return None


def execute(program: Program, value: Input, fuel: Fuel) -> Output:
    fuel.spend()
    if program.family == "S":
        assert isinstance(value, tuple)
        predicate = _PREDICATES[program.option]
        flags = []
        for previous, current in zip(value, value[1:]):
            fuel.spend()
            flags.append(int(predicate(previous, current)))
        return tuple(flags)
    assert isinstance(value, Graph)
    return _path_cost(value, program.option, fuel)


def predict(program_ast: bytes, raw_input: bytes, fuel: Fuel) -> Output:
    """Evaluate a single unlabeled input against an immutable AST."""
    program = compile_ast(program_ast)
    value = input_value(program.family, read_json(raw_input, max_bytes=4096))
    return execute(program, value, fuel)
