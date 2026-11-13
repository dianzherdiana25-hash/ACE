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

Stage L2 expansion: four more generic schemas (bool_constant,
name_swap, unary_not, subscript_index) and *pair discovery* —
for tasks no single edit solves, a bounded search over pairs of
score-improving edits; a shown-perfect pair credits BOTH of its
operator keys toward admission (each must still reach the
admission threshold across the pool). This is the mechanism's
answer to masked defect pairs, where each single fix is
individually invisible to the shown set. The operator vocabulary
stays one-edit; pairs exist only at discovery time — at solve
time the existing greedy chains admitted singles across rounds.
"""
from __future__ import annotations

import ast
import copy
import itertools
import signal
from typing import Any

from typing import Protocol


class FamilyAdapter(Protocol):
    """Family machinery for the discovery core (P1 decoupling,
    bench Task 04 design). The core imports NO family module:
    every family-specific operation arrives through an adapter
    the CALLER names, so a preregistration can name it too.

    Task contract (producers must emit): buggy_code,
    shown_cases, shown_truth, holdout_cases, holdout_truth,
    defects, task_id; single-entry-function programs only
    (the entrypoint is the first/only function)."""

    family_id: str

    def make_budget(self, task): ...
    """Budget object with .score(code) -> int = COUNT of
    passed shown cases, under the family's own limits."""

    def passes(self, code, cases, truth) -> int: ...
    """Count of holdout cases passed."""

    def baseline_variants(self, code) -> list: ...
    """The family's PRE-improvement variant generator; the
    extended arm is this plus admitted operators/chains,
    assembled by the core."""

    def baseline_catalog_id(self) -> str: ...
    """Stable identifier of the baseline catalog."""

    def extra_string_candidates(self, code) -> set: ...
    """Family literals seeded into the string-candidate set
    (grid: {'#'}; pricing: empty)."""


def _resolve_adapter(adapter):
    """Explicit adapter wins. The None default resolves to
    the grid adapter through ONE documented legacy point so
    the pre-P1 call sites (and the unchanged test suite)
    keep working; new families must pass their adapter
    explicitly — the G3 preregistration names it."""
    if adapter is not None:
        return adapter
    from .grid_adapter import GRID_ADAPTER
    return GRID_ADAPTER


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


def _string_candidates(code: str,
                       extra: frozenset | set = frozenset()) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Constant) and isinstance(node.value,
                                                         str):
            found.add(node.value)
    # Family literals (e.g. the grid wall character) arrive
    # through the adapter's extra_string_candidates, never
    # from a literal baked into the core (P1, coupling K6).
    found |= set(extra)
    return found


def enumerate_variants(code: str, string_seeds=frozenset()
                       ) -> list[tuple[tuple, str]]:
    """All one-schema-edit variants of `code`, each with its
    abstract operator key. `string_seeds` are the family's
    extra string candidates (via its adapter)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    fn = _function_of(tree)
    if fn is None:
        return []
    params = [a.arg for a in fn.args.args]
    strings = _string_candidates(code, string_seeds)
    scope_names = set(params)
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx,
                                                    ast.Store):
            scope_names.add(sub.id)
        if isinstance(sub, ast.arg):
            scope_names.add(sub.arg)
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
        # boolean constants: flip (stage L2)
        if isinstance(node, ast.Constant) and isinstance(node.value,
                                                         bool):
            new_tree = copy.deepcopy(tree)
            target = _node_at(_function_of(new_tree), path)
            target.value = not node.value  # type: ignore[attr-defined]
            emit(("bool_constant", path, target.value), new_tree)
        # name reference: swap to another in-scope name (stage L2)
        if isinstance(node, ast.Name) and isinstance(node.ctx,
                                                     ast.Load):
            for name in sorted(scope_names - {node.id}):
                new_tree = copy.deepcopy(tree)
                target = _node_at(_function_of(new_tree), path)
                target.id = name  # type: ignore[attr-defined]
                emit(("name_swap", path, name), new_tree)
        # condition negation: wrap a comparison/boolop in `not`,
        # or unwrap an existing one (stage L2)
        if isinstance(node, (ast.Compare, ast.BoolOp)):
            new_tree = copy.deepcopy(tree)
            new_fn = _function_of(new_tree)
            target = _node_at(new_fn, path)
            if target is not None and _replace_at(
                    new_fn, path,
                    ast.UnaryOp(op=ast.Not(),
                                operand=copy.deepcopy(target))):
                emit(("unary_not", path, "wrap"), new_tree)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op,
                                                         ast.Not):
            new_tree = copy.deepcopy(tree)
            new_fn = _function_of(new_tree)
            target = _node_at(new_fn, path)
            if target is not None and _replace_at(
                    new_fn, path, copy.deepcopy(target.operand)):
                emit(("unary_not", path, "unwrap"), new_tree)
        # subscript index anywhere in the body (stage L2): nudge an
        # int-constant slice, or rebind a name slice to a parameter
        if isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(
                    sl.value, int) and not isinstance(sl.value, bool):
                for value in {0, 1, sl.value - 1, sl.value + 1}:
                    if value == sl.value:
                        continue
                    new_tree = copy.deepcopy(tree)
                    target = _node_at(_function_of(new_tree), path)
                    target.slice.value = value  # type: ignore[attr-defined]
                    emit(("subscript_index", path, value), new_tree)
            elif isinstance(sl, ast.Name):
                for name in params:
                    if name == sl.id:
                        continue
                    new_tree = copy.deepcopy(tree)
                    target = _node_at(_function_of(new_tree), path)
                    target.slice.id = name  # type: ignore[attr-defined]
                    emit(("subscript_index", path, name), new_tree)
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


_BINOPS = {"Add": ast.Add, "Sub": ast.Sub, "Mult": ast.Mult}
_COMPARES = {"Lt": ast.Lt, "LtE": ast.LtE, "Gt": ast.Gt,
             "GtE": ast.GtE, "Eq": ast.Eq, "NotEq": ast.NotEq}


def _apply_key_direct(code: str, key: tuple) -> str | None:
    """Apply an operator key directly: parse, locate the site by
    its AST path, apply the schema's transformation with the
    recorded parameter. Semantically identical to enumerating
    variants and matching the key (the roundtrip test proves it
    on real task code), but O(parse) instead of O(all variants) —
    the enumeration-based apply made the expanded schema space
    too slow to measure (a 25-minute run lost to a VM restart).
    """
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
    if schema == "int_constant" and isinstance(node, ast.Constant):
        node.value = parameter
    elif schema == "bool_constant" and isinstance(node,
                                                  ast.Constant):
        node.value = parameter
    elif schema == "string_literal" and isinstance(node,
                                                   ast.Constant):
        node.value = parameter
    elif schema == "name_swap" and isinstance(node, ast.Name):
        node.id = parameter
    elif schema == "binop_swap" and isinstance(node, ast.BinOp):
        node.op = _BINOPS[parameter]()
    elif schema == "binop_unwrap" and isinstance(node, ast.BinOp):
        if not _replace_at(fn, path, copy.deepcopy(node.left)):
            return None
    elif schema == "compare_swap" and isinstance(node, ast.Compare):
        node.ops = [_COMPARES[parameter]()]
    elif schema == "unary_not":
        if parameter == "wrap":
            if not _replace_at(fn, path, ast.UnaryOp(
                    op=ast.Not(), operand=copy.deepcopy(node))):
                return None
        elif isinstance(node, ast.UnaryOp):
            if not _replace_at(fn, path,
                               copy.deepcopy(node.operand)):
                return None
        else:
            return None
    elif schema == "subscript_index" and isinstance(
            node, ast.Subscript):
        if isinstance(parameter, int):
            node.slice.value = parameter  # type: ignore[attr-defined]
        else:
            node.slice.id = parameter  # type: ignore[attr-defined]
    elif schema == "return_indices" and isinstance(node,
                                                   ast.Return):
        names: list[ast.Name] = []
        walk: ast.AST = node.value
        while isinstance(walk, ast.Subscript) and isinstance(
                walk.slice, ast.Name):
            names.append(walk.slice)
            walk = walk.value
        if len(names) != len(parameter):
            return None
        for name_node, name in zip(reversed(names), parameter):
            name_node.id = name
    else:
        return None
    try:
        text = ast.unparse(ast.fix_missing_locations(tree))
    except Exception:
        return None
    return text if text != code else None


def apply_operator(code: str, key: tuple) -> str | None:
    """Re-apply a discovered operator to a fresh program by
    re-locating its site path and transformation. Direct
    application first; the original enumerate-and-match path is
    kept as a fallback so behaviour can only stay identical."""
    direct = _apply_key_direct(code, key)
    if direct is not None:
        return direct
    for candidate_key, text in enumerate_variants(code):
        if candidate_key == key:
            return text
    return None


# --- discovery + admission ----------------------------------------------

def _scored_variants(task: dict[str, Any],
                     adapter) -> tuple[int, list]:
    """(baseline score, [(score, key, text), ...]) over all
    one-edit variants of the task's buggy code."""
    budget = adapter.make_budget(task)
    baseline = _safe_score(budget, task["buggy_code"])
    seeds = adapter.extra_string_candidates(task["buggy_code"])
    scored = [(_safe_score(budget, variant), key, variant)
              for key, variant in
              enumerate_variants(task["buggy_code"], seeds)]
    return baseline, scored


def discover_for_task(task: dict[str, Any],
                      adapter=None) -> list[tuple]:
    """Operator keys whose single application makes the task's
    shown cases fully pass."""
    adapter = _resolve_adapter(adapter)
    shown_total = len(task["shown_cases"])
    _, scored = _scored_variants(task, adapter)
    return [key for score, key, _ in scored if score >= shown_total]


def discover_pairs_for_task(task: dict[str, Any],
                            max_partners: int = 10,
                            adapter=None) -> list[tuple]:
    """Ordered operator-key pairs whose sequential application
    makes the shown cases fully pass, for tasks no single edit
    solves (stage L2, masked pairs). Partners are the strongest
    score-improving single edits; the search is bounded and every
    candidate is scored under the wall-clock guard."""
    adapter = _resolve_adapter(adapter)
    shown_total = len(task["shown_cases"])
    baseline, scored = _scored_variants(task, adapter)
    if any(score >= shown_total for score, _, _ in scored):
        return []
    improvers = sorted(
        ((score, key, text) for score, key, text in scored
         if baseline < score < shown_total),
        key=lambda item: -item[0])[:max_partners]
    budget = adapter.make_budget(task)
    pairs = []
    for _, key_a, text_a in improvers:
        for _, key_b, _ in improvers:
            if key_a == key_b:
                continue
            applied = apply_operator(text_a, key_b)
            if applied is not None and \
                    _safe_score(budget, applied) >= shown_total:
                pairs.append((key_a, key_b))
    return pairs


def discover_chain_for_task(task: dict[str, Any],
                            max_depth: int = 3,
                            adapter=None) -> tuple | None:
    """Composition discovery v2: a greedy chain of edits with
    RE-ENUMERATION at every step (the mechanism whose absence
    L2 diagnosed in pair discovery — pairs drawn from the
    original enumeration scored 0/6, while solve-time greedy,
    which re-enumerates, composed successfully). At each step
    every variant of the CURRENT program is scored; the chain
    advances on the best strictly-improving variant and ends
    when a step reaches shown-perfect. Returns the key chain,
    or None when no single solves it either (a length-1 result
    is single discovery's domain, not a chain) or the walk
    stalls. Deterministic: highest score, enumeration order
    breaks ties."""
    adapter = _resolve_adapter(adapter)
    shown_total = len(task["shown_cases"])
    budget = adapter.make_budget(task)
    current = task["buggy_code"]
    current_score = _safe_score(budget, current)
    if current_score >= shown_total:
        return None
    chain: list[tuple] = []
    for _ in range(max_depth):
        seeds = adapter.extra_string_candidates(current)
        scored = [(_safe_score(budget, text), key, text)
                  for key, text in
                  enumerate_variants(current, seeds)]
        if not scored:
            return None
        best_score, best_key, best_text = max(
            scored, key=lambda item: item[0])
        if best_score >= shown_total:
            chain.append(best_key)
            return tuple(chain) if len(chain) >= 2 else None
        if best_score <= current_score:
            return None
        chain.append(best_key)
        current, current_score = best_text, best_score
    return None


def apply_chain(code: str, chain: tuple) -> str | None:
    """Apply a discovered chain step by step; each key is
    located on the program produced by the previous step."""
    current: str | None = code
    for key in chain:
        if current is None:
            return None
        current = apply_operator(current, key)
    return current


def solve_task(task, adapter, extra_keys=(), extra_chains=(),
               *, max_score_calls: int | None = None,
               trace: list | None = None) -> str:
    """Budgeted per-arm solver — the greedy loop lifted
    out of `run_discovery` (A/B/C v3 build, PR #147
    step 1), behaviour-identical: variant sources are
    the adapter's baseline variants plus any discovered
    operator keys and chains; greedy best-first, 6
    rounds, frontier of the top 4. `max_score_calls`
    caps the number of scoring evaluations (the v3 arms
    share one score-call budget); None is uncapped,
    which is the v4 behaviour the replication gate
    checks. Returns the best code found.

    `trace` (A/B/C v3 build, midday track (a)) is an
    optional caller-owned list recording the PROVENANCE
    of every improving step, in order: ("baseline",
    None) for a baseline-variant step, ("key", key)
    for a discovered-single step, ("chain", chain)
    for a discovered-chain step. Provenance is
    first-source-wins in the `extended_variants` dedup
    order (baseline, then extra_keys in order, then
    extra_chains in order). When `trace` is None no
    provenance is recorded and the solver is
    behaviour-identical to the un-traced form."""
    provenance: dict[str, tuple] = {}

    def extended_variants(code):
        variants = adapter.baseline_variants(code)
        if trace is not None:
            for text in variants:
                provenance.setdefault(text, ("baseline", None))
        for key in extra_keys:
            text = apply_operator(code, key)
            if text is not None and text not in variants:
                variants.append(text)
                if trace is not None:
                    provenance.setdefault(text, ("key", key))
        for chain in extra_chains:
            text = apply_chain(code, chain)
            if text is not None and text not in variants:
                variants.append(text)
                if trace is not None:
                    provenance.setdefault(text, ("chain", chain))
        return variants

    budget = adapter.make_budget(task)
    calls = 0

    def score(code):
        nonlocal calls
        calls += 1
        return _safe_score(budget, code)

    start = task["buggy_code"]
    best_code, best_score = start, score(start)
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
        scored_pairs = []
        for candidate in candidates:
            if max_score_calls is not None and \
                    calls >= max_score_calls:
                break
            scored_pairs.append((score(candidate), candidate))
        if not scored_pairs:
            break
        scored = sorted(scored_pairs, key=lambda pair: -pair[0])
        if scored[0][0] > best_score:
            best_code, best_score = scored[0][1], scored[0][0]
            if trace is not None:
                trace.append(provenance[scored[0][1]])
        frontier = [c for s, c in scored[:4] if s >= best_score]
        if not frontier:
            break
    return best_code


def run_discovery(*, pool: list[dict[str, Any]],
                  evaluation: list[dict[str, Any]],
                  control: list[dict[str, Any]],
                  pair_pool: list[dict[str, Any]] | None = None,
                  chain_pool: list[dict[str, Any]] | None = None,
                  min_pool_fixes: int = 2,
                  adapter=None) -> dict[str, Any]:
    """Pool -> candidate operators -> admission (>= min_pool_fixes
    pool tasks fixed) -> measured transfer on evaluation + control
    regression, all with the extended greedy solver. `pair_pool`
    tasks (stage L2) feed pair discovery only: a shown-perfect
    pair credits both constituent keys toward the admission of
    each of the task's defect classes."""
    by_class: dict[str, Any] = {}
    admitted_keys: dict[str, list[tuple]] = {}
    pool_by_class: dict[str, list] = {}
    for task in pool:
        for defect in task["defects"]:
            pool_by_class.setdefault(defect, []).append(task)
    adapter = _resolve_adapter(adapter)
    pair_credits: dict[str, dict[tuple, int]] = {}
    pair_tasks_solved = 0
    for task in pair_pool or []:
        pairs = discover_pairs_for_task(task, adapter=adapter)
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
        chain = discover_chain_for_task(task, adapter=adapter)
        if chain is None:
            continue
        chain_tasks_solved += 1
        for defect in task["defects"]:
            counts = chain_credits.setdefault(defect, {})
            counts[chain] = counts.get(chain, 0) + 1
    eval_by_class: dict[str, list] = {}
    for task in evaluation:
        for defect in task["defects"]:
            eval_by_class.setdefault(defect, []).append(task)

    def solve_with(task, extra_keys, extra_chains=()):
        # Delegates to the lifted module-level solver
        # (v3 build); uncapped = the v4 behaviour.
        return solve_task(task, adapter, extra_keys,
                          extra_chains)

    def solved(task, extra_keys, extra_chains=()) -> bool:
        code = solve_with(task, extra_keys, extra_chains)
        cases = [tuple(c) for c in task["holdout_cases"]]
        previous = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, 5.0)
        try:
            passed = adapter.passes(code, cases,
                                    task["holdout_truth"])
        except _ScoreTimeout:
            passed = -1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        return passed == len(cases)

    admitted_chains: dict[str, list[tuple]] = {}
    for defect_class, class_pool in sorted(pool_by_class.items()):
        fix_counts: dict[tuple, int] = {}
        for task in class_pool:
            for key in discover_for_task(task, adapter=adapter):
                fix_counts[key] = fix_counts.get(key, 0) + 1
        for key, count in pair_credits.get(defect_class,
                                           {}).items():
            fix_counts[key] = fix_counts.get(key, 0) + count
        admitted = [key for key, count in fix_counts.items()
                    if count >= min_pool_fixes]
        admitted_keys[defect_class] = admitted
        class_chains = [chain for chain, count
                        in chain_credits.get(defect_class,
                                             {}).items()
                        if count >= min_pool_fixes]
        admitted_chains[defect_class] = class_chains
        class_eval = eval_by_class.get(defect_class, [])
        base_solved = sum(1 for t in class_eval if solved(t, []))
        ext_solved = sum(
            1 for t in class_eval
            if solved(t, admitted, class_chains)) \
            if admitted or class_chains else base_solved
        by_class[defect_class] = {
            "pool_tasks": len(class_pool),
            "candidate_operators": len(fix_counts),
            "admitted_operators": [str(k) for k in admitted],
            "admitted_chains": [str(c) for c in class_chains],
            "eval_tasks": len(class_eval),
            "eval_solved_baseline": base_solved,
            "eval_solved_extended": ext_solved}
    all_admitted = [key for keys in admitted_keys.values()
                    for key in keys]
    all_chains = [c for chains in admitted_chains.values()
                  for c in chains]
    control_base = sum(1 for t in control if solved(t, []))
    control_ext = sum(1 for t in control
                      if solved(t, all_admitted, all_chains)) \
        if all_admitted or all_chains else control_base
    mixed_eval = [t for t in evaluation if len(t["defects"]) == 2]
    mixed = {"total": len(mixed_eval),
             "solved_baseline": sum(1 for t in mixed_eval
                                    if solved(t, [])),
             "solved_extended": sum(1 for t in mixed_eval
                                    if solved(t, all_admitted,
                                              all_chains))
             if all_admitted or all_chains else 0}
    return {"by_class": by_class,
            "pair_pool": {"tasks": len(pair_pool or []),
                          "tasks_solved_by_pairs": pair_tasks_solved},
            "chain_pool": {"tasks": len(chain_pool or []),
                           "tasks_solved_by_chains":
                           chain_tasks_solved},
            "mixed_evaluation": mixed,
            "control": {"total": len(control),
                        "solved_baseline": control_base,
                        "solved_extended": control_ext}}
