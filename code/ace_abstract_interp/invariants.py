"""Abstract Interpretation Invariant Analyzer & Invariant Synthesizer.

Mathematical Foundation:
- Galois Connection (alpha, gamma) over the Interval Lattice (D_sharp, sqsubseteq, sqcup, sqcap, top, bot).
- Sound abstract transfer operators (+, -, *).
- Inductive invariant synthesis via Widening (nabla) and Narrowing (Delta).
- Sound bounds certification for program candidates and semantic drift quarantine.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

INF = float("inf")
NEG_INF = float("-inf")


@dataclass(frozen=True)
class Interval:
    """Element of the Interval Lattice. None represents bottom (empty set)."""
    low: float = NEG_INF
    high: float = INF
    is_bot: bool = False

    @classmethod
    def bot(cls) -> Interval:
        return cls(low=INF, high=NEG_INF, is_bot=True)

    @classmethod
    def top(cls) -> Interval:
        return cls(low=NEG_INF, high=INF, is_bot=False)

    @classmethod
    def point(cls, val: float) -> Interval:
        return cls(low=float(val), high=float(val), is_bot=False)

    def contains(self, val: float) -> bool:
        if self.is_bot:
            return False
        return self.low <= val <= self.high

    def is_subset(self, other: Interval) -> bool:
        """sqsubseteq ordering: self <= other."""
        if self.is_bot:
            return True
        if other.is_bot:
            return False
        return other.low <= self.low and self.high <= other.high

    def join(self, other: Interval) -> Interval:
        """sqcup: Least Upper Bound."""
        if self.is_bot:
            return other
        if other.is_bot:
            return self
        return Interval(low=min(self.low, other.low), high=max(self.high, other.high))

    def meet(self, other: Interval) -> Interval:
        """sqcap: Greatest Lower Bound."""
        if self.is_bot or other.is_bot:
            return Interval.bot()
        new_low = max(self.low, other.low)
        new_high = min(self.high, other.high)
        if new_low > new_high:
            return Interval.bot()
        return Interval(low=new_low, high=new_high)

    def widen(self, other: Interval) -> Interval:
        """Widening operator (nabla) accelerating divergence to infinity."""
        if self.is_bot:
            return other
        if other.is_bot:
            return self
        new_low = NEG_INF if other.low < self.low else self.low
        new_high = INF if other.high > self.high else self.high
        return Interval(low=new_low, high=new_high)

    def narrow(self, other: Interval) -> Interval:
        """Narrowing operator (Delta) refining infinite bounds back to finite bounds."""
        if self.is_bot or other.is_bot:
            return Interval.bot()
        new_low = other.low if self.low == NEG_INF else self.low
        new_high = other.high if self.high == INF else self.high
        return Interval(low=new_low, high=new_high)

    # Abstract arithmetic transfer operators
    def __add__(self, other: Interval) -> Interval:
        if self.is_bot or other.is_bot:
            return Interval.bot()
        return Interval(low=self.low + other.low, high=self.high + other.high)

    def __sub__(self, other: Interval) -> Interval:
        if self.is_bot or other.is_bot:
            return Interval.bot()
        return Interval(low=self.low - other.high, high=self.high - other.low)

    def __mul__(self, other: Interval) -> Interval:
        if self.is_bot or other.is_bot:
            return Interval.bot()
        products = [
            self.low * other.low,
            self.low * other.high,
            self.high * other.low,
            self.high * other.high,
        ]
        # Filter out nan from 0 * inf
        valid = [p for p in products if not math.isnan(p)]
        if not valid:
            return Interval.top()
        return Interval(low=min(valid), high=max(valid))


class AbstractState:
    """Environment mapping variable identifiers to abstract intervals."""

    def __init__(self, mapping: Optional[Dict[str, Interval]] = None, is_bot: bool = False):
        self.mapping = dict(mapping) if mapping else {}
        self.is_bot = is_bot

    @classmethod
    def bot(cls) -> AbstractState:
        return cls(is_bot=True)

    def get(self, var: str) -> Interval:
        if self.is_bot:
            return Interval.bot()
        return self.mapping.get(var, Interval.top())

    def set(self, var: str, interval: Interval) -> AbstractState:
        if self.is_bot or interval.is_bot:
            return AbstractState.bot()
        new_map = dict(self.mapping)
        new_map[var] = interval
        return AbstractState(new_map)

    def join(self, other: AbstractState) -> AbstractState:
        if self.is_bot:
            return other
        if other.is_bot:
            return self
        all_vars = set(self.mapping.keys()) | set(other.mapping.keys())
        joined = {v: self.get(v).join(other.get(v)) for v in all_vars}
        return AbstractState(joined)

    def meet(self, other: AbstractState) -> AbstractState:
        if self.is_bot or other.is_bot:
            return AbstractState.bot()
        all_vars = set(self.mapping.keys()) | set(other.mapping.keys())
        res = {}
        for v in all_vars:
            m = self.get(v).meet(other.get(v))
            if m.is_bot:
                return AbstractState.bot()
            res[v] = m
        return AbstractState(res)

    def widen(self, other: AbstractState) -> AbstractState:
        if self.is_bot:
            return other
        if other.is_bot:
            return self
        all_vars = set(self.mapping.keys()) | set(other.mapping.keys())
        widened = {v: self.get(v).widen(other.get(v)) for v in all_vars}
        return AbstractState(widened)

    def is_subset(self, other: AbstractState) -> bool:
        if self.is_bot:
            return True
        if other.is_bot:
            return False
        return all(self.get(v).is_subset(other.get(v)) for v in self.mapping)


class AbstractInterpreter:
    """Evaluates program expressions and branch guards over abstract intervals."""

    def eval_expr(self, expr: Any, state: AbstractState) -> Interval:
        if isinstance(expr, (int, float)):
            return Interval.point(expr)
        elif isinstance(expr, str):
            return state.get(expr)
        elif isinstance(expr, tuple):
            op = expr[0]
            if op == "+":
                return self.eval_expr(expr[1], state) + self.eval_expr(expr[2], state)
            elif op == "-":
                return self.eval_expr(expr[1], state) - self.eval_expr(expr[2], state)
            elif op == "*":
                return self.eval_expr(expr[1], state) * self.eval_expr(expr[2], state)
        return Interval.top()

    def filter_guard(self, var: str, op: str, limit: float, state: AbstractState) -> AbstractState:
        """Refines state assuming branch condition `var op limit` is true."""
        curr = state.get(var)
        if op == "<=":
            guard_interval = Interval(low=NEG_INF, high=limit)
        elif op == "<":
            guard_interval = Interval(low=NEG_INF, high=limit - 1)
        elif op == ">=":
            guard_interval = Interval(low=limit, high=INF)
        elif op == ">":
            guard_interval = Interval(low=limit + 1, high=INF)
        elif op == "==":
            guard_interval = Interval.point(limit)
        else:
            guard_interval = Interval.top()

        refined = curr.meet(guard_interval)
        return state.set(var, refined)


class InvariantSynthesizer:
    """Computes inductive loop invariants via Widening and Narrowing fixpoint iteration."""

    def __init__(self, max_widening_steps: int = 10, max_narrowing_steps: int = 5):
        self.max_widening_steps = max_widening_steps
        self.max_narrowing_steps = max_narrowing_steps

    def synthesize_loop_invariant(
        self,
        init_state: AbstractState,
        loop_step_fn: Callable[[AbstractState], AbstractState],
    ) -> Tuple[AbstractState, int]:
        """Computes least fixpoint inductive invariant: Post(I) <= I."""
        curr = init_state
        step = 0

        # Phase 1: Widening to guarantee finite convergence
        while step < self.max_widening_steps:
            step += 1
            next_state = curr.join(loop_step_fn(curr))
            if next_state.is_subset(curr):
                break
            curr = curr.widen(next_state)

        # Phase 2: Narrowing to recover precision
        narrow_step = 0
        while narrow_step < self.max_narrowing_steps:
            narrow_step += 1
            refined = curr.meet(loop_step_fn(curr))
            if curr.is_subset(refined):
                break
            curr = refined

        return curr, step

    def certify_bounds(
        self,
        state: AbstractState,
        var: str,
        safe_low: float,
        safe_high: float,
    ) -> Tuple[bool, Interval]:
        """Certifies that variable var strictly stays within safe bounds [safe_low, safe_high]."""
        interval = state.get(var)
        safe_interval = Interval(low=safe_low, high=safe_high)
        is_safe = interval.is_subset(safe_interval)
        return is_safe, interval
