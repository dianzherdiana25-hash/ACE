"""Lexical, method, wrapper, and argument AST operators for multi-family discovery.

Extends ACE's generic AST edit discovery beyond expression-level arithmetic
and grid indexing (``operator_discovery.py``) and statement reordering
(``statement_ops.py``) without altering any frozen core file.

Generic AST edit schemas:
- ``attribute_swap``: Swap a method attribute inside an ``ast.Call`` across
  standard Python string/collection equivalence classes (case/strip/split/find).
- ``call_arg_drop`` / ``call_arg_restore``: Drop a positional constant argument
  on a call (e.g. ``x.split(" ") -> x.split()``) or restore a canonical separator.
- ``call_wrapper_unwrap`` / ``call_wrapper_wrap``: Remove or insert a unary builtin
  wrapper (e.g. ``reversed(words) <-> words``).
- Plus generic expression schemas (``string_literal``, ``int_constant``,
  ``bool_constant``, ``compare_swap``, ``binop_swap``, ``binop_unwrap``).

Also provides ``ShippingAdapter``, ``build_shipping_task``, and ``shipping_rivals``
so ``grid``, ``pricing``, ``shipping``, and ``text_transform`` all share one clean
FamilyAdapter discovery/evaluation interface.
"""
from __future__ import annotations

import ast
import copy
import re
import signal
from typing import Any

from .curriculum_lab import _run_cases, generate_task
from .operator_discovery import (
    _BINOPS,
    _COMPARES,
    _ScoreTimeout,
    _alarm_handler,
    _function_of,
    _node_at,
    _replace_at,
    _safe_score,
    _string_candidates,
    _walk_paths,
)
from .reasoning_lab import Budget

METHOD_GROUPS: tuple[tuple[str, ...], ...] = (
    ("lower", "upper", "title", "capitalize", "swapcase", "casefold"),
    ("strip", "lstrip", "rstrip"),
    ("split", "rsplit", "splitlines"),
    ("startswith", "endswith"),
    ("find", "rfind", "index", "rindex"),
)

_ATTR_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    attr: tuple(other for other in group if other != attr)
    for group in METHOD_GROUPS
    for attr in group
}

UNARY_WRAPPERS: tuple[str, ...] = ("reversed", "sorted", "list", "tuple")
_RESTORABLE_ARG_METHODS = frozenset({"split", "rsplit", "strip", "lstrip", "rstrip"})
_DEFAULT_RESTORE_SEPARATORS: tuple[str, ...] = (" ", ",", "-", "_")


def _int_candidates(tree: ast.AST, current_val: int, extra: set[int] | frozenset[int] = frozenset()) -> list[int]:
    cands = {0, 1, 2, 3, current_val - 1, current_val + 1, current_val - 2, current_val + 2}
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, int) and not isinstance(sub.value, bool):
            cands.add(sub.value)
    cands.update(extra)
    cands.discard(current_val)
    return sorted(cands)


def enumerate_lexical_variants(
    code: str,
    string_seeds: set[str] | frozenset[str] = frozenset(),
    int_seeds: set[int] | frozenset[int] = frozenset(),
) -> list[tuple[tuple, str]]:
    """Enumerate all single-edit lexical and expression AST variants with canonical keys."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    fn = _function_of(tree)
    if fn is None:
        return []

    strings = sorted(_string_candidates(code, string_seeds))
    out: list[tuple[tuple, str]] = []
    seen_texts: set[str] = set()

    def emit(key: tuple, new_tree: ast.AST) -> None:
        try:
            text = ast.unparse(ast.fix_missing_locations(new_tree))
        except Exception:
            return
        if text != code and text not in seen_texts:
            seen_texts.add(text)
            out.append((key, text))

    for path, node in _walk_paths(fn):
        # 1. String-method attribute swap (e.g. w.lower() <-> w.upper() <-> w.title())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            alt_attrs = _ATTR_ALTERNATIVES.get(node.func.attr, ())
            for new_attr in alt_attrs:
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute):
                    target.func.attr = new_attr
                    emit(("attribute_swap", path, new_attr), new_tree)

            # 2. Drop a constant positional arg (e.g. text.split(" ") -> text.split())
            if len(node.args) >= 1 and all(isinstance(a, ast.Constant) for a in node.args):
                for idx in range(len(node.args) - 1, -1, -1):
                    new_tree = copy.deepcopy(tree)
                    target = _node_at(_function_of(new_tree), path)
                    if isinstance(target, ast.Call) and idx < len(target.args):
                        target.args.pop(idx)
                        emit(("call_arg_drop", path, idx), new_tree)

            # 3. Restore canonical string separator arg on empty split/strip calls
            if not node.args and not node.keywords and node.func.attr in _RESTORABLE_ARG_METHODS:
                for sep in _DEFAULT_RESTORE_SEPARATORS:
                    new_tree = copy.deepcopy(tree)
                    target = _node_at(_function_of(new_tree), path)
                    if isinstance(target, ast.Call):
                        target.args = [ast.Constant(value=sep)]
                        emit(("call_arg_restore", path, sep), new_tree)

        # 4. Unwrap single-argument unary builtin wrapper (e.g. reversed(words) -> words)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in UNARY_WRAPPERS
            and len(node.args) == 1
            and not node.keywords
        ):
            new_tree = copy.deepcopy(tree)
            new_fn = _function_of(new_tree)
            target = _node_at(new_fn, path)
            if (
                new_fn is not None
                and isinstance(target, ast.Call)
                and len(target.args) == 1
                and _replace_at(new_fn, path, copy.deepcopy(target.args[0]))
            ):
                emit(("call_wrapper_unwrap", path, node.func.id), new_tree)

        # 5. Wrap simple Name argument inside `.join(name)` or direct call arg with unary builtin
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join":
            for arg_idx, arg in enumerate(node.args):
                if isinstance(arg, ast.Name):
                    for wrapper in ("reversed", "sorted"):
                        new_tree = copy.deepcopy(tree)
                        target = _node_at(_function_of(new_tree), path)
                        if isinstance(target, ast.Call) and arg_idx < len(target.args):
                            inner = copy.deepcopy(target.args[arg_idx])
                            target.args[arg_idx] = ast.Call(
                                func=ast.Name(id=wrapper, ctx=ast.Load()),
                                args=[inner],
                                keywords=[],
                            )
                            emit(("call_wrapper_wrap", path, (arg_idx, wrapper)), new_tree)

        # 6. String literals
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for value in strings:
                if value == node.value:
                    continue
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if isinstance(target, ast.Constant):
                    target.value = value
                    emit(("string_literal", path, value), new_tree)

        # 7. Integer constants (relative delta first so off-by-one generalizes across literals)
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            for delta in (1, -1, 2, -2):
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if isinstance(target, ast.Constant) and isinstance(target.value, int):
                    target.value = target.value + delta
                    emit(("int_delta", path, delta), new_tree)
            for value in _int_candidates(fn, node.value, int_seeds):
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if isinstance(target, ast.Constant):
                    target.value = value
                    emit(("int_constant", path, value), new_tree)

        # 8. Boolean constants
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            new_tree = copy.deepcopy(tree)
            target = _node_at(_function_of(new_tree), path)
            if isinstance(target, ast.Constant):
                target.value = not node.value
                emit(("bool_constant", path, target.value), new_tree)

        # 9. Comparison operators
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            for op_cls in (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq):
                if isinstance(node.ops[0], op_cls):
                    continue
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if isinstance(target, ast.Compare):
                    target.ops = [op_cls()]
                    emit(("compare_swap", path, op_cls.__name__), new_tree)

        # 10. Binary operators
        if isinstance(node, ast.BinOp):
            for op_cls in (ast.Add, ast.Sub, ast.Mult):
                if isinstance(node.op, op_cls):
                    continue
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                if isinstance(target, ast.BinOp):
                    target.op = op_cls()
                    emit(("binop_swap", path, op_cls.__name__), new_tree)
            if isinstance(node.left, ast.Name) and isinstance(node.right, ast.Constant):
                new_tree = copy.deepcopy(tree)
                new_fn = _function_of(new_tree)
                target = _node_at(new_fn, path)
                if new_fn is not None and isinstance(target, ast.BinOp) and _replace_at(
                    new_fn, path, copy.deepcopy(target.left)
                ):
                    emit(("binop_unwrap", path, "left"), new_tree)

    return out


def _apply_lexical_direct(code: str, key: tuple) -> str | None:
    if not isinstance(key, tuple) or len(key) != 3:
        return None
    schema, path, parameter = key
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    fn = _function_of(tree)
    if fn is None:
        return None
    node = _node_at(fn, path)
    if node is None:
        return None

    if schema == "attribute_swap":
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return None
        node.func.attr = str(parameter)
    elif schema == "call_arg_drop":
        if not isinstance(node, ast.Call) or not isinstance(parameter, int):
            return None
        if parameter < 0 or parameter >= len(node.args):
            return None
        node.args.pop(parameter)
    elif schema == "call_arg_restore":
        if not isinstance(node, ast.Call) or not isinstance(parameter, str):
            return None
        if node.args:
            return None
        node.args = [ast.Constant(value=parameter)]
    elif schema == "call_wrapper_unwrap":
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == parameter
            and len(node.args) == 1
        ):
            return None
        if not _replace_at(fn, path, copy.deepcopy(node.args[0])):
            return None
    elif schema == "call_wrapper_wrap":
        if not (isinstance(node, ast.Call) and isinstance(parameter, tuple) and len(parameter) == 2):
            return None
        arg_idx, wrapper = parameter
        if not isinstance(arg_idx, int) or arg_idx < 0 or arg_idx >= len(node.args):
            return None
        inner = copy.deepcopy(node.args[arg_idx])
        node.args[arg_idx] = ast.Call(
            func=ast.Name(id=str(wrapper), ctx=ast.Load()),
            args=[inner],
            keywords=[],
        )
    elif schema == "string_literal" and isinstance(node, ast.Constant):
        node.value = parameter
    elif schema == "int_delta" and isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        if not isinstance(parameter, int):
            return None
        node.value = node.value + parameter
    elif schema == "int_constant" and isinstance(node, ast.Constant):
        node.value = parameter
    elif schema == "bool_constant" and isinstance(node, ast.Constant):
        node.value = parameter
    elif schema == "compare_swap" and isinstance(node, ast.Compare):
        op_cls = _COMPARES.get(parameter)
        if op_cls is None:
            return None
        node.ops = [op_cls()]
    elif schema == "binop_swap" and isinstance(node, ast.BinOp):
        op_cls = _BINOPS.get(parameter)
        if op_cls is None:
            return None
        node.op = op_cls()
    elif schema == "binop_unwrap" and isinstance(node, ast.BinOp):
        if not _replace_at(fn, path, copy.deepcopy(node.left)):
            return None
    else:
        return None

    try:
        text = ast.unparse(ast.fix_missing_locations(tree))
    except Exception:
        return None
    return text if text != code else None


def apply_lexical_operator(code: str, key: tuple) -> str | None:
    """Re-apply a lexical or expression operator key deterministically (O(parse) direct)."""
    direct = _apply_lexical_direct(code, key)
    if direct is not None:
        return direct
    for cand_key, text in enumerate_lexical_variants(code):
        if cand_key == key:
            return text
    return None


def apply_lexical_chain(code: str, chain: tuple) -> str | None:
    """Apply a sequence of lexical operator keys step by step."""
    current: str | None = code
    for key in chain:
        if current is None:
            return None
        current = apply_lexical_operator(current, key)
    return current


# ---------------------------------------------------------------------------
# Discovery, chains, and Lineage-Guard solving
# ---------------------------------------------------------------------------

def _passes_pool_holdout(task: dict[str, Any], code: str, adapter) -> bool:
    cases = [tuple(c) for c in task.get("holdout_cases", [])]
    if not cases:
        return True
    truth = list(task.get("holdout_truth", []))
    return adapter.passes(code, cases, truth) == len(cases)


def _scored_lexical_variants(task: dict[str, Any], adapter) -> tuple[int, list[tuple[int, tuple, str]]]:
    budget = adapter.make_budget(task)
    baseline = _safe_score(budget, task["buggy_code"])
    seeds = adapter.extra_string_candidates(task["buggy_code"])
    scored = [
        (_safe_score(budget, variant), key, variant)
        for key, variant in enumerate_lexical_variants(task["buggy_code"], seeds)
    ]
    return baseline, scored


def discover_lexical_for_task(
    task: dict[str, Any],
    adapter,
    *,
    require_pool_holdout: bool = True,
) -> list[tuple]:
    """Single-edit lexical keys that fix `task`'s shown (and optionally pool holdout) cases."""
    shown_total = len(task["shown_cases"])
    if shown_total == 0:
        return []
    _, scored = _scored_lexical_variants(task, adapter)
    out: list[tuple] = []
    for score, key, variant in scored:
        if score >= shown_total:
            if not require_pool_holdout or _passes_pool_holdout(task, variant, adapter):
                out.append(key)
    return out


def discover_lexical_pairs_for_task(
    task: dict[str, Any],
    adapter,
    *,
    max_partners: int = 12,
    require_pool_holdout: bool = True,
) -> list[tuple[tuple, tuple]]:
    """Discover ordered pairs of edits for L2 multi-defect tasks."""
    shown_total = len(task["shown_cases"])
    if shown_total == 0:
        return []
    baseline, scored = _scored_lexical_variants(task, adapter)
    if any(score >= shown_total for score, _, _ in scored):
        return []
    improvers = sorted(
        ((score, key, text) for score, key, text in scored if baseline <= score < shown_total),
        key=lambda item: (-int(item[0] > baseline), -item[0]),
    )[:max_partners]
    budget = adapter.make_budget(task)
    pairs: list[tuple[tuple, tuple]] = []
    seen_pairs: set[tuple[tuple, tuple]] = set()
    for _, key_a, text_a in improvers:
        seeds = adapter.extra_string_candidates(text_a)
        for key_b, text_ab in enumerate_lexical_variants(text_a, seeds):
            if _safe_score(budget, text_ab) >= shown_total:
                if not require_pool_holdout or _passes_pool_holdout(task, text_ab, adapter):
                    pair = (key_a, key_b)
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        pairs.append(pair)
                    break
    return pairs


def discover_lexical_chain_for_task(
    task: dict[str, Any],
    adapter,
    *,
    max_depth: int = 3,
    require_pool_holdout: bool = True,
) -> tuple | None:
    """Greedy re-enumerating chain discovery on a pool task."""
    shown_total = len(task["shown_cases"])
    if shown_total == 0:
        return None
    budget = adapter.make_budget(task)
    current = task["buggy_code"]
    current_score = _safe_score(budget, current)
    if current_score >= shown_total:
        return None
    chain: list[tuple] = []
    for _ in range(max_depth):
        seeds = adapter.extra_string_candidates(current)
        scored = [
            (_safe_score(budget, text), key, text)
            for key, text in enumerate_lexical_variants(current, seeds)
        ]
        if not scored:
            return None
        best_score, best_key, best_text = max(scored, key=lambda item: item[0])
        if best_score >= shown_total:
            if not require_pool_holdout or _passes_pool_holdout(task, best_text, adapter):
                chain.append(best_key)
                return tuple(chain) if len(chain) >= 2 else None
            return None
        if best_score <= current_score:
            return None
        chain.append(best_key)
        current, current_score = best_text, best_score
    return None


def solve_lexical_task(
    task: dict[str, Any],
    adapter,
    extra_keys: tuple | list = (),
    extra_chains: tuple | list = (),
    *,
    max_score_calls: int | None = None,
    trace: list | None = None,
    guard: bool = True,
    guard_stats: dict[str, int] | None = None,
    max_rounds: int = 6,
    frontier_width: int = 4,
) -> str:
    """Budgeted greedy solver for lexical/expression operators with optional Lineage-Guard."""
    provenance: dict[str, tuple] = {}
    label_of: dict[str, str] = {}

    def extended_variants(code: str) -> list[str]:
        parent_label = label_of[code] if guard else ""
        variants = list(adapter.baseline_variants(code))
        if guard:
            for text in variants:
                label_of.setdefault(text, parent_label)
        if trace is not None:
            for text in variants:
                provenance.setdefault(text, ("baseline", None))
        for key in extra_keys:
            text = apply_lexical_operator(code, key)
            if text is not None:
                if guard:
                    label_of.setdefault(text, "ENRICHED")
                if text not in variants:
                    variants.append(text)
                    if trace is not None:
                        provenance.setdefault(text, ("key", key))
        for chain in extra_chains:
            text = apply_lexical_chain(code, chain)
            if text is not None:
                if guard:
                    label_of.setdefault(text, "ENRICHED")
                if text not in variants:
                    variants.append(text)
                    if trace is not None:
                        provenance.setdefault(text, ("chain", chain))
        return variants

    budget = adapter.make_budget(task)
    calls = 0

    def score(code: str) -> int:
        nonlocal calls
        calls += 1
        return _safe_score(budget, code)

    start = task["buggy_code"]
    if guard:
        label_of[start] = "BASE"
    best_code, best_score = start, score(start)
    frontier, seen = [start], {start}
    shown_len = len(task["shown_cases"])

    for _ in range(max_rounds):
        if best_score >= shown_len:
            break
        candidates: list[str] = []
        for code in frontier:
            for variant in extended_variants(code):
                if variant not in seen:
                    seen.add(variant)
                    candidates.append(variant)
        if not candidates:
            break
        scored_pairs: list[tuple[int, str]] = []
        for candidate in candidates:
            if max_score_calls is not None and calls >= max_score_calls:
                break
            scored_pairs.append((score(candidate), candidate))
        if not scored_pairs:
            break
        scored = sorted(scored_pairs, key=lambda pair: -pair[0])
        if scored[0][0] > best_score:
            best_code, best_score = scored[0][1], scored[0][0]
            if trace is not None:
                trace.append(provenance[scored[0][1]])
        frontier = [c for s, c in scored[:frontier_width] if s >= best_score]
        if guard and frontier and all(label_of.get(c) != "BASE" for c in frontier):
            base_scored = [c for s, c in scored if label_of.get(c) == "BASE"]
            if base_scored:
                frontier = frontier[:-1] + [base_scored[0]]
                if guard_stats is not None:
                    guard_stats["triggers"] = guard_stats.get("triggers", 0) + 1
        if not frontier:
            break
    return best_code


def _task_passes_holdout(task: dict[str, Any], code: str, adapter) -> bool:
    cases = [tuple(c) for c in task["holdout_cases"]]
    previous = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, 5.0)
    try:
        passed = adapter.passes(code, cases, task["holdout_truth"])
    except _ScoreTimeout:
        passed = -1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    return passed == len(cases)


def run_lexical_discovery(
    *,
    pool: list[dict[str, Any]],
    evaluation: list[dict[str, Any]],
    control: list[dict[str, Any]],
    pair_pool: list[dict[str, Any]] | None = None,
    chain_pool: list[dict[str, Any]] | None = None,
    min_pool_fixes: int = 2,
    adapter,
    guard: bool = True,
    require_pool_holdout: bool = True,
) -> dict[str, Any]:
    """Pool discovery -> admission -> held-out transfer and control check for lexical/expr schemas."""
    by_class: dict[str, Any] = {}
    admitted_keys: dict[str, list[tuple]] = {}
    pool_by_class: dict[str, list] = {}
    for task in pool:
        for defect in task["defects"]:
            pool_by_class.setdefault(defect, []).append(task)

    pair_credits: dict[str, dict[tuple, int]] = {}
    pair_tasks_solved = 0
    for task in pair_pool or []:
        pairs = discover_lexical_pairs_for_task(
            task, adapter, require_pool_holdout=require_pool_holdout
        )
        if not pairs:
            continue
        pair_tasks_solved += 1
        credited: set[tuple] = set()
        for key_a, key_b in pairs:
            credited.add(key_a)
            credited.add(key_b)
        for defect in task["defects"]:
            counts = pair_credits.setdefault(defect, {})
            for key in credited:
                counts[key] = counts.get(key, 0) + 1

    chain_credits: dict[str, dict[tuple, int]] = {}
    chain_tasks_solved = 0
    for task in chain_pool or []:
        chain = discover_lexical_chain_for_task(
            task, adapter, require_pool_holdout=require_pool_holdout
        )
        if chain is None:
            continue
        chain_tasks_solved += 1
        for defect in task["defects"]:
            counts = chain_credits.setdefault(defect, {})
            counts[chain] = counts.get(chain, 0) + 1

    eval_by_class: dict[str, list] = {}
    for task in evaluation:
        if len(task["defects"]) == 1:
            eval_by_class.setdefault(task["defects"][0], []).append(task)
        else:
            for defect in task["defects"]:
                eval_by_class.setdefault(defect, []).append(task)

    def solved(task: dict[str, Any], keys: tuple | list, chains: tuple | list = ()) -> bool:
        code = solve_lexical_task(task, adapter, keys, chains, guard=guard)
        return _task_passes_holdout(task, code, adapter)

    admitted_chains: dict[str, list[tuple]] = {}
    raw_by_class: dict[str, dict[str, Any]] = {}
    for defect_class, class_pool in sorted(pool_by_class.items()):
        fix_counts: dict[tuple, int] = {}
        for task in class_pool:
            for key in discover_lexical_for_task(
                task, adapter, require_pool_holdout=require_pool_holdout
            ):
                fix_counts[key] = fix_counts.get(key, 0) + 1
        for key, count in pair_credits.get(defect_class, {}).items():
            fix_counts[key] = fix_counts.get(key, 0) + count

        admitted = [key for key, count in fix_counts.items() if count >= min_pool_fixes]
        admitted_keys[defect_class] = admitted
        class_chains = [
            chain
            for chain, count in chain_credits.get(defect_class, {}).items()
            if count >= min_pool_fixes
        ]
        admitted_chains[defect_class] = class_chains
        raw_by_class[defect_class] = {
            "pool_tasks": len(class_pool),
            "candidate_operators": len(fix_counts),
        }

    all_admitted: list[tuple] = []
    for keys in admitted_keys.values():
        for k in keys:
            if k not in all_admitted:
                all_admitted.append(k)
    all_chains: list[tuple] = []
    for chains in admitted_chains.values():
        for c in chains:
            if c not in all_chains:
                all_chains.append(c)

    for defect_class in sorted(pool_by_class):
        admitted = admitted_keys[defect_class]
        class_chains = admitted_chains[defect_class]
        class_eval = eval_by_class.get(defect_class, [])
        base_solved = sum(1 for t in class_eval if solved(t, ()))
        ext_solved = (
            sum(
                1
                for t in class_eval
                if solved(
                    t,
                    admitted if len(t["defects"]) == 1 else all_admitted,
                    class_chains if len(t["defects"]) == 1 else all_chains,
                )
            )
            if (admitted or class_chains)
            else base_solved
        )
        by_class[defect_class] = {
            "pool_tasks": raw_by_class[defect_class]["pool_tasks"],
            "candidate_operators": raw_by_class[defect_class]["candidate_operators"],
            "admitted_operators": [str(k) for k in admitted],
            "admitted_chains": [str(c) for c in class_chains],
            "eval_tasks": len(class_eval),
            "eval_solved_baseline": base_solved,
            "eval_solved_extended": ext_solved,
        }

    control_base = sum(1 for t in control if solved(t, ()))
    control_ext = (
        sum(1 for t in control if solved(t, all_admitted, all_chains))
        if (all_admitted or all_chains)
        else control_base
    )

    mixed_eval = [t for t in evaluation if len(t["defects"]) == 2]
    mixed = {
        "total": len(mixed_eval),
        "solved_baseline": sum(1 for t in mixed_eval if solved(t, ())),
        "solved_extended": (
            sum(1 for t in mixed_eval if solved(t, all_admitted, all_chains))
            if (all_admitted or all_chains)
            else 0
        ),
    }

    return {
        "family": adapter.family_id,
        "by_class": by_class,
        "pair_pool": {
            "tasks": len(pair_pool or []),
            "tasks_solved_by_pairs": pair_tasks_solved,
        },
        "chain_pool": {
            "tasks": len(chain_pool or []),
            "tasks_solved_by_chains": chain_tasks_solved,
        },
        "mixed_evaluation": mixed,
        "control": {
            "total": len(control),
            "solved_baseline": control_base,
            "solved_extended": control_ext,
        },
    }


# ---------------------------------------------------------------------------
# Shipping family adapter & builder (Family 4 integration alongside Text/Grid/Pricing)
# ---------------------------------------------------------------------------

def build_shipping_task(*, seed: int, level: int) -> dict[str, Any]:
    """Build a discovery-core task for the ``shipping`` family in ``curriculum_lab``."""
    task = generate_task("shipping", level, seed=seed)
    cases = [tuple(c) for c in task["cases"]]
    expected = list(task["expected"])
    shown = [tuple(c) for c in task["shown_cases"]]
    shown_set = set(shown)
    shown_truth = _run_cases(task["reference_code"], "ongkir", shown)
    holdout_cases = [c for c in cases if c not in shown_set]
    truth_by_case = dict(zip(cases, expected))
    holdout_truth = [truth_by_case[c] for c in holdout_cases]
    return {
        "task_id": task["task_id"],
        "family": "shipping",
        "level": level,
        "seed": seed,
        "buggy_code": task["buggy_code"],
        "reference_code": task["reference_code"],
        "shown_cases": [list(c) for c in shown],
        "shown_truth": shown_truth,
        "holdout_cases": [list(c) for c in holdout_cases],
        "holdout_truth": holdout_truth,
        "defects": [r["name"] for r in task["defects"]],
        "entrypoint": "ongkir",
    }


def shipping_rivals(task: dict[str, Any]) -> list[tuple[str, str]]:
    """Construct rival programs for shipping tasks to support discriminating curriculum checks."""
    ref = task.get("reference_code") or ""
    m_lim = re.search(r"berat\s*<=\s*(\d+)", ref)
    m_mult = re.search(r"biaya\s*\*=\s*(\d+)", ref)
    if not (m_lim and m_mult):
        return []
    rivals: list[tuple[str, str]] = []
    cand_free = ref.replace(f"berat <= {m_lim.group(1)}", f"berat < {m_lim.group(1)}")
    if cand_free != ref and cand_free != task.get("buggy_code"):
        rivals.append(("rival_free_boundary", cand_free))
    cand_mult = ref.replace(f"biaya *= {m_mult.group(1)}", "biaya *= 1")
    if cand_mult != ref and cand_mult != task.get("buggy_code"):
        rivals.append(("rival_multiplier_dropped", cand_mult))
    return rivals


def _run_shipping_one(code: str, case: tuple) -> Any:
    try:
        ns: dict[str, Any] = {}
        exec(compile(code, "<ship_cand>", "exec"), ns)
        return ns["ongkir"](*case)
    except Exception:
        return None


class ShippingAdapter:
    """FamilyAdapter-protocol binding for ``shipping``."""

    family_id = "shipping"

    def make_budget(self, task):
        return Budget(
            1_000_000,
            entrypoint="ongkir",
            shown_cases=[tuple(c) for c in task["shown_cases"]],
            shown_expected=list(task["shown_truth"]),
        )

    def passes(self, code, cases, truth) -> int:
        return sum(1 for case, want in zip(cases, truth) if _run_shipping_one(code, tuple(case)) == want)

    def baseline_variants(self, code) -> list:
        return []

    def baseline_catalog_id(self) -> str:
        return "shipping-empty-v0"

    def extra_string_candidates(self, code) -> set:
        return set()


SHIPPING_ADAPTER = ShippingAdapter()
