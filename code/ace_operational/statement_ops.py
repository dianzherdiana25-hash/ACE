"""Statement-level operators — the round-2 schema family,
lifted from sandbox prototype to mechanism module
(gate design: docs/research/
ACE_ROUND2_GATE_DESIGN_20261113.md §2; prototype:
statement_ops_prototype.py on the discovery v-next
branch, whose sandbox confirmation is
discovery-round2-01, ROUND2_CONFIRMED).

The frozen discovery mechanism enumerates
expression-level edit schemas only; the statement_order
calibration (Addendum 49) measured the consequence —
on a class whose repair is MOVING a statement, the
frozen mechanism's discovery effect is exactly 0.
This module is the schema family that calibration's
falsification consequence names, ported faithfully
from the prototype: same fingerprints, same def/use
legality filter, same enumeration order, same
admission semantics. Behaviour on the sandbox band
is therefore the prototype's behaviour by
construction; the gate's replication guard (§3 of
the design) is the empirical check, and it is a
LATER stage — nothing in this module has been run
against the gate bands.

Architecture choice (recorded per the lift brief):

- The schema lives HERE, not inside
  `operator_discovery.py`, and the core solver is
  NOT modified: `solve_task` / `run_discovery`
  keep their exact frozen shape, and no core code
  path imports this module at load time. The grid
  family's behaviour cannot change, because the
  only files the grid path executes are untouched
  and this module is reachable solely through the
  pricing family's explicit motion path
  (`PricingAdapter.motion_variants`, the core's
  re-exported `discover_motion_keys` /
  `apply_motion` / `enumerate_motion_variants`
  wrappers, and the provider factories below).
- `operator_discovery.py` gains only an appended
  re-export section (lazy imports), which is what
  makes its bytes the *lifted* bytes the design's
  manifest names as component 1.
- `PricingAdapter.baseline_variants` is byte-for-
  byte the frozen substrate call it always was;
  the adapter gains a separate `motion_variants`
  method. The B-3 substrate freeze
  (`pricing_substrate.py`, freeze digest
  658b9022...) is not touched.
- Admission is the frozen rule, unchanged: a
  motion key is admitted iff it fixes
  >= min_pool_fixes (default 2) independent pool
  tasks, where *fixes* is the stage-I notion
  carried to motion keys (see `motion_key_fixes`).

Manifest coverage note (named, not hidden): the
design §2 construction hashes the lifted
`operator_discovery.py`, the frozen
`grid_adapter.py`, the (lift-extended)
`pricing_adapter.py`, the ASCII parameter string,
and the ASCII substrate freeze digest — it does
NOT hash this file. `compute_lift_manifest`
implements the construction exactly as designed;
whether the preregistration should extend the
construction with a sixth component (this file)
is a decision for the ratification stage, recorded
here so it is made with open eyes.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import signal
from pathlib import Path
from typing import Any, Callable

from .curriculum_lab import _run_cases, generate_task

# The frozen admission/signature parameters of the
# lifted core (design §2). These strings are part
# of the lift manifest construction — do not
# reformat them.
MANIFEST_PARAMS = "min_pool_fixes=2,max_rounds=6,frontier=4"
SUBSTRATE_FREEZE_DIGEST = \
    "658b9022681bcb9e658b7b3f1c85fd3bc8e106718dca8b5ff1fd6b8cffd6bd21"


# ------------------------------------------------------------------
# sandbox task construction (Addendum 49's class, ported
# verbatim from the prototype)
# ------------------------------------------------------------------


def apply_statement_order_defect(reference_code: str):
    """Move the final top-level AugAssign (the tax
    statement) to directly after the opening assignment.
    Returns the variant code, or None if the reference
    does not have the expected shape."""
    tree = ast.parse(reference_code)
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef)), None)
    if fn is None:
        return None
    body = fn.body
    tax_idx = None
    for i, stmt in enumerate(body):
        if isinstance(stmt, ast.AugAssign) and \
                isinstance(stmt.op, ast.Add):
            tax_idx = i
    if tax_idx is None or tax_idx < 2:
        return None
    new_tree = copy.deepcopy(tree)
    new_fn = next(n for n in new_tree.body
                  if isinstance(n, ast.FunctionDef))
    tax_stmt = new_fn.body.pop(tax_idx)
    new_fn.body.insert(1, tax_stmt)
    return ast.unparse(ast.fix_missing_locations(new_tree))


def build_order_task(seed: int) -> dict | None:
    """Core-contract statement_order task from the
    frozen generator; validity gate identical to
    Addendum 49's (the variant must fail >= 1 case
    of the reference's grid). The prototype's
    `build_order_task_sandbox`, unchanged."""
    lab = generate_task("pricing", 1, seed=seed)
    reference = lab["reference_code"]
    buggy = apply_statement_order_defect(reference)
    if buggy is None or buggy == reference:
        return None
    cases = [tuple(c) for c in lab["cases"]]
    shown = [tuple(c) for c in lab["shown_cases"]]
    shown_set = set(shown)
    holdout = [c for c in cases if c not in shown_set]
    ref_truth = _run_cases(reference, "total", cases)
    truth_by_case = dict(zip(cases, ref_truth))
    buggy_runs = _run_cases(buggy, "total", cases)
    discriminates = any(g != truth_by_case[c]
                        for g, c in zip(buggy_runs, cases))
    if not discriminates:
        return None
    return {
        "task_id": f"pricing-order-{seed}",
        "buggy_code": buggy,
        "reference_code": reference,
        "shown_cases": shown,
        "shown_truth": [truth_by_case[c] for c in shown],
        "holdout_cases": holdout,
        "holdout_truth": [truth_by_case[c] for c in holdout],
        "defects": ["statement_order"],
        "entrypoint": "total",
    }


# ------------------------------------------------------------------
# structural fingerprints (prototype, verbatim)
# ------------------------------------------------------------------


def _leftmost_leaf_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.BinOp):
        node = node.left
    return node.id if isinstance(node, ast.Name) else None


def statement_fingerprint(stmt: ast.stmt) -> tuple:
    """Structural identity of a top-level statement:
    kind + binding target + operator + the leftmost
    leaf name of its value/test. Constants are
    deliberately NOT part of the fingerprint: a motion
    key must generalise across the family's parameter
    variation (the tax rate differs per program; a key
    carrying '12' could never transfer to an '11'
    program). Granularity is the trade: coarser
    fingerprints transfer, finer ones locate more
    precisely — round 2 fixes this middle point and
    the occurrence suffix (see _fingerprints)
    disambiguates residual collisions within a body."""
    if isinstance(stmt, ast.AugAssign) and \
            isinstance(stmt.target, ast.Name):
        return ("augassign", stmt.target.id,
                type(stmt.op).__name__,
                _leftmost_leaf_name(stmt.value))
    if isinstance(stmt, ast.Assign) and \
            len(stmt.targets) == 1 and \
            isinstance(stmt.targets[0], ast.Name):
        return ("assign", stmt.targets[0].id,
                _leftmost_leaf_name(stmt.value))
    if isinstance(stmt, ast.Return):
        return ("return",)
    if isinstance(stmt, ast.If):
        return ("if", _leftmost_leaf_name(stmt.test))
    return (type(stmt).__name__.lower(),)


def _fingerprints(body: list[ast.stmt]) -> list[tuple]:
    """Per-statement fingerprints, unique within the
    body: collisions gain an occurrence suffix."""
    seen: dict[tuple, int] = {}
    out: list[tuple] = []
    for stmt in body:
        fp = statement_fingerprint(stmt)
        seen[fp] = seen.get(fp, 0) + 1
        if seen[fp] > 1:
            fp = fp + (f"#{seen[fp]}",)
        out.append(fp)
    return out


# ------------------------------------------------------------------
# def/use legality (prototype, verbatim)
# ------------------------------------------------------------------


def _defs_uses(stmt: ast.stmt) -> tuple[set, set]:
    """(defined, used) top-level names for one
    statement. An AugAssign target is both used and
    defined. Nested scopes are not modelled (scope:
    straight-line pricing programs)."""
    defined: set = set()
    used: set = set()
    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            for node in ast.walk(target):
                if isinstance(node, ast.Name):
                    defined.add(node.id)
    elif isinstance(stmt, ast.AugAssign) and \
            isinstance(stmt.target, ast.Name):
        defined.add(stmt.target.id)
        used.add(stmt.target.id)
    for node in ast.walk(stmt):
        if isinstance(node, ast.Name) and \
                isinstance(node.ctx, ast.Load):
            used.add(node.id)
    return defined, used


def _order_is_legal(body: list[ast.stmt],
                    params: set) -> bool:
    """True iff every used name is defined before its
    use in this statement order (params pre-defined)."""
    defined = set(params)
    for stmt in body:
        defs, uses = _defs_uses(stmt)
        if not uses <= defined:
            return False
        defined |= defs
    return True


# ------------------------------------------------------------------
# motion enumeration (prototype, verbatim)
# ------------------------------------------------------------------

_MOVABLE = (ast.Assign, ast.AugAssign)
_END = ("end",)


def enumerate_motion_variants(code: str) -> list:
    """All legal single statement motions of the entry
    function's top-level body, as (key, new_code),
    deterministic order, change-only, deduplicated.
    Key: ("move_stmt", moved_fingerprint,
    anchor_fingerprint | ("end",)) — insert the moved
    statement directly before the anchor statement
    (or at the last position before a trailing
    Return)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    fns = [n for n in tree.body
           if isinstance(n, ast.FunctionDef)]
    if len(fns) != 1:
        return []
    fn = fns[0]
    body = fn.body
    if len(body) < 3:
        return []
    params = {a.arg for a in fn.args.args}
    fps = _fingerprints(body)
    fp_by_id = {id(stmt): fp for stmt, fp in zip(body, fps)}
    out: list = []
    seen_texts: set = set()
    for i, stmt in enumerate(body):
        if not isinstance(stmt, _MOVABLE):
            continue
        rest = body[:i] + body[i + 1:]
        for insert_at in range(len(rest) + 1):
            if insert_at == i:
                continue  # the statement's own slot: no-op
            candidate = rest[:insert_at] + [stmt] + \
                rest[insert_at:]
            # A moved statement never lands after a
            # Return (dead code is not a repair).
            if any(isinstance(s, ast.Return)
                   for s in candidate[:insert_at]):
                continue
            if not _order_is_legal(candidate, params):
                continue
            anchor = fp_by_id[id(candidate[insert_at + 1])] \
                if insert_at + 1 < len(candidate) else _END
            new_tree = copy.deepcopy(tree)
            new_fn = next(n for n in new_tree.body
                          if isinstance(n, ast.FunctionDef))
            moved = new_fn.body.pop(i)
            new_fn.body.insert(insert_at, moved)
            try:
                text = ast.unparse(
                    ast.fix_missing_locations(new_tree))
            except Exception:
                continue
            if text == code or text in seen_texts:
                continue
            seen_texts.add(text)
            key = ("move_stmt", fps[i], anchor)
            out.append((key, text))
    return out


def motion_variants(code: str) -> list:
    """Just the variant texts (solver provider form)."""
    return [text for _, text in enumerate_motion_variants(code)]


def apply_motion(code: str, key: tuple) -> str | None:
    """Re-locate a motion key on a fresh program by
    re-enumeration and fingerprint match — the
    apply_operator contract at statement level."""
    for candidate_key, text in enumerate_motion_variants(code):
        if candidate_key == key:
            return text
    return None


# ------------------------------------------------------------------
# greedy solver (mirrors the frozen loop's shape, as in
# the prototype; the core solver is NOT used here and
# NOT modified)
# ------------------------------------------------------------------


class _ScoreTimeout(Exception):
    pass


def _alarm_handler(signum, frame):  # noqa: ARG001
    raise _ScoreTimeout()


def _safe_score(budget: Any, code: str,
                seconds: float = 1.0) -> int:
    previous = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return budget.score(code)
    except _ScoreTimeout:
        return -1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def solve_with_variants(start_code: str, task: dict,
                        adapter,
                        variant_fn: Callable,
                        *, max_rounds: int = 6) -> str:
    """Greedy best-first repair: frontier <= 4, score
    = shown cases passed (adapter budget), exactly the
    frozen solver loop's shape with the variant
    provider injected."""
    budget = adapter.make_budget(task)
    best_code, best_score = start_code, _safe_score(
        budget, start_code)
    frontier, seen = [start_code], {start_code}
    for _ in range(max_rounds):
        if best_score >= len(task["shown_cases"]):
            break
        candidates: list = []
        for code in frontier:
            for variant in variant_fn(code):
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
        frontier = [c for s, c in scored[:4]
                    if s >= best_score]
        if not frontier:
            break
    return best_code


def solved_by(task: dict, adapter, variant_fn) -> bool:
    """Holdout verdict under the adapter, with the
    frozen protocol's 5 s guard."""
    code = solve_with_variants(task["buggy_code"], task,
                               adapter, variant_fn)
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


# ------------------------------------------------------------------
# variant providers (adapter-parametric forms of the
# prototype's three arms)
# ------------------------------------------------------------------


def baseline_provider(adapter) -> Callable:
    """Arm A provider factory: the family's frozen
    baseline variants, through its adapter."""
    def provider(code: str) -> list:
        return adapter.baseline_variants(code)
    return provider


def augmented_provider(adapter) -> Callable:
    """Reachability-ceiling provider factory: baseline
    variants + every legal statement motion,
    re-enumerated at every frontier program."""
    def provider(code: str) -> list:
        out = adapter.baseline_variants(code)
        for text in motion_variants(code):
            if text not in out:
                out.append(text)
        return out
    return provider


def admitted_provider(adapter,
                      admitted_keys: list) -> Callable:
    """Transfer-arm provider factory: baseline variants
    + the admitted motion keys, re-located per program
    by fingerprint (apply_motion)."""
    def provider(code: str) -> list:
        out = adapter.baseline_variants(code)
        for key in admitted_keys:
            text = apply_motion(code, key)
            if text is not None and text not in out:
                out.append(text)
        return out
    return provider


# ------------------------------------------------------------------
# motion discovery + admission (prototype, verbatim
# semantics; the frozen >= min_pool_fixes rule)
# ------------------------------------------------------------------


def motion_key_fixes(task: dict, adapter, key: tuple) -> bool:
    """A motion key FIXES a pool task if, applied as
    the first edit, the baseline greedy then reaches
    shown-perfect and the result passes holdout — the
    stage-I 'fixes' notion, carried to motion keys."""
    moved = apply_motion(task["buggy_code"], key)
    if moved is None:
        return False
    code = solve_with_variants(moved, task, adapter,
                               baseline_provider(adapter))
    if _safe_score(adapter.make_budget(task), code) < \
            len(task["shown_cases"]):
        return False
    cases = [tuple(c) for c in task["holdout_cases"]]
    return adapter.passes(code, cases,
                          task["holdout_truth"]) == len(cases)


def discover_motion_keys(pool: list, adapter,
                         *, min_pool_fixes: int = 2) -> list:
    """Candidate motion keys from the pool's own
    enumerations; a key is admitted iff it fixes
    >= min_pool_fixes independent pool tasks (the
    frozen admission rule, unchanged)."""
    fix_counts: dict = {}
    for task in pool:
        credited: set = set()
        for key, _ in enumerate_motion_variants(
                task["buggy_code"]):
            if key in credited:
                continue
            if motion_key_fixes(task, adapter, key):
                credited.add(key)
        for key in credited:
            fix_counts[key] = fix_counts.get(key, 0) + 1
    return sorted(key for key, count in fix_counts.items()
                  if count >= min_pool_fixes)


# ------------------------------------------------------------------
# lift manifest (design §2 construction, exactly)
# ------------------------------------------------------------------


def compute_lift_manifest(root: Path | None = None) -> str:
    """SHA-256 hex digest of the lifted core, in the
    design §2 construction, in order, no separators:
    the lifted operator_discovery.py bytes, the
    frozen grid_adapter.py bytes, the (lift-extended)
    pricing_adapter.py bytes, ASCII MANIFEST_PARAMS,
    ASCII substrate freeze digest. `root` overrides
    the package directory (tests)."""
    base = Path(root) if root is not None else \
        Path(__file__).resolve().parent
    h = hashlib.sha256()
    for name in ("operator_discovery.py", "grid_adapter.py",
                 "pricing_adapter.py"):
        h.update((base / name).read_bytes())
    h.update(MANIFEST_PARAMS.encode("ascii"))
    h.update(SUBSTRATE_FREEZE_DIGEST.encode("ascii"))
    return h.hexdigest()
