"""Grid generalization universe (Phase 2, stage F).

The stage-C substrate (PR #125) solves 58/58 tasks whose defect
classes its operators were authored against. The official question
of this universe is whether that is *generalization* or *catalog
memorization*: the holdout defects below are new classes that no
substrate v1 operator touches — a doubled step cost, an off-by-one
row bound, a return of the start cell's distance, and a wall test
against the wrong character literal (same symptom family as
walls_passable, different mechanism).

Arms mirror the A/B/C pilot semantics on the grid substrate:
A fixed catalog order, B adaptive (operator order learned on the
train split), C evolutionary (operator subset+order evolved on the
train split). All learning is confined to train tasks carrying
*catalog* defects; every arm is frozen before holdout.

Endpoints (preregistered): primary — full-solve rate on the
new-only holdout subset per arm; secondary — full-solve on the
mixed subset, mean holdout-case fraction (partial credit) per
subset, and the catalog-control solve rate (pipeline validity).
"""
from __future__ import annotations

import itertools
import random
from typing import Any

from .curriculum_lab import _GRID_SETS, _NAVIGATE_REFERENCE
from .grid_substrate import _OPERATORS, solve_grid
from .reasoning_lab import Budget

# --- defect maps -----------------------------------------------------

def _catalog_defects() -> dict[str, Any]:
    def walls_passable(code):
        return code.replace(' and grid[nr][nc] != "#"', "")

    def start_offset(code):
        return code.replace("dist[sr][sc] = 0", "dist[sr][sc] = 1")

    def no_up(code):
        return code.replace("(-1, 0), ", "", 1)

    def diagonal_moves(code):
        return code.replace(
            "((1, 0), (-1, 0), (0, 1), (0, -1))",
            "((1, 0), (-1, 0), (0, 1), (0, -1), "
            "(1, 1), (1, -1), (-1, 1), (-1, -1))")

    return {"walls_passable": walls_passable,
            "start_offset": start_offset, "no_up": no_up,
            "diagonal_moves": diagonal_moves}


def _new_defects() -> dict[str, Any]:
    """Holdout classes absent from the substrate v1 catalog."""

    def dist_step_2(code):
        return code.replace("dist[nr][nc] = dist[r][c] + 1",
                            "dist[nr][nc] = dist[r][c] + 2")

    def bounds_off_by_one(code):
        return code.replace("0 <= nr < rows", "0 <= nr < rows - 1")

    def returns_start_distance(code):
        return code.replace("return dist[gr][gc]",
                            "return dist[sr][sc]")

    def wall_char_x(code):
        return code.replace('grid[nr][nc] != "#"', 'grid[nr][nc] != "X"')

    return {"dist_step_2": dist_step_2,
            "bounds_off_by_one": bounds_off_by_one,
            "returns_start_distance": returns_start_distance,
            "wall_char_x": wall_char_x}


CATALOG_DEFECTS = _catalog_defects()
NEW_DEFECTS = _new_defects()
ALL_DEFECTS = {**CATALOG_DEFECTS, **NEW_DEFECTS}
OPERATOR_NAMES = ("wall_guard", "directions", "start_offset")
_OP_BY_NAME = dict(zip(OPERATOR_NAMES, _OPERATORS))


def _apply(code: str, names: tuple[str, ...]) -> str:
    for name in names:
        code = ALL_DEFECTS[name](code)
    return code


def _run(code: str, case: tuple) -> Any:
    """Execute one navigate case; errors become a sentinel value so a
    crashing candidate simply fails its cases (lab code only)."""
    try:
        namespace: dict[str, Any] = {}
        exec(compile(code, "<gridgen>", "exec"), namespace)
        return namespace["navigate"](*case)
    except Exception as exc:  # noqa: BLE001 - sentinel by design
        return ("__error__", type(exc).__name__)


# --- shown-set identifiability (generic R1/R2) ------------------------

def _passes(code: str, cases: list[tuple], truth: list) -> int:
    return sum(1 for case, want in zip(cases, truth)
               if _run(code, case) == want)


def _gradient_path(partials: dict[frozenset, str], remaining: frozenset,
                   shown: list[tuple], truth: list) -> bool:
    """Statement B: some single-defect removal improves the shown
    score now, or ties while a recursive path exists beneath it."""
    if not remaining:
        return True
    current = _passes(partials[remaining], shown, truth)
    for defect in remaining:
        reduced = remaining - {defect}
        score = _passes(partials[reduced], shown, truth)
        if score > current:
            return True
        if score == current and _gradient_path(partials, reduced,
                                               shown, truth):
            return True
    return False


def identifiable_shown(defect_names: tuple[str, ...],
                       cases: list[tuple], truth: list,
                       buggy: str) -> list[tuple] | None:
    """Largest shown subset of the buggy-failing cases satisfying
    R1 (every partial fix fails somewhere shown) and R2 (a gradient
    path exists), or None.

    v1 of this universe took the *smallest* identifiable set; the
    preregistered validity gate caught the flaw (catalog control
    47% < 80%): a 1–2 case shown set satisfies the letter of R1/R2
    over defect-removal programs but starves the operator-level
    greedy search of gradient. Identifiability is a floor, not a
    target — v2 maximises signal subject to it."""
    failing = [case for case, want in zip(cases, truth)
               if _run(buggy, case) != want]
    if not failing:
        return None
    partials: dict[frozenset, str] = {}
    for size in range(0, len(defect_names)):
        for subset in itertools.combinations(defect_names, size):
            partials[frozenset(subset)] = _apply(_NAVIGATE_REFERENCE,
                                                 tuple(subset))
    full = frozenset(defect_names)
    partials[full] = buggy
    for size in range(min(8, len(failing)), 0, -1):
        for shown in itertools.combinations(failing, size):
            shown = list(shown)
            if len(defect_names) > 1:
                ok = True
                for subset, program in partials.items():
                    if subset and subset != full and \
                            _passes(program, shown, truth) == len(shown):
                        ok = False
                        break
                if not ok:
                    continue
            if _gradient_path(partials, full, shown, truth):
                return shown
    return None


# --- universe ----------------------------------------------------------

def _make_task(rng: random.Random, task_id: str, subset: str,
               defect_names: tuple[str, ...]) -> dict[str, Any] | None:
    cases = [tuple(c) for c in rng.choice(_GRID_SETS)]
    truth = [_run(_NAVIGATE_REFERENCE, case) for case in cases]
    buggy = _apply(_NAVIGATE_REFERENCE, defect_names)
    if _passes(buggy, cases, truth) == len(cases):
        return None  # defect not behaviourally real on this case set
    shown = identifiable_shown(defect_names, cases, truth, buggy)
    if shown is None:
        return None
    shown_truth = [truth[cases.index(case)] for case in shown]
    holdout = [case for case in cases if case not in shown]
    return {"task_id": task_id, "subset": subset,
            "defects": list(defect_names), "buggy_code": buggy,
            "shown_cases": [list(c) for c in shown],
            "shown_truth": shown_truth,
            "holdout_cases": [list(c) for c in holdout],
            "holdout_truth": [truth[cases.index(c)] for c in holdout]}


def build_universe(seed: int = 20261112) -> dict[str, Any]:
    """Deterministic universe; generation failures are counted, not
    silently dropped."""
    catalog = sorted(CATALOG_DEFECTS)
    new = sorted(NEW_DEFECTS)
    plan: list[tuple[str, tuple[str, ...], int]] = []
    for name in catalog:
        plan.append(("train", (name,), 3))
    for pair in itertools.combinations(catalog, 2):
        plan.append(("train", pair, 4))
    for name in new:
        plan.append(("new_only", (name,), 6))
    for pair in itertools.combinations(new, 2):
        plan.append(("new_only", pair, 4))
    for cat in catalog:
        for nw in new:
            plan.append(("mixed", (cat, nw), 2))
    for name in catalog:
        plan.append(("catalog_control", (name,), 4))
    for pair in itertools.combinations(catalog, 2):
        plan.append(("catalog_control", pair, 3))

    tasks: list[dict[str, Any]] = []
    failures: dict[str, int] = {}
    counters: dict[str, int] = {}
    stream = 0
    for subset, defects, count in plan:
        for _ in range(count):
            counters[subset] = counters.get(subset, 0) + 1
            stream += 1
            rng = random.Random(seed * 100003 + stream * 131)
            task = _make_task(rng, f"{subset}-{counters[subset]:03d}",
                              subset, defects)
            if task is None:
                key = f"{subset}:{'+'.join(defects)}"
                failures[key] = failures.get(key, 0) + 1
            else:
                tasks.append(task)
    return {"tasks": tasks, "generation_failures": failures}


# --- arms ---------------------------------------------------------------

def _budget_for(task: dict[str, Any]) -> Budget:
    return Budget(1_000_000, entrypoint="navigate",
                  shown_cases=[tuple(c) for c in task["shown_cases"]],
                  shown_expected=list(task["shown_truth"]))


def _solve_with(task: dict[str, Any], operators: tuple) -> tuple[str, int]:
    budget = _budget_for(task)
    solved = solve_grid(task, budget,
                        shown_total=len(task["shown_cases"]),
                        operators=operators)
    return (solved if solved is not None else task["buggy_code"],
            budget.used)


def _evaluate(task: dict[str, Any], code: str) -> tuple[bool, float]:
    cases = [tuple(c) for c in task["holdout_cases"]]
    passed = _passes(code, cases, task["holdout_truth"])
    return passed == len(cases), passed / max(1, len(cases))


def arm_a(task: dict[str, Any]) -> tuple[str, int]:
    return _solve_with(task, _OPERATORS)


def learn_order(train: list[dict[str, Any]]) -> tuple:
    """B's learning: rank operators by how often applying one alone
    improves a train task's shown score."""
    gains = {name: 0 for name in OPERATOR_NAMES}
    for task in train:
        budget = _budget_for(task)
        base = budget.score(task["buggy_code"])
        from .grid_substrate import grid_variants
        for name in OPERATOR_NAMES:
            variants = grid_variants(task["buggy_code"],
                                     (_OP_BY_NAME[name],))
            if any(budget.score(v) > base for v in variants):
                gains[name] += 1
    ranked = sorted(OPERATOR_NAMES, key=lambda n: -gains[n])
    return tuple(_OP_BY_NAME[n] for n in ranked)


def evolve_genome(train: list[dict[str, Any]], seed: int = 777,
                  population_size: int = 10, generations: int = 5
                  ) -> tuple:
    """C's learning: evolve (subset, order) genomes on train tasks;
    fitness = train tasks whose *full* case list the genome solves."""
    rng = random.Random(seed)

    def random_genome():
        names = list(OPERATOR_NAMES)
        rng.shuffle(names)
        keep = rng.randint(1, len(names))
        return tuple(names[:keep])

    def fitness(genome: tuple) -> int:
        operators = tuple(_OP_BY_NAME[n] for n in genome)
        score = 0
        for task in train:
            code, _ = _solve_with(task, operators)
            all_cases = [tuple(c) for c in task["shown_cases"]] + \
                [tuple(c) for c in task["holdout_cases"]]
            truth = task["shown_truth"] + task["holdout_truth"]
            if _passes(code, all_cases, truth) == len(all_cases):
                score += 1
        return score

    population = [random_genome() for _ in range(population_size)]
    scored = sorted(((fitness(g), g) for g in population),
                    key=lambda pair: -pair[0])
    for _ in range(generations):
        parents = [g for _, g in scored[:4]]
        children = list(parents)
        while len(children) < population_size:
            genome = list(rng.choice(parents))
            if len(genome) > 1 and rng.random() < 0.5:
                i, j = rng.sample(range(len(genome)), 2)
                genome[i], genome[j] = genome[j], genome[i]
            elif rng.random() < 0.4:
                missing = [n for n in OPERATOR_NAMES if n not in genome]
                if missing:
                    genome.append(rng.choice(missing))
                elif len(genome) > 1:
                    genome.pop(rng.randrange(len(genome)))
            children.append(tuple(genome))
        scored = sorted(((fitness(g), g) for g in children),
                        key=lambda pair: -pair[0])
    best = scored[0][1]
    return tuple(_OP_BY_NAME[n] for n in best)


def run_pilot(universe: dict[str, Any]) -> dict[str, Any]:
    """Execute all arms frozen; learning happens here, on train only,
    before any holdout task is touched."""
    tasks = universe["tasks"]
    train = [t for t in tasks if t["subset"] == "train"]
    holdout = [t for t in tasks if t["subset"] != "train"]
    order_b = learn_order(train)
    genome_c = evolve_genome(train)
    arms = {"A": lambda t: _solve_with(t, _OPERATORS),
            "B": lambda t: _solve_with(t, order_b),
            "C": lambda t: _solve_with(t, genome_c)}
    results: dict[str, Any] = {"arms": {}, "null_control": {}}
    for arm_name, solver in arms.items():
        per_subset: dict[str, Any] = {}
        total_calls = 0
        for task in holdout:
            code, calls = solver(task)
            total_calls += calls
            solved, fraction = _evaluate(task, code)
            bucket = per_subset.setdefault(
                task["subset"], {"solved": 0, "total": 0,
                                 "fraction_sum": 0.0})
            bucket["total"] += 1
            bucket["solved"] += int(solved)
            bucket["fraction_sum"] += fraction
        for bucket in per_subset.values():
            bucket["mean_fraction"] = round(
                bucket["fraction_sum"] / bucket["total"], 4)
            del bucket["fraction_sum"]
        results["arms"][arm_name] = {"subsets": per_subset,
                                     "budget_calls": total_calls}
    null_solved = 0
    for task in holdout:
        solved, _ = _evaluate(task, task["buggy_code"])
        null_solved += int(solved)
    results["null_control"] = {"solved": null_solved,
                               "total": len(holdout)}
    results["holdout_total"] = len(holdout)
    results["train_total"] = len(train)
    return results
