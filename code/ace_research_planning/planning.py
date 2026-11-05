"""ACE R6: deterministic, bounded planning on procedural locked-room graphs.

Closed state/action interpreter only; never executes synthesized code. Python 3.10+.
All environments are explicitly author-created PUBLIC synthetic development tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappush, heappop
from collections import deque
import random
from typing import Optional


@dataclass(frozen=True)
class World:
    width: int
    height: int
    adjacency: tuple[tuple[int, ...], ...]
    weights: tuple[tuple[int, int, int], ...]
    keys: tuple[int, ...]
    shock: Optional[tuple[int, int]] = None
    locks: Optional[tuple[int, ...]] = None

    @property
    def goal(self) -> int:
        return self.width * self.height - 1

    @property
    def all_keys(self) -> int:
        return (1 << len(self.keys)) - 1

    def cost(self, u: int, v: int) -> int:
        a, b = sorted((u, v))
        for x, y, cost in self.weights:
            if x == a and y == b:
                return cost
        raise ValueError("nonexistent edge")

    def requirement(self, u: int, v: int) -> int:
        # Crossing column j -> j+1 requires key j, when that key exists.
        c1, c2 = u % self.width, v % self.width
        boundary = min(c1, c2)
        active = range(len(self.keys)) if self.locks is None else self.locks
        if c1 != c2 and boundary in active:
            return 1 << boundary
        return 0


@dataclass
class Meter:
    limit: int
    expanded: int = 0
    heuristic_calls: int = 0
    peak_frontier: int = 0
    calls: int = 0
    exhausted: bool = False


@dataclass(frozen=True)
class SearchResult:
    route: Optional[tuple[int, ...]]
    cost: Optional[int]


def xy_distance(world: World, a: int, b: int) -> int:
    return abs(a % world.width - b % world.width) + abs(a // world.width - b // world.width)


def heuristic(world: World, pos: int, mask: int, target: Optional[int]) -> int:
    if target is not None:
        return xy_distance(world, pos, target)
    points = [world.keys[i] for i in range(len(world.keys)) if not mask & (1 << i)]
    points.append(world.goal)
    # Manhattan MST + agent-to-nearest: admissible path lower bound.
    nearest = min(xy_distance(world, pos, p) for p in points)
    seen = {0}
    mst = 0
    while len(seen) < len(points):
        d, j = min((xy_distance(world, points[i], points[j]), j)
                   for i in seen for j in range(len(points)) if j not in seen)
        seen.add(j)
        mst += d
    return nearest + mst


def search(world: World, start: tuple[int, int], blocked: frozenset[tuple[int, int]],
           mode: str, meter: Meter, target: Optional[int] = None) -> SearchResult:
    """Find an action route. `target=None` means all keys + final goal.

    Targeted search can collect intermediate keys. Search's own only information
    is World minus observed blocked edges, never World.shock.
    """
    if mode not in {"astar", "greedy", "bfs", "dijkstra"}:
        raise ValueError("unknown algorithm")
    if meter.limit < 0:
        raise ValueError("negative budget")
    meter.calls += 1

    def done(st: tuple[int, int]) -> bool:
        if target is None:
            return st[0] == world.goal and st[1] == world.all_keys
        return st[0] == target

    def h(st: tuple[int, int]) -> int:
        meter.heuristic_calls += 1
        return heuristic(world, st[0], st[1], target)

    if done(start):
        return SearchResult((), 0)
    best = {start: 0}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    serial = 0
    if mode == "bfs":
        frontier = deque([(start, 0)])
    else:
        priority = h(start) if mode in {"astar", "greedy"} else 0
        frontier = [(priority, serial, start, 0)]
    expanded_cost: dict[tuple[int, int], int] = {}
    while frontier:
        meter.peak_frontier = max(meter.peak_frontier, len(frontier))
        if mode == "bfs":
            st, dist = frontier.popleft()
        else:
            _, _, st, dist = heappop(frontier)
        if best[st] != dist or dist >= expanded_cost.get(st, float("inf")):
            continue
        if meter.expanded >= meter.limit:
            meter.exhausted = True
            return SearchResult(None, None)
        expanded_cost[st] = dist
        meter.expanded += 1
        if done(st):
            route = []
            cur = st
            while cur != start:
                route.append(cur[0])
                cur = parent[cur]
            route.reverse()
            return SearchResult(tuple(route), dist)
        pos, mask = st
        for nxt in world.adjacency[pos]:
            if tuple(sorted((pos, nxt))) in blocked:
                continue
            requirement = world.requirement(pos, nxt)
            if requirement and not (mask & requirement):
                continue
            nmask = mask
            for i, node in enumerate(world.keys):
                if node == nxt:
                    nmask |= 1 << i
            ns = (nxt, nmask)
            step = world.cost(pos, nxt)
            nd = dist + step
            # For BFS and greedy, first-discovered state is used; A*/Dijkstra
            # may reopen cheaper paths (with positive weights).
            if mode in {"bfs", "greedy"}:
                if ns in best:
                    continue
            elif nd >= best.get(ns, float("inf")):
                continue
            best[ns] = nd
            parent[ns] = st
            if mode == "bfs":
                frontier.append((ns, nd))
            else:
                serial += 1
                score = nd if mode == "dijkstra" else (nd + h(ns) if mode == "astar" else h(ns))
                heappush(frontier, (score, serial, ns, nd))
    return SearchResult(None, None)


def hierarchical_route(world: World, state: tuple[int, int],
                       blocked: frozenset[tuple[int, int]], meter: Meter) -> SearchResult:
    pos, mask = state
    remaining = [i for i in range(len(world.keys)) if not mask & (1 << i)]
    if not remaining:
        return search(world, state, blocked, "astar", meter, world.goal)
    # Choose nearest physically reachable key (not necessarily globally optimal).
    candidates = sorted(remaining, key=lambda i: (xy_distance(world, pos, world.keys[i]), i))
    for idx in candidates:
        route = search(world, state, blocked, "astar", meter, world.keys[idx])
        if route.route is not None:
            return route
        if meter.exhausted:
            break
    return SearchResult(None, None)


def forced_key_order_certificate(world: World) -> bool:
    """Sufficient (not necessary) structural certificate for ordered subgoals.

    Every key i is in column i and boundary i is gated by key i.
    Starting at column zero, key j cannot be reached before keys < j.
    Does not claim that a hierarchical policy is optimal for arbitrary graphs.
    """
    k = len(world.keys)
    return (0 < k < world.width
            and tuple(range(k)) == (tuple(range(k)) if world.locks is None else world.locks)
            and all(node % world.width == i for i, node in enumerate(world.keys)))


def structural_route(world: World, state: tuple[int, int],
                     blocked: frozenset[tuple[int, int]], meter: Meter) -> tuple[SearchResult, str]:
    """Use forced-dependency structure, otherwise guard expensive global A*.

    This is a fixed researcher-written policy, not a learned reasoning system.
    The gate is conservative, keeping a feasible hierarchical search available
    under small caps. The threshold is set from a public state-space bound,
    not from test or OOD results.
    """
    if forced_key_order_certificate(world):
        missing = next((i for i in range(len(world.keys))
                        if not state[1] & (1 << i)), None)
        target = world.goal if missing is None else world.keys[missing]
        return search(world, state, blocked, "astar", meter, target), "certified_subgoal"
    remaining = meter.limit - meter.expanded
    upper_states = world.width * world.height * (1 << len(world.keys))
    # Deterministic resource rule. Never attempt costly full-state A* if the
    # remaining budget is small relative to the finite state space.
    if remaining >= 2 * upper_states:
        return search(world, state, blocked, "astar", meter), "global_astar"
    return hierarchical_route(world, state, blocked, meter), "hierarchical_fallback"


def simulate(world: World, method: str, limit: int = 1800) -> dict:
    """Single environment rollout with a TOTAL per-agent search expansion cap.

    `shock` is hidden to every planner. It removes a physical edge after a plan
    is constructed; only failed attempted actions expose it. Full-state oracle
    and benchmark generation never pass shock information to search.
    """
    if method not in {"bfs", "greedy", "astar", "hier_fixed", "hier_replan", "adaptive", "structural"}:
        raise ValueError("unknown method")
    meter = Meter(limit)
    state = (0, 0)
    # Pickup at start is possible in general worlds, although generated keys avoid it.
    for i, node in enumerate(world.keys):
        if node == 0:
            state = (0, state[1] | (1 << i))
    revealed: set[tuple[int, int]] = set()
    pending: list[int] = []
    actions = failures = replans = switches = 0
    paid_cost = 0
    structural_choices: list[str] = []
    terminated = "step_cap"
    for _ in range(4 * world.width * world.height * (len(world.keys) + 1)):
        if state == (world.goal, world.all_keys):
            terminated = "success"
            break
        if not pending:
            blocked = frozenset(revealed)
            if method == "structural":
                plan, choice = structural_route(world, state, blocked, meter)
                if structural_choices and structural_choices[-1] != choice:
                    switches += 1
                structural_choices.append(choice)
            elif method in {"hier_fixed", "hier_replan"} or (method == "adaptive" and switches == 0):
                plan = hierarchical_route(world, state, blocked, meter)
            else:
                plan = search(world, state, blocked, method if method in {"bfs", "greedy", "astar"} else "astar", meter)
            if plan.route is None:
                terminated = "budget" if meter.exhausted else "no_plan"
                break
            if not plan.route:
                terminated = "no_progress"
                break
            pending = list(plan.route)
        nxt = pending.pop(0)
        edge = tuple(sorted((state[0], nxt)))
        if edge == world.shock:
            failures += 1
            revealed.add(edge)
            pending = []
            if method == "hier_fixed":
                terminated = "unexpected_change"
                break
            replans += 1
            if method == "adaptive" and switches == 0:
                switches += 1
            continue
        requirement = world.requirement(state[0], nxt)
        if nxt not in world.adjacency[state[0]] or (requirement and not state[1] & requirement):
            terminated = "illegal_transition"
            break
        mask = state[1]
        for i, node in enumerate(world.keys):
            if node == nxt:
                mask |= 1 << i
        paid_cost += world.cost(state[0], nxt)
        actions += 1
        state = (nxt, mask)
    else:
        if state == (world.goal, world.all_keys):
            terminated = "success"
    output = dict(status=terminated, success=terminated == "success", cost=paid_cost,
                  actions=actions, failed_actions=failures, replans=replans, switches=switches,
                  expanded=meter.expanded, heuristics=meter.heuristic_calls,
                  frontier_peak=meter.peak_frontier, search_calls=meter.calls,
                  budget=limit, collected=state[1].bit_count(),
                  shock_encountered=failures > 0)
    if method == "structural":
        output["strategy_trace"] = structural_choices
    return output


def oracle_cost(world: World, blocked: frozenset[tuple[int, int]] = frozenset()) -> Optional[int]:
    meter = Meter(10_000_000)
    result = search(world, (0, 0), blocked, "dijkstra", meter)
    return result.cost


def generate(seed: int, family: str = "dev", shock: bool = False) -> World:
    """Disjoint deterministic families; reject if no fully solvable graph.

    dev: 4-5 by 4, 2 keys, moderate deletions.
    ood: 7-8 by 5-6, 3-4 keys, more deletions / deeper prerequisites.
    """
    if family not in {"dev", "ood"}:
        raise ValueError("unknown family")
    rng = random.Random(seed)
    for _ in range(300):
        width = rng.choice((4, 5)) if family == "dev" else rng.choice((7, 8))
        height = 4 if family == "dev" else rng.choice((5, 6))
        numkeys = 2 if family == "dev" else rng.choice((3, 4))
        delete_prob = 0.10 if family == "dev" else 0.19
        open_task = family == "ood" and seed % 2 == 0
        if open_task:
            keys = tuple(rng.sample(range(1, width * height - 1), numkeys))
            locks = ()
        else:
            keys = tuple(rng.randrange(height) * width + i for i in range(numkeys))
            locks = tuple(range(numkeys))
        if 0 in keys:
            continue
        neighbors = [set() for _ in range(width * height)]
        weights: list[tuple[int, int, int]] = []
        for u in range(width * height):
            for v in (u + 1, u + width):
                if v >= width * height or (v == u + 1 and u // width != v // width):
                    continue
                if rng.random() < delete_prob:
                    continue
                neighbors[u].add(v)
                neighbors[v].add(u)
                weights.append((u, v, rng.randint(1, 5)))
        world = World(width, height, tuple(tuple(sorted(n)) for n in neighbors), tuple(weights), keys, locks=locks)
        if oracle_cost(world) is None:
            continue
        if not shock:
            return world
        # Pick a common, outcome-independent perturbation from the *first* route
        # of the fixed hierarchical policy; independently verify a route remains.
        meter = Meter(100000)
        first = hierarchical_route(world, (0, 0), frozenset(), meter).route or ()
        previous = 0
        possible = []
        for nxt in first:
            edge = tuple(sorted((previous, nxt)))
            if oracle_cost(world, frozenset((edge,))) is not None:
                possible.append(edge)
            previous = nxt
        if possible:
            return World(width, height, world.adjacency, world.weights, keys, possible[0], locks)
    raise RuntimeError(f"cannot generate {family} task for seed={seed}, shock={shock}")
