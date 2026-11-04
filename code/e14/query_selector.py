"""Select one input using only two fitted typed programs and unlabelled inputs."""

import random
from dataclasses import dataclass
from time import perf_counter_ns, process_time_ns

from e13.contract import input_value, read_json
from e13.dsl import FuelExhausted, predict
from e13.evaluator.selection_budget import SelectionFuel

MAX_INPUTS = 8
QUERY_STEPS = 20_000
QUERY_CPU_US = 100_000
QUERY_WALL_US = 250_000


@dataclass(frozen=True)
class Choice:
    index: int
    disagreements: tuple[int, ...]
    reason: str
    steps: int
    cpu_us: int
    wall_us: int


def choose_query(counter, order, pool, *, seed):
    if (not 1 <= len(pool) <= MAX_INPUTS or any(type(value) is not bytes for value in pool)
            or len(set(pool)) != len(pool)):
        raise ValueError("query pool requires distinct unlabelled inputs")
    if counter.program.family != order.program.family:
        raise ValueError("query hypotheses must use the same family")
    cpu, wall = process_time_ns(), perf_counter_ns()
    for value in pool:
        input_value(counter.program.family, read_json(value, 4_096))

    rng = random.Random(seed)
    fallback = rng.randrange(len(pool))
    fuel = SelectionFuel(QUERY_STEPS, cpu + QUERY_CPU_US * 1_000, wall + QUERY_WALL_US * 1_000)
    disagreements = []
    reason = "initial_fit_not_exact"
    index = fallback
    if counter.status == order.status == "fit":
        try:
            for i, value in enumerate(pool):
                a = predict(counter.program.ast, value, fuel, allow_extension=True)
                b = predict(order.program.ast, value, fuel, allow_extension=True)
                if a != b:
                    disagreements.append(i)
            fuel.check_time()
        except FuelExhausted:
            disagreements.clear()
            reason = "query_budget_exhausted"
        else:
            reason = "disagreement" if disagreements else "agreement"
            if disagreements:
                index = rng.choice(disagreements)
    return Choice(index, tuple(disagreements), reason, fuel.used,
                  (process_time_ns() - cpu) // 1_000, (perf_counter_ns() - wall) // 1_000)
