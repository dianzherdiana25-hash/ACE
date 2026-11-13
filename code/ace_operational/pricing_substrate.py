"""Authored pricing substrate — stage B-3 (bench Task 06
design), the pricing family's analogue of the grid
substrate (Stage C precedent).

Structural operators only: each recognises a defect's
*symptom structure* in the AST of `total()` and repairs
it generically. Nothing here searches for a defect's
literal text — the lab's defect transforms are string
replacements of the reference, and an operator that read
them would be reading the answer key. The accumulator is
identified structurally (the variable bound from the
first parameter in the opening assignment, and targeted
by the discount/tax augmented assignments), never by the
literal name `t`, so the substrate survives the lab's
renaming normalisation.

Epistemic label (Stage C's, restated for this family):
operators authored against a known defect catalog prove
that structure-level operators *reach* these classes —
not generalisation to unseen classes. That question
belongs to discovery and to G3's instrument, later.

Freeze discipline: this module freezes as pricing
substrate v1 at the B-3 stage (probe set fixed BEFORE
authoring, one-shot probe, digest recorded in the stage
evidence). Any post-freeze change is v2: new probe on a
fresh set, new digest, new freeze record.
"""
from __future__ import annotations

import ast
import copy
from typing import Any


def _function(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node
    return None


def _first_param(fn: ast.FunctionDef) -> str | None:
    return fn.args.args[0].arg if fn.args.args else None


def _accumulator(fn: ast.FunctionDef,
                 first_param: str) -> str | None:
    """The variable bound from the first parameter in the
    opening assignment (`t = subtotal`)."""
    for node in fn.body:
        if isinstance(node, ast.Assign) and \
                isinstance(node.value, ast.Name) and \
                node.value.id == first_param and \
                len(node.targets) == 1 and \
                isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
    return None


def _leftmost_leaf(node: ast.AST) -> ast.AST:
    while isinstance(node, ast.BinOp):
        node = node.left
    return node


# --- operators ----------------------------------------------------


def _threshold_sites(fn: ast.FunctionDef,
                     first_param: str,
                     accumulator: str) -> list[ast.Compare]:
    sites = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Gt)
                and isinstance(test.left, ast.Name)
                and test.left.id == first_param
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and isinstance(test.comparators[0].value, int)):
            continue
        guards_discount = any(
            isinstance(stmt, ast.AugAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == accumulator
            for stmt in node.body)
        if guards_discount:
            sites.append(test)
    return sites


def _variants_threshold(tree: ast.Module):
    """threshold_boundary: `if subtotal > K` guarding a
    discount AugAssign -> `>=`. Fires only on the defect
    signature (the reference's test is already GtE)."""
    fn = _function(tree)
    if fn is None:
        return
    first = _first_param(fn)
    acc = _accumulator(fn, first) if first else None
    if first is None or acc is None:
        return
    count = len(_threshold_sites(fn, first, acc))
    for i in range(count):
        new_tree = copy.deepcopy(tree)
        new_fn = _function(new_tree)
        sites = _threshold_sites(new_fn, first, acc)
        sites[i].ops[0] = ast.GtE()
        yield new_tree


def _rebase_sites(fn: ast.FunctionDef,
                  first_param: str,
                  accumulator: str) -> list[ast.Name]:
    """AugAssign leaves where a multiplication chain is
    rooted at the raw parameter instead of the
    accumulator (tax_basis at the final statement,
    member_basis inside the member If)."""
    sites = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.AugAssign):
            continue
        if not isinstance(node.op, (ast.Add, ast.Sub)):
            continue
        if not (isinstance(node.target, ast.Name)
                and node.target.id == accumulator):
            continue
        if not isinstance(node.value, ast.BinOp):
            continue
        leaf = _leftmost_leaf(node.value)
        if isinstance(leaf, ast.Name) and leaf.id == first_param:
            sites.append(leaf)
    return sites


def _variants_rebase_basis(tree: ast.Module):
    """tax_basis + member_basis: rebase an offending
    statement's multiplication chain onto the accumulator,
    one variant per offending statement, so the greedy
    solver can compose them across rounds for pairs."""
    fn = _function(tree)
    if fn is None:
        return
    first = _first_param(fn)
    acc = _accumulator(fn, first) if first else None
    if first is None or acc is None or acc == first:
        return
    count = len(_rebase_sites(fn, first, acc))
    for i in range(count):
        new_tree = copy.deepcopy(tree)
        new_fn = _function(new_tree)
        sites = _rebase_sites(new_fn, first, acc)
        sites[i].id = acc
        yield new_tree


_OPERATORS = (_variants_threshold, _variants_rebase_basis)


def pricing_variants(code: str,
                     operators: tuple = _OPERATORS) -> list[str]:
    """All one-operator structural variants of `code`
    (parse-checked, deduplicated, change-only)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    out: list[str] = []
    for operator in operators:
        for new_tree in operator(tree):
            try:
                text = ast.unparse(
                    ast.fix_missing_locations(new_tree))
            except Exception:
                continue
            if text != code and text not in out:
                out.append(text)
    return out


def solve_pricing(task: dict[str, Any], budget: Any, *,
                  shown_total: int, max_rounds: int = 6,
                  operators: tuple = _OPERATORS) -> str | None:
    """Greedy best-first repair over the structural
    operators — `solve_grid`'s loop, verbatim in shape.
    `budget` is the reasoning_lab Budget (shown cases
    only; score is a count). Returns the best code found;
    callers verify against holdout themselves."""
    start = task["buggy_code"]
    best_code, best_score = start, budget.score(start)
    frontier = [start]
    seen = {start}
    for _ in range(max_rounds):
        if best_score >= shown_total:
            break
        candidates: list[str] = []
        for code in frontier:
            for variant in pricing_variants(code, operators):
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
            frontier = [c for s, c in scored
                        if s == best_score][:4]
        else:
            break
    return best_code
