"""Interpret a closed set of typed ASTs with a step budget."""

import hashlib
import heapq
import operator
from dataclasses import dataclass

from .contract import (
    MAX_FUEL, ContractError, Graph, Input, Output, array, canonical_json, input_value,
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
    table: tuple = ()
    accepts: tuple[int, ...] = ()

    @property
    def sha256(self):
        return hashlib.sha256(self.ast).hexdigest()


def compile_ast(raw: bytes, *, allow_extension=False) -> Program:
    value = read_json(raw, max_bytes=1024)
    require_fields(value, "family", "ast")
    family, ast = value["family"], value["ast"]
    if type(ast) is dict:
        operation = ast.get("op")
        if operation in ("symbol_machine", "graph_machine"):
            return _compile_machine(family, ast, canonical_json(value), 1, 4)
        if operation in ("symbol_extension", "graph_extension"):
            if not allow_extension:
                raise ContractError("state extension is disabled")
            return _compile_machine(family, ast, canonical_json(value), 5, 8)
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


def _compile_machine(family, ast, canonical, minimum, maximum):
    operation = ast["op"]
    if family == "S" and operation in ("symbol_machine", "symbol_extension"):
        require_fields(ast, "op", "table")
        rows = array(ast["table"], minimum, maximum)
        table = []
        for row in rows:
            cells = []
            for cell in array(row, 3, 3):
                state, bit = array(cell, 2, 2)
                cells.append((integer(state, 0, len(rows) - 1), integer(bit, 0, 1)))
            table.append(tuple(cells))
        return Program(family, canonical, "symbol_machine", tuple(table))
    if family == "G" and operation in ("graph_machine", "graph_extension"):
        require_fields(ast, "op", "table", "accept")
        rows = array(ast["table"], minimum, maximum)
        table = tuple(tuple(integer(cell, -1, len(rows) - 1)
                            for cell in array(row, 3, 3)) for row in rows)
        accepts = tuple(integer(bit, 0, 1) for bit in array(ast["accept"], len(rows), len(rows)))
        return Program(family, canonical, "graph_machine", table, accepts)
    raise ContractError("machine does not match the family")


def symbol_event(left, right):
    """Three comparison events shared by symbolic machines and inference."""
    return 0 if left < right else 1 if left == right else 2


def graph_costs(graph: Graph, table, fuel: Fuel):
    """Find minimum cost to each monitor state at the goal."""
    adjacency = [[] for _ in range(graph.nodes)]
    for edge in graph.edges:
        fuel.spend()
        adjacency[edge.start].append(edge)
    best = {(graph.start, -1, 0): 0}
    queue = [(0, graph.start, -1, 0)]
    costs = [None] * len(table)
    while queue:
        fuel.spend()
        cost, node, previous, state = heapq.heappop(queue)
        if cost != best[node, previous, state]:
            continue
        if node == graph.goal and costs[state] is None:
            costs[state] = cost
            if None not in costs:
                break
        for edge in adjacency[node]:
            fuel.spend()
            event = 0 if previous == -1 else 1 if previous == edge.label else 2
            next_state = table[state][event]
            if next_state == -1:
                continue
            destination = (edge.end, edge.label, next_state)
            new_cost = cost + edge.cost
            if destination not in best or new_cost < best[destination]:
                best[destination] = new_cost
                heapq.heappush(queue, (new_cost, *destination))
    return costs


def accepted_cost(costs, accepts):
    return min((cost for cost, accept in zip(costs, accepts, strict=True)
                if accept and cost is not None), default=None)


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
        if program.option == "symbol_machine":
            state = 0
            flags = []
            for left, right in zip(value, value[1:]):
                fuel.spend()
                state, bit = program.table[state][symbol_event(left, right)]
                flags.append(bit)
            return tuple(flags)
        predicate = _PREDICATES[program.option]
        flags = []
        for previous, current in zip(value, value[1:]):
            fuel.spend()
            flags.append(int(predicate(previous, current)))
        return tuple(flags)
    assert isinstance(value, Graph)
    if program.option == "graph_machine":
        return accepted_cost(graph_costs(value, program.table, fuel), program.accepts)
    return _path_cost(value, program.option, fuel)


def predict(program_ast: bytes, raw_input: bytes, fuel: Fuel, *, allow_extension=False) -> Output:
    """Evaluate a single unlabeled input against an immutable AST."""
    program = compile_ast(program_ast, allow_extension=allow_extension)
    value = input_value(program.family, read_json(raw_input, max_bytes=4096))
    return execute(program, value, fuel)
