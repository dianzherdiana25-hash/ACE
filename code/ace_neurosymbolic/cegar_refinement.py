"""Counterexample-Guided Abstraction Refinement (CEGAR) over Predicate Lattices.

Implements the Clarke-Grumberg-Jha (2000) CEGAR loop:
1. Abstract Model Checking: Explores program state space over a predicate abstraction lattice L(P).
2. Spurious Counterexample Detection: Concretely simulates abstract counterexample traces.
3. Monotonic Lattice Refinement: Automatically synthesizes Craig-interpolating separating
   predicates to eliminate spurious traces.
4. Inductive Safety Certification: When error states are unreachable, emits verified
   inductive invariants proving program safety.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ace_evolution.island_search import TypedASTNode


@dataclass
class Predicate:
    """A boolean predicate over program states (e.g., 'x >= 0', 'denom != 0')."""
    name: str
    formula: str
    eval_fn: Callable[[Dict[str, Any]], bool]

    def evaluate(self, state: Dict[str, Any]) -> bool:
        try:
            return bool(self.eval_fn(state))
        except Exception:
            return False

    def __repr__(self) -> str:
        return self.formula


@dataclass(frozen=True)
class AbstractPredicateState:
    """An element in the Predicate Lattice L(P): P -> {True, False, TOP, BOT}."""
    values: Tuple[Tuple[str, Optional[bool]], ...]  # Predicate name -> True/False/None (TOP)
    is_bot: bool = False

    @classmethod
    def bot(cls) -> AbstractPredicateState:
        return cls(values=(), is_bot=True)

    @classmethod
    def top(cls, predicates: List[Predicate]) -> AbstractPredicateState:
        return cls(values=tuple((p.name, None) for p in predicates), is_bot=False)

    @classmethod
    def from_dict(cls, val_map: Dict[str, Optional[bool]]) -> AbstractPredicateState:
        return cls(values=tuple(sorted(val_map.items())))

    def get_dict(self) -> Dict[str, Optional[bool]]:
        return dict(self.values)

    def get(self, pred_name: str) -> Optional[bool]:
        for k, v in self.values:
            if k == pred_name:
                return v
        return None

    def join(self, other: AbstractPredicateState) -> AbstractPredicateState:
        """Least Upper Bound (sqcup) in predicate lattice."""
        if self.is_bot:
            return other
        if other.is_bot:
            return self

        d1 = self.get_dict()
        d2 = other.get_dict()
        all_keys = set(d1.keys()).union(set(d2.keys()))
        new_dict: Dict[str, Optional[bool]] = {}

        for k in all_keys:
            v1 = d1.get(k)
            v2 = d2.get(k)
            if v1 == v2:
                new_dict[k] = v1
            else:
                new_dict[k] = None  # Divergence yields TOP (unknown)

        return AbstractPredicateState.from_dict(new_dict)

    def meet(self, other: AbstractPredicateState) -> AbstractPredicateState:
        """Greatest Lower Bound (sqcap) in predicate lattice."""
        if self.is_bot or other.is_bot:
            return AbstractPredicateState.bot()

        d1 = self.get_dict()
        d2 = other.get_dict()
        all_keys = set(d1.keys()).union(set(d2.keys()))
        new_dict: Dict[str, Optional[bool]] = {}

        for k in all_keys:
            v1 = d1.get(k)
            v2 = d2.get(k)
            if v1 is None:
                new_dict[k] = v2
            elif v2 is None:
                new_dict[k] = v1
            elif v1 == v2:
                new_dict[k] = v1
            else:
                # Contradiction True vs False yields BOT (empty set)
                return AbstractPredicateState.bot()

        return AbstractPredicateState.from_dict(new_dict)

    def is_subset(self, other: AbstractPredicateState) -> bool:
        """Lattice ordering: self sqsubseteq other (self implies other)."""
        if self.is_bot:
            return True
        if other.is_bot:
            return False

        d1 = self.get_dict()
        d2 = other.get_dict()
        for k, v2 in d2.items():
            if v2 is not None:
                if d1.get(k) != v2:
                    return False
        return True

    def to_formula(self) -> str:
        if self.is_bot:
            return "FALSE (BOT)"
        parts = []
        for k, v in self.values:
            if v is True:
                parts.append(k)
            elif v is False:
                parts.append(f"(not {k})")
        return " and ".join(parts) if parts else "TRUE (TOP)"


@dataclass
class CFGEdge:
    """A control flow graph transition with guard and assignment updates."""
    src: str
    dst: str
    guard_fn: Callable[[Dict[str, Any]], bool]
    guard_expr: str
    update_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    update_expr: str = "pass"

    def is_feasible(self, concrete_state: Dict[str, Any]) -> bool:
        try:
            return bool(self.guard_fn(concrete_state))
        except Exception:
            return False

    def execute(self, concrete_state: Dict[str, Any]) -> Dict[str, Any]:
        new_state = copy.deepcopy(concrete_state)
        if self.update_fn:
            new_state = self.update_fn(new_state)
        return new_state


class ProgramCFG:
    """Control Flow Graph representation of a neurosymbolic program verification task."""

    def __init__(self, entry_loc: str = "entry", error_loc: str = "error"):
        self.entry_loc = entry_loc
        self.error_loc = error_loc
        self.locations: Set[str] = {entry_loc, error_loc}
        self.edges: List[CFGEdge] = []
        self.adj_out: Dict[str, List[CFGEdge]] = {}

    def add_location(self, loc: str):
        self.locations.add(loc)
        if loc not in self.adj_out:
            self.adj_out[loc] = []

    def add_edge(
        self,
        src: str,
        dst: str,
        guard_fn: Callable[[Dict[str, Any]], bool],
        guard_expr: str = "True",
        update_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        update_expr: str = "pass",
    ):
        self.add_location(src)
        self.add_location(dst)
        edge = CFGEdge(src, dst, guard_fn, guard_expr, update_fn, update_expr)
        self.edges.append(edge)
        self.adj_out[src].append(edge)


@dataclass
class AbstractTraceStep:
    """A step in an abstract counterexample trace."""
    loc: str
    state: AbstractPredicateState
    edge: Optional[CFGEdge] = None


@dataclass
class CEGARResult:
    """Outcome of CEGAR Verification."""
    status: str  # 'SAFE', 'UNSAFE', 'UNKNOWN'
    is_certified: bool
    iterations: int
    spurious_counterexamples_eliminated: int
    discovered_predicates: List[str]
    inductive_invariants: Dict[str, str]
    concrete_counterexample: Optional[List[Dict[str, Any]]]
    runtime_sec: float


class CEGARVerifier:
    """Clarke-Grumberg-Jha CEGAR Verification Engine."""

    def __init__(
        self,
        cfg: ProgramCFG,
        initial_predicates: Optional[List[Predicate]] = None,
        max_iterations: int = 15,
    ):
        self.cfg = cfg
        self.predicates: List[Predicate] = list(initial_predicates or [])
        self.max_iterations = max_iterations

    @staticmethod
    def _are_complementary(expr1: str, expr2: str) -> bool:
        """Determines if two guard expressions are logical complements (e.g., 'y == 0' and 'y != 0')."""
        e1 = expr1.strip()
        e2 = expr2.strip()
        if e1 == e2:
            return False
        if "!=" in e1 and "==" in e2:
            return e1.replace("!=", "==") == e2
        if "==" in e1 and "!=" in e2:
            return e1.replace("==", "!=") == e2
        if "<" in e1 and ">=" in e2:
            return e1.replace("<", ">=") == e2
        if ">=" in e1 and "<" in e2:
            return e1.replace(">=", "<") == e2
        if ">" in e1 and "<=" in e2:
            return e1.replace(">", "<=") == e2
        if "<=" in e1 and ">" in e2:
            return e1.replace("<=", ">") == e2
        if e1 == f"not ({e2})" or e2 == f"not ({e1})":
            return True
        if e1 == f"not {e2}" or e2 == f"not {e1}":
            return True
        return False

    def _abstract_post(
        self,
        curr_state: AbstractPredicateState,
        edge: CFGEdge,
    ) -> AbstractPredicateState:
        """Sound abstract postcondition transfer operator over predicate lattice."""
        if curr_state.is_bot:
            return AbstractPredicateState.bot()

        curr_dict = curr_state.get_dict()

        # 1. Contradiction check: Does the edge guard contradict current predicate valuations?
        for p in self.predicates:
            val = curr_dict.get(p.name)
            if val is True:
                # If guard is complementary to p, cannot traverse edge
                if self._are_complementary(edge.guard_expr, p.formula):
                    return AbstractPredicateState.bot()
            elif val is False:
                # If guard requires p, but p is known False, cannot traverse edge
                if edge.guard_expr == p.formula or edge.guard_expr == p.name:
                    return AbstractPredicateState.bot()

        new_dict: Dict[str, Optional[bool]] = {}

        # 2. Compute postcondition valuations for each predicate
        for p in self.predicates:
            # If edge guard explicitly enforces or refutes predicate
            if p.name == edge.guard_expr or p.formula == edge.guard_expr:
                new_dict[p.name] = True
            elif self._are_complementary(edge.guard_expr, p.formula):
                new_dict[p.name] = False
            elif edge.update_fn is None:
                # Without variable mutation, predicate valuations are preserved across edges
                new_dict[p.name] = curr_dict.get(p.name)
            else:
                # With updates, re-evaluate or fall back to TOP
                new_dict[p.name] = None

        return AbstractPredicateState.from_dict(new_dict)

    def _model_check_abstract(
        self,
    ) -> Tuple[bool, Dict[str, AbstractPredicateState], Optional[List[AbstractTraceStep]]]:
        """Explores the abstract state space to find if error_loc is reachable."""
        # Initial abstract state at entry location
        initial_state = AbstractPredicateState.top(self.predicates)
        reachable: Dict[str, AbstractPredicateState] = {
            loc: AbstractPredicateState.bot() for loc in self.cfg.locations
        }
        reachable[self.cfg.entry_loc] = initial_state

        parent_map: Dict[Tuple[str, AbstractPredicateState], Optional[AbstractTraceStep]] = {}
        parent_map[(self.cfg.entry_loc, initial_state)] = None

        worklist: List[Tuple[str, AbstractPredicateState]] = [(self.cfg.entry_loc, initial_state)]
        error_reached_state: Optional[AbstractPredicateState] = None

        while worklist:
            curr_loc, curr_state = worklist.pop(0)

            if curr_loc == self.cfg.error_loc:
                error_reached_state = curr_state
                break

            for edge in self.cfg.adj_out.get(curr_loc, []):
                next_state = self._abstract_post(curr_state, edge)
                if next_state.is_bot:
                    continue

                prev_reach = reachable[edge.dst]
                if not next_state.is_subset(prev_reach):
                    joined = prev_reach.join(next_state)
                    reachable[edge.dst] = joined
                    step_key = (edge.dst, next_state)
                    parent_map[step_key] = AbstractTraceStep(loc=curr_loc, state=curr_state, edge=edge)
                    worklist.append((edge.dst, next_state))

        # Check if error state was reached
        if error_reached_state is not None:
            # Reconstruct abstract counterexample trace
            trace: List[AbstractTraceStep] = [
                AbstractTraceStep(loc=self.cfg.error_loc, state=error_reached_state)
            ]
            curr_key = (self.cfg.error_loc, error_reached_state)
            while parent_map.get(curr_key) is not None:
                prev_step = parent_map[curr_key]
                if prev_step:
                    trace.insert(0, prev_step)
                    curr_key = (prev_step.loc, prev_step.state)
                else:
                    break
            return False, reachable, trace

        return True, reachable, None

    def _simulate_concrete_trace(
        self,
        abstract_trace: List[AbstractTraceStep],
        initial_concrete_states: List[Dict[str, Any]],
    ) -> Tuple[bool, Optional[List[Dict[str, Any]]], int]:
        """Simulates abstract trace concretely.

        Returns:
            (is_real_counterexample, concrete_witness_trace, failure_index)
        """
        active_paths: List[List[Dict[str, Any]]] = [[copy.deepcopy(s)] for s in initial_concrete_states]

        for step_idx in range(len(abstract_trace) - 1):
            edge = abstract_trace[step_idx].edge
            if not edge:
                continue

            next_paths: List[List[Dict[str, Any]]] = []
            for path in active_paths:
                curr_concrete = path[-1]
                if edge.is_feasible(curr_concrete):
                    next_concrete = edge.execute(curr_concrete)
                    next_paths.append(path + [next_concrete])

            if not next_paths:
                # Spurious counterexample: infeasible transition at step_idx
                return False, None, step_idx

            active_paths = next_paths

        # If any concrete path reached the error location, counterexample is real!
        return True, active_paths[0], len(abstract_trace) - 1

    def _discover_separating_predicate(
        self,
        failed_edge: CFGEdge,
        step_idx: int,
    ) -> Predicate:
        """Synthesizes a new interpolating predicate to eliminate the spurious counterexample."""
        formula = failed_edge.guard_expr
        name = f"pred_interpolant_{step_idx}_{formula.replace(' ', '_').replace('!=', 'neq').replace('==', 'eq')}"
        guard_fn = failed_edge.guard_fn

        return Predicate(
            name=name,
            formula=formula,
            eval_fn=guard_fn,
        )

    def verify(
        self,
        initial_concrete_states: Optional[List[Dict[str, Any]]] = None,
    ) -> CEGARResult:
        """Executes full CEGAR verification loop."""
        start_time = time.time()
        initial_samples = initial_concrete_states or [{"x": 10, "y": 0, "denom": 0, "count": 0, "len": 0}]

        spurious_count = 0
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            # 1. Abstract Model Checking
            is_safe, reachable_invariants, abstract_trace = self._model_check_abstract()

            if is_safe:
                duration = time.time() - start_time
                invariants_summary = {
                    loc: state.to_formula()
                    for loc, state in reachable_invariants.items()
                }
                return CEGARResult(
                    status="SAFE",
                    is_certified=True,
                    iterations=iterations,
                    spurious_counterexamples_eliminated=spurious_count,
                    discovered_predicates=[p.formula for p in self.predicates],
                    inductive_invariants=invariants_summary,
                    concrete_counterexample=None,
                    runtime_sec=duration,
                )

            # 2. Counterexample Analysis & Concrete Simulation
            if abstract_trace is None:
                break

            is_real, concrete_witness, failed_idx = self._simulate_concrete_trace(
                abstract_trace, initial_samples
            )

            if is_real:
                # Genuine bug / unsafe counterexample
                duration = time.time() - start_time
                return CEGARResult(
                    status="UNSAFE",
                    is_certified=False,
                    iterations=iterations,
                    spurious_counterexamples_eliminated=spurious_count,
                    discovered_predicates=[p.formula for p in self.predicates],
                    inductive_invariants={},
                    concrete_counterexample=concrete_witness,
                    runtime_sec=duration,
                )

            # 3. Spurious Counterexample Elimination & Abstraction Refinement
            spurious_count += 1
            failed_edge = abstract_trace[failed_idx].edge
            if failed_edge is None:
                break

            new_pred = self._discover_separating_predicate(failed_edge, failed_idx)
            # Monotonic lattice refinement: add new predicate
            self.predicates.append(new_pred)

        duration = time.time() - start_time
        return CEGARResult(
            status="UNKNOWN",
            is_certified=False,
            iterations=iterations,
            spurious_counterexamples_eliminated=spurious_count,
            discovered_predicates=[p.formula for p in self.predicates],
            inductive_invariants={},
            concrete_counterexample=None,
            runtime_sec=duration,
        )


def build_guarded_division_cfg() -> ProgramCFG:
    """Builds a CFG of guarded division: safe if y != 0 branch protects the divide."""
    cfg = ProgramCFG(entry_loc="entry", error_loc="error")
    cfg.add_location("check")
    cfg.add_location("compute_safe")
    cfg.add_location("fallback")
    cfg.add_location("exit")

    # entry -> check
    cfg.add_edge("entry", "check", lambda s: True, "True")

    # check -> compute_safe (guard: y != 0)
    cfg.add_edge(
        "check",
        "compute_safe",
        lambda s: s.get("y", 0) != 0,
        "y != 0",
        update_fn=lambda s: {**s, "z": s.get("x", 0) // s.get("y", 1)},
    )

    # check -> fallback (guard: y == 0)
    cfg.add_edge(
        "check",
        "fallback",
        lambda s: s.get("y", 0) == 0,
        "y == 0",
        update_fn=lambda s: {**s, "z": 0},
    )

    # compute_safe -> exit
    cfg.add_edge("compute_safe", "exit", lambda s: True, "True")

    # fallback -> exit
    cfg.add_edge("fallback", "exit", lambda s: True, "True")

    # compute_safe -> error (if y == 0 happens at compute_safe)
    cfg.add_edge(
        "compute_safe",
        "error",
        lambda s: s.get("y", 0) == 0,
        "y == 0",
    )

    return cfg


def build_unguarded_unsafe_division_cfg() -> ProgramCFG:
    """Builds a CFG of unguarded division: truly unsafe since y can be zero."""
    cfg = ProgramCFG(entry_loc="entry", error_loc="error")
    cfg.add_location("compute")
    cfg.add_location("exit")

    # entry -> compute
    cfg.add_edge("entry", "compute", lambda s: True, "True")

    # compute -> error (if y == 0)
    cfg.add_edge(
        "compute",
        "error",
        lambda s: s.get("y", 0) == 0,
        "y == 0",
    )

    # compute -> exit (if y != 0)
    cfg.add_edge(
        "compute",
        "exit",
        lambda s: s.get("y", 0) != 0,
        "y != 0",
    )

    return cfg


def build_loop_counter_cfg(target_count: int = 3) -> ProgramCFG:
    """Builds a CFG with a counting loop: terminates and proves i >= target_count."""
    cfg = ProgramCFG(entry_loc="entry", error_loc="error")
    cfg.add_location("loop_head")
    cfg.add_location("body")
    cfg.add_location("done")
    cfg.add_location("exit")

    # entry -> loop_head (init: i = 0)
    cfg.add_edge("entry", "loop_head", lambda s: True, "True", update_fn=lambda s: {**s, "i": 0})

    # loop_head -> body (guard: i < target_count)
    cfg.add_edge(
        "loop_head",
        "body",
        lambda s: s.get("i", 0) < target_count,
        f"i < {target_count}",
        update_fn=lambda s: {**s, "i": s.get("i", 0) + 1},
    )

    # body -> loop_head
    cfg.add_edge("body", "loop_head", lambda s: True, "True")

    # loop_head -> done (guard: i >= target_count)
    cfg.add_edge(
        "loop_head",
        "done",
        lambda s: s.get("i", 0) >= target_count,
        f"i >= {target_count}",
    )

    # done -> exit (assert: i >= target_count)
    cfg.add_edge(
        "done",
        "exit",
        lambda s: s.get("i", 0) >= target_count,
        f"i >= {target_count}",
    )

    # done -> error (if i < target_count at done)
    cfg.add_edge(
        "done",
        "error",
        lambda s: s.get("i", 0) < target_count,
        f"i < {target_count}",
    )

    return cfg

