"""Structural repair substrate for the grid/BFS family (Phase 2, stage C).

The token-search smoke measurement (Addendum 21) solved 0/58 grid
tasks: BFS defects are structural — a dropped guard conjunct, a
missing direction-tuple element, injected diagonal steps, an offset
initial distance — none reachable by single-token substitution.
Following the same growth pattern as substrate v2 for shipping (one
operator per *measured* defect class), this module provides four
AST-level operators and a greedy solver over them:

* ``restore_wall_guard`` — re-insert the ``grid[..][..] != "#"``
  conjunct into the neighbour-admission test that lost it;
* ``remove_diagonals`` — drop diagonal steps from the direction tuple;
* ``add_direction`` — insert one missing cardinal direction;
* ``fix_start_offset`` — reset the initial distance assignment to 0.

Operators are admitted only when they parse and actually change the
code. The solver is best-first greedy scored *only* on the shown
cases (via the caller's Budget); holdout judgement stays with the
curriculum verifier, exactly as in the other substrates.
"""
from __future__ import annotations

import ast
import copy
from typing import Any

CARDINALS = {(1, 0), (-1, 0), (0, 1), (0, -1)}


def _const_pair(node: ast.expr) -> tuple[int, int] | None:
    if isinstance(node, ast.Tuple) and len(node.elts) == 2:
        vals = []
        for elt in node.elts:
            v = _const_int(elt)
            if v is None:
                return None
            vals.append(v)
        return (vals[0], vals[1])
    return None


def _const_int(node: ast.expr) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _const_int(node.operand)
        return -inner if inner is not None else None
    return None


def _int_expr(value: int) -> ast.expr:
    if value < 0:
        return ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=-value))
    return ast.Constant(value=value)


def _pair_expr(pair: tuple[int, int]) -> ast.Tuple:
    return ast.Tuple(elts=[_int_expr(pair[0]), _int_expr(pair[1])],
                     ctx=ast.Load())


def _find_navigate(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "navigate":
            return node
    return None


def _direction_tuple(fn: ast.FunctionDef) -> ast.Tuple | None:
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            if node.iter.elts and all(_const_pair(e) is not None
                                      for e in node.iter.elts):
                return node.iter
    return None


def _variants_wall_guard(tree: ast.Module) -> list[ast.Module]:
    fn = _find_navigate(tree)
    if fn is None:
        return []
    out = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test_src = ast.dump(node.test)
        if "dist" not in test_src or "grid" in test_src:
            continue
        # The neighbour-admission test: mentions dist[..][..] == -1 and
        # has no grid lookup. Rebuild its index names from the dist
        # subscript so the guard reads grid[nr][nc] in whatever names
        # the code actually uses.
        idx_names = None
        for sub in ast.walk(node.test):
            if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Subscript):
                inner = sub.value
                if isinstance(inner.value, ast.Name) and inner.value.id == "dist":
                    a, b = inner.slice, sub.slice
                    if isinstance(a, ast.Name) and isinstance(b, ast.Name):
                        idx_names = (a.id, b.id)
        if idx_names is None:
            continue
        new_tree = copy.deepcopy(tree)
        for new_node in ast.walk(_find_navigate(new_tree)):
            if isinstance(new_node, ast.If) and ast.dump(new_node.test) == test_src:
                guard = ast.Compare(
                    left=ast.Subscript(
                        value=ast.Subscript(
                            value=ast.Name(id="grid", ctx=ast.Load()),
                            slice=ast.Name(id=idx_names[0], ctx=ast.Load()),
                            ctx=ast.Load()),
                        slice=ast.Name(id=idx_names[1], ctx=ast.Load()),
                        ctx=ast.Load()),
                    ops=[ast.NotEq()], comparators=[ast.Constant(value="#")])
                if isinstance(new_node.test, ast.BoolOp) and \
                        isinstance(new_node.test.op, ast.And):
                    new_node.test.values.append(guard)
                else:
                    new_node.test = ast.BoolOp(op=ast.And(),
                                               values=[new_node.test, guard])
                out.append(new_tree)
                break
    return out


def _variants_directions(tree: ast.Module) -> list[ast.Module]:
    fn = _find_navigate(tree)
    if fn is None:
        return []
    tup = _direction_tuple(fn)
    if tup is None:
        return []
    pairs = [_const_pair(e) for e in tup.elts]
    present = set(pairs)
    out = []
    if any(abs(a) + abs(b) == 2 for a, b in pairs):
        new_tree = copy.deepcopy(tree)
        new_tup = _direction_tuple(_find_navigate(new_tree))
        new_tup.elts = [e for e, p in zip(new_tup.elts, pairs)
                        if abs(p[0]) + abs(p[1]) == 1]
        out.append(new_tree)
    for missing in sorted(CARDINALS - present):
        new_tree = copy.deepcopy(tree)
        new_tup = _direction_tuple(_find_navigate(new_tree))
        new_tup.elts.append(_pair_expr(missing))
        out.append(new_tree)
    return out


def _variants_start_offset(tree: ast.Module) -> list[ast.Module]:
    fn = _find_navigate(tree)
    if fn is None:
        return []
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Subscript) and \
                    isinstance(target.value, ast.Subscript) and \
                    isinstance(target.value.value, ast.Name) and \
                    target.value.value.id == "dist":
                value = _const_int(node.value)
                if value is not None and value != 0:
                    new_tree = copy.deepcopy(tree)
                    for new_node in ast.walk(_find_navigate(new_tree)):
                        if isinstance(new_node, ast.Assign) and \
                                ast.dump(new_node.targets[0]) == ast.dump(target):
                            new_node.value = ast.Constant(value=0)
                            out.append(new_tree)
                            break
    return out


_OPERATORS = (_variants_wall_guard, _variants_directions, _variants_start_offset)


def grid_variants(code: str) -> list[str]:
    """All one-operator structural variants of `code` (parse-checked)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    out: list[str] = []
    for operator in _OPERATORS:
        for new_tree in operator(tree):
            try:
                text = ast.unparse(ast.fix_missing_locations(new_tree))
            except Exception:
                continue
            if text != code and text not in out:
                out.append(text)
    return out


def solve_grid(task: dict[str, Any], budget: Any, *, shown_total: int,
               max_rounds: int = 6) -> str | None:
    """Greedy best-first repair over the structural operators.

    `budget` is the reasoning_lab Budget (shown-cases only; its score
    is a *count* of passed shown cases, so perfection is
    ``shown_total``). Returns the best code found — callers verify
    against holdout themselves.
    """
    start = task["buggy_code"]
    best_code, best_score = start, budget.score(start)
    frontier = [start]
    seen = {start}
    for _ in range(max_rounds):
        if best_score >= shown_total:
            break
        candidates: list[str] = []
        for code in frontier:
            for variant in grid_variants(code):
                if variant not in seen:
                    seen.add(variant)
                    candidates.append(variant)
        if not candidates:
            break
        scored = []
        for variant in candidates:
            if budget.used >= budget.limit:
                break
            scored.append((budget.score(variant), variant))
        if not scored:
            break
        scored.sort(key=lambda item: -item[0])
        if scored[0][0] > best_score:
            best_code, best_score = scored[0][1], scored[0][0]
            frontier = [c for s, c in scored if s == best_score][:4]
        else:
            break
    return best_code
