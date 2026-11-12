"""Operator discovery — catalog growth by mechanism (stage I).

Stage F measured that the grid substrate's competence ends at its
authored catalog. This module is the growth mechanism: given tasks
the substrate cannot solve, it searches a space of *generic AST
edit schemas* (not defect-specific rules) for one-edit repairs,
abstracts each successful edit into a reusable operator — a schema
bound to a structural site path plus a relative transformation —
and admits an operator into the extended catalog only if it fixes
at least two independent discovery-pool tasks. Transfer is then
measured on evaluation tasks the discovery never touched.

Honesty boundary, stated in the design: the schema *space* is
human-designed; the *operators* (which schema, at which site, with
which parameters) are discovered by the mechanism and admitted
under a measured protocol. That is the claim — nothing more.
"""
from __future__ import annotations

import ast
import copy
import itertools
import signal
from typing import Any

from .grid_generalization import _budget_for, _passes
from .grid_substrate import _OPERATORS


class _ScoreTimeout(Exception):
    pass


def _alarm_handler(signum, frame):  # noqa: ARG001 - signal signature
    raise _ScoreTimeout()


def _safe_score(budget: Any, code: str, seconds: float = 0.5) -> int:
    """Score a candidate under a hard wall-clock guard.

    Arbitrary AST edits can make the BFS loop forever (a changed
    visited-sentinel re-queues cells without bound — the first
    version of this module OOM-killed its own test process that
    way). A timeout is a failed candidate, scored -1.
    """
    previous = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return budget.score(code)
    except _ScoreTimeout:
        return -1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)

# --- generic edit schemas ---------------------------------------------
# A variant is (operator_key, new_code). operator_key abstracts the
# edit: (schema, ast_path, parameter). Applying an operator to a
# fresh program re-locates the node by its AST path and re-applies
# the same relative transformation.


def _walk_paths(tree: ast.AST, path: tuple = ()):
    yield path, tree
    for index, child in enumerate(ast.iter_child_nodes(tree)):
        yield from _walk_paths(child, path + (index,))


def _node_at(tree: ast.AST, path: tuple) -> ast.AST | None:
    node = tree
    for index in path:
        children = list(ast.iter_child_nodes(node))
        if index >= len(children):
            return None
        node = children[index]
    return node


def _child_slots(node: ast.AST) -> list[tuple[str, int | None]]:
    """(field, list-index-or-None) per child, in iter_child_nodes
    order — the same order _walk_paths/_node_at use."""
    slots: list[tuple[str, int | None]] = []
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, ast.AST):
                    slots.append((field, i))
        elif isinstance(value, ast.AST):
            slots.append((field, None))
    return slots


def _replace_at(tree: ast.AST, path: tuple, new_node: ast.AST) -> bool:
    if not path:
        return False
    parent = _node_at(tree, path[:-1])
    if parent is None:
        return False
    slots = _child_slots(parent)
    if path[-1] >= len(slots):
        return False
    field, index = slots[path[-1]]
    if index is None:
        setattr(parent, field, new_node)
    else:
        getattr(parent, field)[index] = new_node
    return True


def _function_of(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node
    return None


def _string_candidates(code: str) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Constant) and isinstance(node.value,
                                                         str):
            found.add(node.value)
    # The task family's spec fixes '#' as the wall character and the
    # case grids contain it; both are legitimate generic sources.
    found.add("#")
    return found


def enumerate_variants(code: str) -> list[tuple[tuple, str]]:
    """All one-schema-edit variants of `code`, each with its
    abstract operator key."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    fn = _function_of(tree)
    if fn is None:
        return []
    params = [a.arg for a in fn.args.args]
    strings = _string_candidates(code)
    out: list[tuple[tuple, str]] = []
    seen: set[str] = set()

    def emit(key: tuple, new_tree: ast.AST) -> None:
        try:
            text = ast.unparse(ast.fix_missing_locations(new_tree))
        except Exception:
            return
        if text != code and text not in seen:
            seen.add(text)
            out.append((key, text))

    for path, node in _walk_paths(fn):
        # int constants: nudge or replace with small canonical values
        if isinstance(node, ast.Constant) and isinstance(node.value,
                                                         int) and \
                not isinstance(node.value, bool):
            for value in {0, 1, 2, node.value - 1, node.value + 1}:
                if value == node.value:
                    continue
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                target.value = value  # type: ignore[attr-defined]
                emit(("int_constant", path, value), new_tree)
        # string literals: replace with any other known string
        if isinstance(node, ast.Constant) and isinstance(node.value,
                                                         str):
            for value in strings - {node.value}:
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                target.value = value  # type: ignore[attr-defined]
                emit(("string_literal", path, value), new_tree)
        # binary operator swap
        if isinstance(node, ast.BinOp):
            for op in (ast.Add, ast.Sub, ast.Mult):
                if isinstance(node.op, op):
                    continue
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                target.op = op()  # type: ignore[attr-defined]
                emit(("binop_swap", path, op.__name__), new_tree)
            # unwrap BinOp(Name, op, Const) -> Name
            if isinstance(node.left, ast.Name) and \
                    isinstance(node.right, ast.Constant):
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if target is not None and _replace_at(
                        _function_of(new_tree), path,
                        copy.deepcopy(target.left)):
                    emit(("binop_unwrap", path, "left"), new_tree)
        # comparison operator swap
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            for op in (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq,
                       ast.NotEq):
                if isinstance(node.ops[0], op):
                    continue
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                target.ops = [op()]  # type: ignore[attr-defined]
                emit(("compare_swap", path, op.__name__), new_tree)
        # return subscript chain: dist[a][b] is two nested
        # Subscripts with Name slices (not a Tuple slice — the
        # v1 run's zero candidates for returns_start_distance came
        # from assuming otherwise). Rebind both index names to any
        # parameter combination.
        if isinstance(node, ast.Return):
            chain: list[ast.Name] = []
            cursor: ast.AST = node.value
            while isinstance(cursor, ast.Subscript) and isinstance(
                    cursor.slice, ast.Name):
                chain.append(cursor.slice)
                cursor = cursor.value
            if len(chain) == 2 and isinstance(cursor, ast.Name):
                current = tuple(n.id for n in reversed(chain))
                for combo in itertools.product(params, repeat=2):
                    if combo == current:
                        continue
                    new_tree = copy.deepcopy(tree)
                    target = _node_at(_function_of(new_tree), path)
                    names: list[ast.Name] = []
                    walk: ast.AST = target.value
                    while isinstance(walk, ast.Subscript) and \
                            isinstance(walk.slice, ast.Name):
                        names.append(walk.slice)
                        walk = walk.value
                    for name_node, name in zip(reversed(names),
                                               combo):
                        name_node.id = name
                    emit(("return_indices", path, combo), new_tree)
    return out


def apply_operator(code: str, key: tuple) -> str | None:
    """Re-apply a discovered operator to a fresh program by
    re-locating its site path and transformation."""
    schema, path, parameter = key
    for candidate_key, text in enumerate_variants(code):
        if candidate_key == key:
            return text
    return None


# --- discovery + admission ----------------------------------------------

def discover_for_task(task: dict[str, Any]) -> list[tuple]:
    """Operator keys whose single application makes the task's
    shown cases fully pass."""
    budget = _budget_for(task)
    shown_total = len(task["shown_cases"])
    found = []
    for key, variant in enumerate_variants(task["buggy_code"]):
        if _safe_score(budget, variant) >= shown_total:
            found.append(key)
    return found


def run_discovery(*, pool: list[dict[str, Any]],
                  evaluation: list[dict[str, Any]],
                  control: list[dict[str, Any]],
                  min_pool_fixes: int = 2) -> dict[str, Any]:
    """Pool -> candidate operators -> admission (>= min_pool_fixes
    pool tasks fixed) -> measured transfer on evaluation + control
    regression, all with the extended greedy solver."""
    by_class: dict[str, Any] = {}
    admitted_keys: dict[str, list[tuple]] = {}
    pool_by_class: dict[str, list] = {}
    for task in pool:
        for defect in task["defects"]:
            pool_by_class.setdefault(defect, []).append(task)
    eval_by_class: dict[str, list] = {}
    for task in evaluation:
        for defect in task["defects"]:
            eval_by_class.setdefault(defect, []).append(task)

    def solve_with(task, extra_keys):
        def extended_variants(code):
            from .grid_substrate import grid_variants
            variants = grid_variants(code, _OPERATORS)
            for key in extra_keys:
                text = apply_operator(code, key)
                if text is not None and text not in variants:
                    variants.append(text)
            return variants
        budget = _budget_for(task)
        # Greedy over the union variant generator, mirroring
        # solve_grid's loop with an injected generator.
        start = task["buggy_code"]
        best_code, best_score = start, _safe_score(budget, start)
        frontier, seen = [start], {start}
        for _ in range(6):
            if best_score >= len(task["shown_cases"]):
                break
            candidates = []
            for code in frontier:
                for variant in extended_variants(code):
                    if variant not in seen:
                        seen.add(variant)
                        candidates.append(variant)
            if not candidates:
                break
            scored = sorted(((_safe_score(budget, c), c)
                             for c in candidates),
                            key=lambda pair: -pair[0])
            if scored[0][0] > best_score:
                best_code, best_score = scored[0][1], scored[0][0]
            frontier = [c for s, c in scored[:4] if s >= best_score]
            if not frontier:
                break
        return best_code

    def solved(task, extra_keys) -> bool:
        code = solve_with(task, extra_keys)
        cases = [tuple(c) for c in task["holdout_cases"]]
        previous = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, 5.0)
        try:
            passed = _passes(code, cases, task["holdout_truth"])
        except _ScoreTimeout:
            passed = -1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        return passed == len(cases)

    for defect_class, class_pool in sorted(pool_by_class.items()):
        fix_counts: dict[tuple, int] = {}
        for task in class_pool:
            for key in discover_for_task(task):
                fix_counts[key] = fix_counts.get(key, 0) + 1
        admitted = [key for key, count in fix_counts.items()
                    if count >= min_pool_fixes]
        admitted_keys[defect_class] = admitted
        class_eval = eval_by_class.get(defect_class, [])
        base_solved = sum(1 for t in class_eval if solved(t, []))
        ext_solved = sum(1 for t in class_eval
                         if solved(t, admitted)) if admitted else base_solved
        by_class[defect_class] = {
            "pool_tasks": len(class_pool),
            "candidate_operators": len(fix_counts),
            "admitted_operators": [str(k) for k in admitted],
            "eval_tasks": len(class_eval),
            "eval_solved_baseline": base_solved,
            "eval_solved_extended": ext_solved}
    all_admitted = [key for keys in admitted_keys.values()
                    for key in keys]
    control_base = sum(1 for t in control if solved(t, []))
    control_ext = sum(1 for t in control
                      if solved(t, all_admitted)) if all_admitted \
        else control_base
    return {"by_class": by_class,
            "control": {"total": len(control),
                        "solved_baseline": control_base,
                        "solved_extended": control_ext}}
