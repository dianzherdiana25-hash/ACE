"""Statement-level operators — discovery v-next PROTOTYPE
(sandbox; design: docs/research/
ACE_DISCOVERY_VNEXT_DESIGN_20261113.md).

The frozen discovery mechanism (operator_discovery.py,
digest 23448d8b... at the B-3 lineage tip) enumerates
expression-level edit schemas only. The statement_order
calibration (Addendum 49) measured the consequence: on a
class whose repair is MOVING a statement, the frozen
mechanism's discovery effect is exactly 0, while a
token-search comparator scores 0/24 and the frozen
substrate baseline ~21%. This module prototypes the
round-2 schema family the calibration's falsification
consequence names: statement-motion operators.

What is here (sandbox scope, stated honestly):

- `enumerate_motion_variants(code)`: every legal
  top-level statement motion of the single entry
  function, as (motion_key, new_code). A motion key is
  ("move_stmt", statement_fingerprint,
  anchor_fingerprint): statements are addressed by a
  STRUCTURAL FINGERPRINT, not by child-index path,
  because a motion invalidates its siblings' indices
  (path rot) — re-location after prior edits must be
  by identity of content, not position.
- A def/use legality filter: a motion is enumerated
  only if, in the resulting statement order, every
  name a statement uses is defined before that use
  (parameters count as defined at entry). This blocks
  use-before-def motions generically; it deliberately
  does NOT block reorderings among statements that
  mutate the same accumulator — that reordering is
  the semantic content this schema family exists to
  express.
- `apply_motion(code, key)`: re-enumerates motions on
  the target program and returns the variant whose
  key matches — the apply_operator contract, carried
  to the statement level.
- A greedy solver loop mirroring run_discovery's
  solve_with in shape (frontier <= 4, <= 6 rounds,
  timeout-guarded scoring), parameterised by a
  variant provider, because the frozen core's solver
  cannot host motion arms without core changes (the
  round-2 production change the design doc proposes;
  a prototype must not edit the frozen core).
- `build_order_task_sandbox(seed)`: the dossier
  construction of Addendum 49 (statement_order class),
  rebuilt here against the byte-identical carried
  frozen generator (curriculum_lab.py on this branch,
  sha256 22304a45... = the B-3 freeze's generator
  component). The carried pricing_adapter /
  pricing_substrate on this branch are likewise
  byte-identical to the freeze (adapter 0f19ff1c...,
  substrate 791fd77f...) so the baseline arm below IS
  the frozen substrate through the frozen adapter.

Measurement harness: `run_sandbox_measurement()` (see
__main__) on the sandbox band seeds 70000-70099 —
disjoint from the calibration band (40000-40023) and
from every G3 application band. This is a sandbox
measurement, not a gate measurement; no gate claim
is made from it.
"""
from __future__ import annotations

import ast
import copy
import signal
from typing import Any, Callable

from .curriculum_lab import _run_cases, generate_task
from .pricing_adapter import PRICING_ADAPTER

# ------------------------------------------------------------------
# sandbox task construction (Addendum 49's class, local rebuild)
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


def build_order_task_sandbox(seed: int) -> dict | None:
    """Core-contract statement_order task from the
    carried frozen generator; validity gate identical
    to Addendum 49's (the variant must fail >= 1 case
    of the reference's grid)."""
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
# structural fingerprints
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
# def/use legality
# ------------------------------------------------------------------


def _defs_uses(stmt: ast.stmt) -> tuple[set, set]:
    """(defined, used) top-level names for one
    statement. An AugAssign target is both used and
    defined. Nested scopes are not modelled (sandbox
    scope: straight-line pricing programs)."""
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
# motion enumeration
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
# greedy solver (mirrors run_discovery.solve_with in shape)
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


def substrate_variants(code: str) -> list:
    """Arm A provider: the frozen substrate, through
    the frozen adapter (byte-identical carries)."""
    return PRICING_ADAPTER.baseline_variants(code)


def augmented_variants(code: str) -> list:
    """Arm B provider: substrate variants + every
    legal statement motion, re-enumerated at every
    frontier program."""
    out = substrate_variants(code)
    for text in motion_variants(code):
        if text not in out:
            out.append(text)
    return out


# ------------------------------------------------------------------
# discovery prototype (admission of motion keys)
# ------------------------------------------------------------------


def motion_key_fixes(task: dict, adapter, key: tuple) -> bool:
    """A motion key FIXES a pool task if, applied as
    the first edit, the substrate greedy then reaches
    shown-perfect and the result passes holdout — the
    stage-I 'fixes' notion, carried to motion keys."""
    moved = apply_motion(task["buggy_code"], key)
    if moved is None:
        return False
    code = solve_with_variants(moved, task, adapter,
                               substrate_variants)
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


def admitted_variants(admitted_keys: list) -> Callable:
    """Arm C provider factory: substrate variants +
    the admitted motion keys, re-located per program
    by fingerprint (apply_motion)."""
    def provider(code: str) -> list:
        out = substrate_variants(code)
        for key in admitted_keys:
            text = apply_motion(code, key)
            if text is not None and text not in out:
                out.append(text)
        return out
    return provider


# ------------------------------------------------------------------
# sandbox measurement (band 70000-70099; NOT a gate run)
# ------------------------------------------------------------------


def run_sandbox_measurement(*, band=range(70000, 70100),
                            pool_size: int = 10,
                            eval_size: int = 30,
                            control_band=range(71000, 71030)
                            ) -> dict:
    """Three arms on fresh statement_order tasks:
    A = frozen substrate through the frozen adapter;
    B = A + every legal motion (reachability ceiling);
    C = A + motion keys DISCOVERED on a disjoint pool
    and admitted under the frozen >=2 rule (transfer).
    Plus a regression control: A vs B on ordinary lab
    pricing singles (the frozen generator's own
    classes) from a separate sandbox band."""
    import time

    from .pricing_adapter import build_pricing_task

    adapter = PRICING_ADAPTER
    built: list = []
    skipped = 0
    for seed in band:
        task = build_order_task_sandbox(seed)
        if task is None:
            skipped += 1
            continue
        built.append(task)
    pool = built[:pool_size]
    evaluation = built[pool_size:pool_size + eval_size]

    def arm(tasks, provider):
        return sum(1 for t in tasks
                   if solved_by(t, adapter, provider))

    result: dict = {
        "stage": "discovery v-next sandbox measurement",
        "band": [band.start, band.stop - 1],
        "built": len(built), "skipped": skipped,
        "pool": len(pool), "evaluation": len(evaluation),
    }
    t0 = time.time()
    result["arm_a_substrate"] = arm(evaluation,
                                    substrate_variants)
    result["arm_b_all_motions"] = arm(evaluation,
                                      augmented_variants)
    admitted = discover_motion_keys(pool, adapter)
    result["admitted_motion_keys"] = [str(k) for k in admitted]
    result["arm_c_admitted"] = arm(
        evaluation, admitted_variants(admitted))
    result["pool_arm_a"] = arm(pool, substrate_variants)
    result["pool_arm_b"] = arm(pool, augmented_variants)
    controls = [build_pricing_task(seed=s, level=1)
                for s in control_band]
    result["control_tasks"] = len(controls)
    result["control_arm_a"] = arm(controls,
                                  substrate_variants)
    result["control_arm_b"] = arm(controls,
                                  augmented_variants)
    result["wall_seconds"] = round(time.time() - t0, 1)
    return result


if __name__ == "__main__":
    import json
    import sys

    report = run_sandbox_measurement()
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1,
                      ensure_ascii=False)
