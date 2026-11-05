"""R6-v6: bounded empirical-Bayes value-of-sensing (public synthetic only).

Only training-world labels fit the posterior. Runtime deciders receive the
shock-redacted world and earlier observations; no planner has oracle access.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from .online_v5 import PROBE_WORK_UNITS, OnlinePolicy, rollout, visible_world
from .planning import World

PROBE_PRICE = 0.5
WORK_PRICE = 0.04
FAILED_ACTION_PRICE = 6.0
# The environment may have at most one hidden blocked edge. The public salience
# rule is researcher-designed, not discovered by ACE.
SALIENCE_SIZE = 3
POLICIES = ("learned_voi", "never", "always", "salient", "global_voi", "anti_salient")


def salience(world: World) -> frozenset[tuple[int, int]]:
    """Top-3 visible salient edges; independent of contestant route/outcome.

    Cheap/fragile/nonlocal edges are prioritized using fixed features. The
    ranking does not consult World.shock, future sensing or outcome labels.
    """
    def score(item: tuple[int, int, int]) -> tuple:
        u, v, cost = item
        x = abs(u % world.width - v % world.width)
        y = abs(u // world.width - v // world.width)
        fragility = int(min(len(world.adjacency[u]), len(world.adjacency[v])) <= 2)
        return (int(cost <= 2), fragility, int(x + y > 1), -cost, -u, -v)
    return frozenset((u, v) for u, v, cost in sorted(world.weights, key=score, reverse=True)[:SALIENCE_SIZE])


@dataclass(frozen=True)
class RiskModel:
    risk_salient: float
    risk_other: float
    shock_frequency: float
    train_worlds: int
    train_positive: int
    train_edge_counts: tuple[int, int]

    def __post_init__(self):
        for p in (self.risk_salient, self.risk_other, self.shock_frequency):
            if not 0.0 < p < 1.0:
                raise ValueError("out-of-range probability")
        if self.train_worlds < 1:
            raise ValueError("empty training")

    def export(self) -> dict:
        return vars(self).copy()


def fit_risk(worlds: tuple[World, ...]) -> RiskModel:
    """Only training worlds; Beta(1,19) per-class smoothing, Beta(1,1) shock rate."""
    if not worlds:
        raise ValueError("no training evidence")
    count = [0, 0]
    positive = [0, 0]
    for world in worlds:
        top = salience(visible_world(world))
        for u, v, _ in world.weights:
            bucket = 0 if (u, v) in top else 1
            count[bucket] += 1
            positive[bucket] += int((u, v) == world.shock)
    shock_count = sum(w.shock is not None for w in worlds)
    return RiskModel((positive[0] + 1) / (count[0] + 20),
                     (positive[1] + 1) / (count[1] + 20),
                     (shock_count + 1) / (len(worlds) + 2),
                     len(worlds), shock_count, (count[0], count[1]))


def edge_priors(model: RiskModel, world: World) -> dict[tuple[int, int], float]:
    public = visible_world(world)
    top = salience(public)
    scores = {(u, v): (model.risk_salient if (u, v) in top else model.risk_other)
              for u, v, _ in public.weights}
    normalizer = sum(scores.values())
    if normalizer <= 0:
        raise ValueError("no edges")
    return {e: model.shock_frequency * p / normalizer for e, p in scores.items()}


def make_decider(method: str, model: RiskModel | None = None) -> Callable:
    """Return one policy callback. All online decisions use redacted observations.

    Declared metering is a proxy, not machine instructions: every callback pays
    one work unit in rollout; feature-building pays ceil(E/4), and conditioning
    pays floor(number of prior open observations / 4) additional units.
    """
    if method not in POLICIES:
        raise ValueError("unknown method")
    if method in {"learned_voi", "global_voi"} and model is None:
        raise ValueError("missing fitted model")
    initialized = False
    top: frozenset[tuple[int, int]] = frozenset()
    prior: dict[tuple[int, int], float] = {}

    def decide(public: World, u: int, v: int, steps: int, discovered: bool,
               known_open: frozenset[tuple[int, int]],
               closed: frozenset[tuple[int, int]]) -> tuple[bool, int]:
        nonlocal initialized, top, prior
        if public.shock is not None:
            raise ValueError("information boundary crossed")
        extra = 0
        if not initialized:
            if method in {"learned_voi", "salient", "anti_salient"}:
                top = salience(public)
                extra = (len(public.weights) + 3) // 4
            if method == "learned_voi":
                prior = edge_priors(model, public)  # type: ignore[arg-type]
            elif method == "global_voi":
                prior = { (u0, v0): model.shock_frequency / len(public.weights)  # type: ignore[union-attr]
                         for u0, v0, _ in public.weights }
                extra = (len(public.weights) + 3) // 4
            initialized = True
        edge = tuple(sorted((u, v)))
        if discovered or edge in known_open or edge in closed:
            return False, extra
        if method == "never":
            return False, extra
        if method == "always":
            return True, extra
        if method == "salient":
            return edge in top, extra
        if method == "anti_salient":
            return edge not in top, extra
        # Posterior mass is conditional on all observed-open edges; one-shock model.
        discarded = sum(prior.get(e, 0) for e in known_open)
        normalizer = max(1 - discarded, 1e-9)
        probability = min(1.0, prior[edge] / normalizer)
        extra += len(known_open) // 4
        return probability * FAILED_ACTION_PRICE > (PROBE_PRICE + PROBE_WORK_UNITS * WORK_PRICE), extra

    return decide


def run_policy(world: World, method: str, model: RiskModel | None, work_limit: int) -> dict:
    return rollout(world, OnlinePolicy("never", "hier"), work_limit=work_limit,
                   decision_fn=make_decider(method, model))


def utility(result: dict, reference: int) -> float:
    """Same main utility as R6-v5; route reference is evaluator-only."""
    if result["success"]:
        return 1000 - 120 * (result["travel_cost"] / reference - 1) \
               - WORK_PRICE * result["work_units"] - FAILED_ACTION_PRICE * result["failed_actions"] \
               - PROBE_PRICE * result["probes"]
    return -200 - WORK_PRICE * result["work_units"] \
           - FAILED_ACTION_PRICE * result["failed_actions"] - PROBE_PRICE * result["probes"]
