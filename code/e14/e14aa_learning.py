"""Bounded synthesis of sparse residual operator forms from purchased labels.

The supplied primitives are addition, multiplication, subtraction, modulo,
equality and threshold comparison. Search composes up to two predicate terms
and fits their signed coefficients; it can express signatures absent from
E1.4y's single-term grammar. This is finite typed program synthesis, not
discovery of an unconstrained primitive or an open-world soundness guarantee.

No task bank, oracle, held-out labels, or prior accepted operator is imported.
Resource counters include local predicate-table construction, failed candidate
fits, and signatures of surviving candidates. CPU limits are cooperative and
must be paired with a process timeout for hostile execution.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations, product
import math
import time

from .e14_shared_budget import BudgetContractError

GRID = tuple((lo, hi) for lo in range(4, 19) for hi in range(lo, 19))
GRID_INDEX = {xy: i for i, xy in enumerate(GRID)}
COEFFICIENTS = (-3, -2, -1, 1, 2, 3)
# Atom data is typed; it is never executable code or an oracle callback.
ATOMS = tuple(("residue", p, r) for p in range(2, 7) for r in range(p)) + tuple(
    ("threshold", t) for t in range(2, 11)
)


@dataclass(frozen=True)
class SearchLimits:
    max_candidates: int = 50000
    max_evaluations: int = 4000000
    max_seconds: float = 5.0
    max_terms: int = 2
    max_nodes: int = 25
    max_programs: int = 16384

    def __post_init__(self):
        for name, low, high in (("max_candidates", 1, 100000),
                                ("max_evaluations", 1, 10000000),
                                ("max_terms", 0, 2), ("max_nodes", 3, 31),
                                ("max_programs", 1, 20000)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise BudgetContractError("invalid search limit: " + name)
        if (type(self.max_seconds) not in (int, float)
                or not math.isfinite(self.max_seconds)
                or not 0 < self.max_seconds <= 30):
            raise BudgetContractError("invalid CPU limit")


@dataclass(frozen=True)
class SearchStats:
    candidates: int
    atom_evaluations: int
    evidence_evaluations: int
    signature_evaluations: int
    primitive_evaluations: int
    cpu_seconds: float
    wall_seconds: float

    @property
    def evaluations(self):
        return self.atom_evaluations + self.evidence_evaluations + self.signature_evaluations


@dataclass(frozen=True)
class FitResult:
    programs: tuple
    signatures: tuple
    complete: bool
    status: str
    stats: SearchStats
    scope: str = "CONDITIONAL_FINITE_TWO_TERM_RESIDUAL_DSL"

    @property
    def unique(self):
        # A truncated search never certifies uniqueness.
        return self.complete and len(self.signatures) == 1


@dataclass(frozen=True)
class QueryResult:
    costs: tuple | None
    complete: bool
    status: str
    signature_lookups: int
    cpu_seconds: float
    wall_seconds: float


def _coordinates(lo, hi):
    if type(lo) is not int or type(hi) is not int or (lo, hi) not in GRID_INDEX:
        raise BudgetContractError("invalid legal cost coordinates")


def _checked_tree(ast, *, max_nodes=31):
    """Validate iteratively, bounding malicious depth before evaluation."""
    pending = [ast]
    size = 0
    while pending:
        node = pending.pop()
        size += 1
        if size > max_nodes or type(node) is not tuple or not node:
            raise BudgetContractError("invalid or oversized typed AST")
        op = node[0]
        if op in ("lo", "hi") and len(node) == 1:
            continue
        if (op == "const" and len(node) == 2 and type(node[1]) is int
                and -10 <= node[1] <= 10):
            continue
        if op not in ("add", "sub", "mul", "mod", "eq", "ge") or len(node) != 3:
            raise BudgetContractError("invalid typed AST operation")
        pending.extend((node[1], node[2]))
    return size


def _eval(ast, lo, hi):
    op = ast[0]
    if op == "lo": return lo
    if op == "hi": return hi
    if op == "const": return ast[1]
    a, b = _eval(ast[1], lo, hi), _eval(ast[2], lo, hi)
    if op == "add": return a + b
    if op == "sub": return a - b
    if op == "mul": return a * b
    if op == "mod":
        if b <= 0: raise BudgetContractError("nonpositive modulus")
        return a % b
    if op == "eq": return int(a == b)
    return int(a >= b)


def evaluate(ast, lo, hi):
    """Evaluate validated, bounded tuple AST data on the legal cost domain."""
    _coordinates(lo, hi)
    _checked_tree(ast)
    result = _eval(ast, lo, hi)
    if not 0 <= result <= 960:
        raise BudgetContractError("operator label outside admitted range")
    return result


def signature(ast):
    _checked_tree(ast)
    values = tuple(_eval(ast, *xy) for xy in GRID)
    if any(not 0 <= v <= 960 for v in values):
        raise BudgetContractError("operator label outside admitted range")
    return values


def _program(terms):
    ast = ("add", ("lo",), ("hi",))
    for index, coefficient in terms:
        atom = ATOMS[index]
        gap = ("sub", ("hi",), ("lo",))
        if atom[0] == "residue":
            predicate = ("eq", ("mod", gap, ("const", atom[1])), ("const", atom[2]))
        else:
            predicate = ("ge", gap, ("const", atom[1]))
        ast = ("add", ast, ("mul", ("const", coefficient), predicate))
    return ast


def _observations(observations):
    if type(observations) not in (tuple, list) or len(observations) > 120:
        raise BudgetContractError("invalid purchased evidence history")
    found = {}
    for row in observations:
        if type(row) not in (tuple, list) or len(row) != 2:
            raise BudgetContractError("invalid purchased evidence row")
        xy, label = row
        if type(xy) is not tuple or len(xy) != 2:
            raise BudgetContractError("invalid evidence coordinates")
        _coordinates(*xy)
        if type(label) is not int or not 0 <= label <= 960:
            raise BudgetContractError("invalid purchased label")
        if xy in found and found[xy] != label:
            raise BudgetContractError("conflicting labels require a new semantic epoch")
        found[xy] = label
    return tuple((GRID_INDEX[xy], label) for xy, label in found.items())


class _Exhausted(Exception):
    pass


class _Meter:
    def __init__(self, limits):
        self.limits = limits
        self.started = time.process_time()
        self.wall = time.monotonic()
        self.candidates = self.atom = self.evidence = self.sig = self.primitive = 0
        self.reason = None

    def check_cpu(self):
        if time.process_time() - self.started >= self.limits.max_seconds:
            self.reason = "CPU_LIMIT"
            raise _Exhausted

    def candidate(self):
        self.check_cpu()
        if self.candidates >= self.limits.max_candidates:
            self.reason = "CANDIDATE_LIMIT"
            raise _Exhausted
        self.candidates += 1

    def point(self, stage, primitives):
        total = self.atom + self.evidence + self.sig
        if total >= self.limits.max_evaluations:
            self.reason = "EVALUATION_LIMIT"
            raise _Exhausted
        if total % 256 == 0:
            self.check_cpu()
        setattr(self, stage, getattr(self, stage) + 1)
        self.primitive += primitives

    def stats(self):
        return SearchStats(self.candidates, self.atom, self.evidence, self.sig,
                           self.primitive, time.process_time() - self.started,
                           time.monotonic() - self.wall)


def fit(observations, *, limits=None):
    """Exhaustively fit a bounded sparse form grammar, or explicitly truncate.

    Each candidate is ``lo+hi + sum(a_i * predicate_i(hi-lo))`` with distinct
    atoms, nonzero coefficients in {-3,-2,-1,1,2,3}, and <=2 terms. The
    primitive inventory and finite cost domain are supplied assumptions.
    Semantic deduplication uses all 120 legal *unlabelled* coordinates. It
    never queries or examines the ground-truth value at unused coordinates.
    """
    observed = _observations(observations)
    if limits is None:
        limits = SearchLimits()
    if type(limits) is not SearchLimits:
        raise BudgetContractError("typed SearchLimits required")
    meter = _Meter(limits)
    solutions = {}
    try:
        atom_values = []
        for atom in ATOMS:
            values = []
            for lo, hi in GRID:
                meter.point("atom", 3 if atom[0] == "residue" else 2)
                gap = hi - lo
                values.append(int(gap % atom[1] == atom[2]) if atom[0] == "residue"
                              else int(gap >= atom[1]))
            atom_values.append(tuple(values))

        for size in range(limits.max_terms + 1):
            for atom_indices in combinations(range(len(ATOMS)), size):
                for coefficients in product(COEFFICIENTS, repeat=size):
                    terms = tuple(zip(atom_indices, coefficients))
                    # Node cap defines a smaller declared DSL, rather than a
                    # partly searched bigger one. Resource truncation differs.
                    nodes = 3 + sum(10 if ATOMS[i][0] == "residue" else 8 for i in atom_indices)
                    if nodes > limits.max_nodes:
                        continue
                    meter.candidate()
                    tables = tuple(atom_values[i] for i in atom_indices)
                    arithmetic_ops = 1 + 2 * size

                    def prediction(index):
                        lo, hi = GRID[index]
                        value = lo + hi
                        for coefficient, table in zip(coefficients, tables):
                            value += coefficient * table[index]
                        return value

                    matches = True
                    for index, label in observed:
                        meter.point("evidence", arithmetic_ops)
                        if prediction(index) != label:
                            matches = False
                            break
                    if not matches:
                        continue
                    values = []
                    for index in range(len(GRID)):
                        meter.point("sig", arithmetic_ops)
                        values.append(prediction(index))
                    sig = tuple(values)
                    if sig not in solutions:
                        if len(solutions) >= limits.max_programs:
                            meter.reason = "PROGRAM_LIMIT"
                            raise _Exhausted
                        solutions[sig] = _program(terms)
        complete = True
    except _Exhausted:
        complete = False
    status = ("UNIQUE_CONDITIONAL" if len(solutions) == 1 else
              "AMBIGUOUS" if solutions else "NO_FIT") if complete else meter.reason
    return FitResult(tuple(solutions.values()), tuple(solutions), complete, status, meter.stats())


def select_query(result, observations, *, allowed=None, max_evaluations=3000000,
                 max_seconds=5.0):
    """Minimax split among surviving signatures; never repeat paid evidence.

    A partial search may still suggest an experiment, but cannot certify a
    unique operator. The deterministic selector uses zero oracle labels.
    It performs at most 120 * len(result.signatures) signature lookups.
    """
    if (type(result) is not FitResult or type(result.programs) is not tuple
            or type(result.signatures) is not tuple
            or len(result.programs) != len(result.signatures)
            or len(result.signatures) > 20000
            or any(type(sig) is not tuple or len(sig) != len(GRID) for sig in result.signatures)):
        raise BudgetContractError("invalid typed fit result")
    if type(max_evaluations) is not int or not 1 <= max_evaluations <= 10000000:
        raise BudgetContractError("invalid query evaluation limit")
    if (type(max_seconds) not in (int, float) or not math.isfinite(max_seconds)
            or not 0 < max_seconds <= 30):
        raise BudgetContractError("invalid query CPU limit")
    observed = _observations(observations)
    if allowed is None:
        allowed = GRID
    if type(allowed) not in (list, tuple) or len(allowed) > len(GRID):
        raise BudgetContractError("invalid query domain")
    for xy in allowed:
        if type(xy) is not tuple or len(xy) != 2:
            raise BudgetContractError("invalid query coordinates")
        _coordinates(*xy)
    used = {i for i, _ in observed}
    offers = []
    started, wall = time.process_time(), time.monotonic()
    lookups = 0
    def answer(costs, complete, status):
        return QueryResult(costs, complete, status, lookups,
                           time.process_time() - started, time.monotonic() - wall)
    for xy in allowed:
        index = GRID_INDEX[xy]
        if index in used:
            continue
        groups = Counter()
        for sig in result.signatures:
            if lookups >= max_evaluations:
                return answer(None, False, "EVALUATION_LIMIT")
            if lookups % 256 == 0 and time.process_time() - started >= max_seconds:
                return answer(None, False, "CPU_LIMIT")
            value = sig[index]
            lookups += 1
            if type(value) is not int or not 0 <= value <= 960:
                raise BudgetContractError("invalid candidate signature label")
            groups[value] += 1
        if len(groups) > 1:
            offers.append(((sum(n * n for n in groups.values()), max(groups.values()), xy), xy))
    return answer(min(offers)[1] if offers else None, True, "SELECTED" if offers else "NO_SPLIT")


def choose_query(result, observations, *, allowed=None):
    """Convenience wrapper; use select_query to retain selection resources."""
    return select_query(result, observations, allowed=allowed).costs
