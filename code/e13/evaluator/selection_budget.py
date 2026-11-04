"""Apply the same fit and prediction budget to each selection arm."""

import json
from dataclasses import asdict
from time import perf_counter_ns, process_time_ns

from ..contract import canonical_json, parse_fit_request
from ..dsl import Fuel, FuelExhausted, predict
from ..extension import POLICIES as EXTENSION_POLICIES
from ..isolation import fit_isolated
from .pilot import summarize_outcomes

TOTAL_STEPS = 100_000
FIT_STEPS = 75_000
CPU_US = 1_000_000
WALL_US = 3_000_000
LIMITS = {"total_steps": TOTAL_STEPS, "fit_steps": FIT_STEPS,
          "fit_and_predict_cpu_us": CPU_US, "fit_and_predict_wall_us": WALL_US}


class SelectionFuel(Fuel):
    def __init__(self, limit, cpu_deadline, wall_deadline):
        super().__init__(limit)
        self.cpu_deadline = cpu_deadline
        self.wall_deadline = wall_deadline

    def check_time(self):
        if process_time_ns() >= self.cpu_deadline or perf_counter_ns() >= self.wall_deadline:
            raise FuelExhausted("selection compute budget reached")

    def spend(self):
        self.check_time()
        super().spend()


def evaluate_arm(episode, policy):
    """Fit with visible demos, then score a frozen AST against private probes."""
    raw = json.loads(episode.fit_request)
    raw["fuel"] = FIT_STEPS
    request = parse_fit_request(canonical_json(raw))
    started = perf_counter_ns()
    fit = fit_isolated(canonical_json(raw), policy=policy)
    cpu_start = process_time_ns()
    budget = SelectionFuel(
        TOTAL_STEPS - fit.steps,
        cpu_start + (CPU_US - fit.metrics.cpu_us) * 1_000,
        started + WALL_US * 1_000,
    )
    outcomes = {}
    capped = False
    for size, probes in (("ordinary", episode.in_distribution),
                         ("extrapolation", episode.extrapolation)):
        matches = []
        for probe in probes:
            if not capped:
                try:
                    budget.check_time()
                    answer = predict(fit.program.ast, probe.input, budget,
                                     allow_extension=policy in EXTENSION_POLICIES)
                    budget.check_time()
                except FuelExhausted:
                    capped = True
            matches.append(None if capped else answer == probe.expected)
        outcomes[size] = matches
    predict_cpu = (process_time_ns() - cpu_start) // 1_000
    arm_cpu = fit.metrics.cpu_us + predict_cpu
    arm_wall = (perf_counter_ns() - started) // 1_000
    if arm_cpu > CPU_US or arm_wall > WALL_US:
        outcomes = {size: [None] * len(matches) for size, matches in outcomes.items()}
        capped = True
    return {
        "task_id": request.task_id, "family": episode.family, "regime": episode.regime,
        "policy": policy, "ast_sha256": fit.program.sha256, "fit_status": fit.status,
        "fit": asdict(fit.metrics), "fit_steps": fit.steps, "proposals": fit.candidates,
        "predict_cpu_us": predict_cpu, "total_cpu_us": arm_cpu, "wall_us": arm_wall,
        "predict_steps": budget.used, "cap_reached": capped,
        "scores": {size: summarize_outcomes(values) for size, values in outcomes.items()},
    }
