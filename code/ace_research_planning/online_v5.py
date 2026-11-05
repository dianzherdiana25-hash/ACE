"""ACE R6-v5: safe, bounded online probe/replan experiment.

An experiment controller alone accesses World.shock. Planners see a shock-redacted
World, an observed-edge set and accumulated public failure/probe observations.
No external effects, network calls, generated executable code or agents.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from .planning import (Meter, WorkBudgetExceeded, World, hierarchical_route,
                       search, xy_distance)

PROBE_MODES = ("never", "always", "heavy", "portal", "fragile", "early")
PLANNER_MODES = ("hier", "dijkstra", "after_discovery_dijkstra")
PROBE_WORK_UNITS = 2


@dataclass(frozen=True)
class OnlinePolicy:
    probe: str
    planner: str

    def __post_init__(self) -> None:
        if self.probe not in PROBE_MODES or self.planner not in PLANNER_MODES:
            raise ValueError("unknown online policy")

    def export(self) -> dict[str, str]:
        return {"probe": self.probe, "planner": self.planner}


def visible_world(world: World) -> World:
    """Planner view redacts future/actual shock; topology is otherwise public."""
    return replace(world, shock=None)


def should_probe(policy: OnlinePolicy, visible: World, u: int, v: int,
                 successful_steps: int, discovered: bool, known_open: set[tuple[int, int]]) -> bool:
    """Decision uses only visible structure and *past* observations.

    A world has at most one hidden closure; after discovery future probes are
    strictly dominated, since every other edge remains open in this model.
    """
    edge = tuple(sorted((u, v)))
    if discovered or edge in known_open:
        return False
    if policy.probe == "never":
        return False
    if policy.probe == "always":
        return True
    if policy.probe == "heavy":
        return visible.cost(u, v) >= 4
    if policy.probe == "portal":
        return xy_distance(visible, u, v) > 1
    if policy.probe == "fragile":
        return min(len(visible.adjacency[u]), len(visible.adjacency[v])) <= 2
    if policy.probe == "early":
        return successful_steps < 6
    raise AssertionError("unreachable probe mode")


def rollout(world: World, policy: OnlinePolicy, work_limit: int = 300,
            expansion_limit: int = 1800) -> dict:
    """Execute bounded online decisions, discovering one hidden edge by action/probe.

    Work cost counts previous v4 instrumented planning work plus two charged
    events per probe. Route construction uses actual previous observations only.
    Failure penalty is separately recorded; there is no free retry or reset.
    """
    if isinstance(work_limit, bool) or not isinstance(work_limit, int) or work_limit < 1:
        raise ValueError("work_limit must be a positive integer")
    if isinstance(expansion_limit, bool) or not isinstance(expansion_limit, int) or expansion_limit < 1:
        raise ValueError("expansion_limit must be a positive integer")
    if not isinstance(policy, OnlinePolicy):
        raise ValueError("policy must be OnlinePolicy")
    public = visible_world(world)
    hidden_shock: Optional[tuple[int, int]] = world.shock
    meter = Meter(expansion_limit, work_limit=work_limit)
    held = sum((1 << i) for i, node in enumerate(public.keys) if node == 0)
    state = (0, held)
    closed: set[tuple[int, int]] = set()
    known_open: set[tuple[int, int]] = set()
    route: list[int] = []
    steps = paid_cost = probes = positive_probes = failures = discoveries = 0
    replans = switches = 0
    trace: list[dict] = []
    status = "step_cap"
    last_method: Optional[str] = None
    cap = 4 * public.width * public.height * (len(public.keys) + 1)
    for _ in range(cap):
        if state == (public.goal, public.all_keys):
            status = "success"
            break
        if not route:
            if policy.planner == "dijkstra":
                mode = "dijkstra"
            elif policy.planner == "after_discovery_dijkstra" and discoveries:
                mode = "dijkstra"
            else:
                mode = "hier"
            if last_method is not None and mode != last_method:
                switches += 1
            last_method = mode
            try:
                plan = (hierarchical_route(public, state, frozenset(closed), meter)
                        if mode == "hier" else
                        search(public, state, frozenset(closed), "dijkstra", meter))
            except WorkBudgetExceeded:
                status = "work_budget"
                break
            if plan.route is None:
                status = "expansion_budget" if meter.exhausted else "unreachable"
                break
            if not plan.route:
                status = "no_progress"
                break
            route = list(plan.route)
            replans += 1
        u, v = state[0], route[0]
        edge = tuple(sorted((u, v)))
        if (v not in public.adjacency[u] or edge in closed or
                (public.requirement(u, v) and not (state[1] & public.requirement(u, v)))):
            status = "invalid_action"
            break
        if should_probe(policy, public, u, v, steps, bool(discoveries), known_open):
            try:
                meter.charge(PROBE_WORK_UNITS)
            except WorkBudgetExceeded:
                status = "work_budget"
                break
            probes += 1
            if edge == hidden_shock:
                positive_probes += 1
                discoveries += 1
                closed.add(edge)
                trace.append(dict(event="probe_blocked", step=steps, edge=list(edge)))
                route = []
                continue
            known_open.add(edge)
        if edge == hidden_shock:
            failures += 1
            discoveries += 1
            closed.add(edge)
            trace.append(dict(event="action_blocked", step=steps, edge=list(edge)))
            route = []
            continue
        route.pop(0)
        mask = state[1]
        for i, node in enumerate(public.keys):
            if node == v:
                mask |= 1 << i
        state = (v, mask)
        paid_cost += public.cost(u, v)
        steps += 1
    else:
        if state == (public.goal, public.all_keys):
            status = "success"
    return dict(status=status, success=status == "success", travel_cost=paid_cost,
                steps=steps, probes=probes, positive_probes=positive_probes,
                failed_actions=failures, discoveries=discoveries,
                encountered=bool(discoveries), recovered=bool(discoveries) and status == "success",
                replans=replans, switches=switches, expanded=meter.expanded,
                heuristic_calls=meter.heuristic_calls, work_units=meter.work_units,
                work_limit=work_limit, search_calls=meter.calls,
                trace=trace)
