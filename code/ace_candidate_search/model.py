"""Closed, integer-typed AST and validated resource contracts (stdlib only)."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json


class IntegrityError(ValueError):
    """Invalid configuration, data, AST, or persisted evidence."""


def integer(value: object, low: int, high: int, name: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise IntegrityError('invalid ' + name)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class Expr:
    """Each node has type Int; binary operations have signature Int × Int → Int."""
    op: str
    value: int | str | None = None
    args: tuple[Expr, ...] = ()

    def __post_init__(self) -> None:
        if type(self.op) is not str or type(self.args) is not tuple:
            raise IntegrityError('AST node type')
        if self.op == 'const':
            integer(self.value, -20, 20, 'constant')
            valid = not self.args
        elif self.op == 'var':
            valid = type(self.value) is str and self.value in ('x', 'y') and not self.args
        elif self.op in ('add', 'sub', 'mul'):
            valid = self.value is None and len(self.args) == 2 and all(type(a) is Expr for a in self.args)
        else:
            valid = False
        if not valid:
            raise IntegrityError('forbidden AST')
        if self.depth > 6 or self.operations > 15:
            raise IntegrityError('AST structural ceiling')

    @property
    def depth(self) -> int:
        return 0 if not self.args else 1 + max(a.depth for a in self.args)

    @property
    def operations(self) -> int:
        return int(bool(self.args)) + sum(a.operations for a in self.args)

    @property
    def nodes(self) -> int:
        return 1 + sum(a.nodes for a in self.args)

    def data(self) -> list:
        return [self.op, self.value, [a.data() for a in self.args]]

    @property
    def key(self) -> str:
        return canonical(self.data()).decode()

    @property
    def identity(self) -> str:
        return digest(self.data())


@dataclass(frozen=True)
class Observation:
    x: int
    y: int
    target: int

    def __post_init__(self) -> None:
        integer(self.x, -100, 100, 'x')
        integer(self.y, -100, 100, 'y')
        integer(self.target, -10**9, 10**9, 'target')


def observations(rows: tuple[Observation, ...]) -> None:
    if type(rows) is not tuple or not 1 <= len(rows) <= 128 or any(type(r) is not Observation for r in rows):
        raise IntegrityError('observations must be a bounded nonempty tuple')
    if len({(r.x, r.y) for r in rows}) != len(rows):
        raise IntegrityError('duplicate inputs')


@dataclass(frozen=True)
class Grammar:
    constants: tuple[int, ...] = (0, 1, 2, 3)
    operations: tuple[str, ...] = ('add', 'sub', 'mul')

    def __post_init__(self) -> None:
        if type(self.constants) is not tuple or len(self.constants) > 16:
            raise IntegrityError('constants grammar')
        for c in self.constants:
            integer(c, -20, 20, 'grammar constant')
        if len(set(self.constants)) != len(self.constants):
            raise IntegrityError('duplicate constants')
        if (type(self.operations) is not tuple or not self.operations or
                any(type(o) is not str or o not in ('add', 'sub', 'mul') for o in self.operations) or
                len(set(self.operations)) != len(self.operations)):
            raise IntegrityError('operation grammar')

    def terminals(self) -> tuple[Expr, ...]:
        return (Expr('var', 'x'), Expr('var', 'y')) + tuple(Expr('const', c) for c in self.constants)


@dataclass(frozen=True)
class Limits:
    max_depth: int = 3
    max_operations: int = 3
    max_candidates: int = 2000
    max_work: int = 200000
    beam_width: int = 20
    shortlist: int = 5

    def __post_init__(self) -> None:
        for name, low, high in (('max_depth', 0, 6), ('max_operations', 0, 15),
                                ('max_candidates', 1, 10000), ('max_work', 1, 5000000),
                                ('beam_width', 1, 128), ('shortlist', 1, 32)):
            integer(getattr(self, name), low, high, name)


class Exhausted(RuntimeError):
    pass


@dataclass
class Meter:
    limit: int
    work: int = 0

    def charge(self, amount: int = 1) -> None:
        if self.work + amount > self.limit:
            raise Exhausted('compute limit')
        self.work += amount


def interpret(expr: Expr, x: int, y: int, meter: Meter) -> int:
    """Dispatch only closed AST variants; charge each visited node, bound intermediates."""
    if type(expr) is not Expr:
        raise IntegrityError('interpreter requires Expr')
    integer(x, -100, 100, 'x')
    integer(y, -100, 100, 'y')

    def walk(node: Expr) -> int:
        meter.charge()
        if node.op == 'var':
            return x if node.value == 'x' else y
        if node.op == 'const':
            return node.value
        left, right = (walk(a) for a in node.args)
        if node.op == 'add':
            value = left + right
        elif node.op == 'sub':
            value = left - right
        elif node.op == 'mul':
            value = left * right
        else:
            raise IntegrityError('forbidden operation')
        if abs(value) > 10**9:
            raise OverflowError('bounded integer overflow')
        return value
    return walk(expr)
