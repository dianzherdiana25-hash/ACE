"""Domain-agnostic, evidence-gated capability composition for ACE.

This module plans over typed contracts. It DOES NOT infer goal semantics,
run executable code, connect to providers, or prove open-ended learning.
Its registry admits arbitrary type names and providers without a domain
allowlist, while each planning invocation has explicit finite resources.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Iterable

EFFECTS = frozenset({"none", "read", "write", "external"})
STATUSES = frozenset({"VERIFIED", "UNVERIFIED", "FAILED"})


def _tokens(items: Iterable[str], field: str) -> frozenset[str]:
    if isinstance(items, str):
        raise TypeError(f"{field} must be an iterable of type names, not a string")
    result = frozenset(items)
    if any(not isinstance(t, str) or not t.strip() or len(t) > 128 for t in result):
        raise ValueError(f"{field} contains invalid type names")
    return result


@dataclass(frozen=True)
class Capability:
    capability_id: str
    consumes: frozenset[str]
    produces: frozenset[str]
    provider: str
    evidence_ref: str = ""
    status: str = "UNVERIFIED"
    effect: str = "none"
    cost_units: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            raise ValueError("capability_id must be nonempty")
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("provider must be nonempty")
        object.__setattr__(self, "consumes", _tokens(self.consumes, "consumes"))
        object.__setattr__(self, "produces", _tokens(self.produces, "produces"))
        if not self.produces:
            raise ValueError("capability must produce at least one output type")
        if self.status not in STATUSES:
            raise ValueError("unknown capability status")
        if self.effect not in EFFECTS:
            raise ValueError("unknown effect")
        if type(self.cost_units) is not int or self.cost_units <= 0:
            raise ValueError("cost_units must be a positive integer")
        if not isinstance(self.evidence_ref, str):
            raise TypeError("evidence_ref must be a string")


class CapabilityRegistry:
    """In-memory contract inventory. No plugin imports or remote execution."""

    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if capability.capability_id in self._items:
            raise ValueError(f"duplicate capability: {capability.capability_id}")
        self._items[capability.capability_id] = capability

    def list_all(self) -> tuple[Capability, ...]:
        return tuple(self._items[k] for k in sorted(self._items))


@dataclass(frozen=True)
class PlanResult:
    status: str
    capability_ids: tuple[str, ...]
    acquired_types: frozenset[str]
    missing_types: frozenset[str]
    expanded_states: int
    total_cost_units: int

    @property
    def executable(self) -> bool:
        # READY means structurally routable, not that a tool was run.
        return self.status == "READY"


def plan_capabilities(
    registry: CapabilityRegistry,
    *,
    available_types: Iterable[str],
    goal_types: Iterable[str],
    allowed_effects: Iterable[str] = ("none", "read"),
    max_steps: int = 12,
    max_expansions: int = 1000,
    max_cost_units: int = 100,
) -> PlanResult:
    """Find a minimum-cost composition with explicit resource and effect bounds.

    Verified capabilities require a nonblank evidence reference. Evidence
    provenance is NOT independently authenticated by this function.
    Candidate actions only add typed outputs; no claims about semantic truth.
    """
    start = _tokens(available_types, "available_types")
    goals = _tokens(goal_types, "goal_types")
    effects = frozenset(allowed_effects)
    if not goals:
        raise ValueError("goal_types must be nonempty")
    if not effects or not effects.issubset(EFFECTS):
        raise ValueError("allowed_effects must be a nonempty subset of EFFECTS")
    for label, value in (
        ("max_steps", max_steps),
        ("max_expansions", max_expansions),
        ("max_cost_units", max_cost_units),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(f"{label} must be a positive integer")

    if goals.issubset(start):
        return PlanResult("READY", (), start, frozenset(), 0, 0)

    eligible = [
        c for c in registry.list_all()
        if c.status == "VERIFIED" and c.evidence_ref.strip() and c.effect in effects
    ]
    # Uniform-cost search. Equal costs are broken deterministically by step
    # count and capability IDs, independent of registry insertion order.
    heap: list[tuple[int, int, tuple[str, ...], frozenset[str]]] = [(0, 0, (), start)]
    best: dict[frozenset[str], tuple[int, int]] = {start: (0, 0)}
    expansions = 0
    hit_limit = False
    best_seen = start
    best_remaining = len(goals - start)

    while heap:
        cost, steps, path, held = heapq.heappop(heap)
        if best.get(held) != (cost, steps):
            continue
        if goals.issubset(held):
            return PlanResult("READY", path, held, frozenset(), expansions, cost)

        if expansions >= max_expansions:
            hit_limit = True
            break
        expansions += 1

        remainder = len(goals - held)
        if remainder < best_remaining:
            best_seen, best_remaining = held, remainder

        for cap in eligible:
            if not cap.consumes.issubset(held) or cap.produces.issubset(held):
                continue
            next_cost = cost + cap.cost_units
            next_steps = steps + 1
            if next_steps > max_steps or next_cost > max_cost_units:
                hit_limit = True
                continue
            acquired = held | cap.produces
            old = best.get(acquired)
            if old is not None and old <= (next_cost, next_steps):
                continue
            best[acquired] = (next_cost, next_steps)
            heapq.heappush(heap, (next_cost, next_steps, path + (cap.capability_id,), acquired))

    return PlanResult(
        status="SEARCH_LIMIT" if hit_limit else "NO_PLAN",
        capability_ids=(),
        acquired_types=best_seen,
        missing_types=goals - best_seen,
        expanded_states=expansions,
        total_cost_units=0,
    )
