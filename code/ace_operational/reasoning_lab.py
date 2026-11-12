"""OMEGA-11 — Reasoning, Representation and Algorithm Lab.

A small formal-contrast harness. It pits three repair strategies for
OMEGA-10 tasks against each other under *identical* budgets, on tasks
the strategies may not tune against:

* **grammar** — authored grammar composition: a fixed set of AST-level
  edit operators (boundary flips at spec-mentioned constants, basis
  swaps toward the accumulator variable, constant nudges), composed by
  greedy hill-climbing on the shown cases.
* **token-search** — the contrasting representation proposal: the code
  is a token stream, the operators are single-token substitutions, and
  search is best-first. Nothing about the defect catalog is authored
  into it.
* **random** — the resource-matched control: random token substitutions
  under the same evaluation budget.

Rules of the lab, enforced by the harness (not by trust):

* Solvers see only the public bundle (spec + buggy code + shown cases).
  Fitness during search is computed on shown cases only; the headline
  score is the OMEGA-10 verifier over *all* cases, computed by the
  harness after the solver returns — independent evaluation.
* Every solver gets the same evaluation budget. A solver that exceeds
  it is marked ABSTAIN (budget violation), never scored.
* The hypothesis and its decision rule are declared before the run.
  The outcome is SUPPORTED, FALSIFIED or INCONCLUSIVE by that rule —
  falsification is a first-class result.
* **Claims discipline (the OMEGA-11 gate):** the report's novelty and
  generalization claims are NOT_ASSESSED, and `promote_claims` refuses
  to raise them without custody and transfer-proof artifacts. Winning a
  small contrast on generated tasks is data, not a novelty proof.
"""
from __future__ import annotations

import ast
import json
import random
import re
from typing import Any, Callable

from ace_operational.curriculum_lab import generate_task, split_of, verify_candidate


class LabError(Exception):
    pass


class ClaimsGateError(LabError):
    pass


# ---------------------------------------------------------------------------
# Shown-case fitness (the only signal solvers may use)
# ---------------------------------------------------------------------------

class Budget:
    """Shown-case fitness with a hard evaluation cap.

    The Budget is constructed by the harness from the *shown* cases and
    their expected values only — holdout cases and their answers never
    enter the solver's world, so there is nothing to peek at.
    """

    def __init__(self, limit: int, *, entrypoint: str,
                 shown_cases: list[tuple], shown_expected: list[Any]):
        self.limit = limit
        self.used = 0
        self._entrypoint = entrypoint
        self._shown = list(zip(shown_cases, shown_expected))

    def score(self, code: str) -> int:
        self.used += 1
        try:
            namespace: dict[str, Any] = {}
            exec(compile(code, "<cand>", "exec"), namespace)
            fn = namespace[self._entrypoint]
            return sum(1 for case, expected in self._shown if fn(*case) == expected)
        except Exception:
            return -1


# ---------------------------------------------------------------------------
# Solvers. Signature: solver(task, budget) -> repaired code or None.
# ---------------------------------------------------------------------------

def _spec_numbers(spec: str) -> set[int]:
    return {int(n) for n in re.findall(r"\d+", spec)}


def _transform_variants(code: str, spec: str) -> list[str]:
    """The authored grammar: every single-operator variant of the code."""
    variants: list[str] = []
    tree = ast.parse(code)
    numbers = _spec_numbers(spec)
    lines = code.splitlines()

    # Operator 1: boundary flips at constants the spec mentions.
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            comp = node.comparators[0]
            if isinstance(comp, ast.Constant) and comp.value in numbers:
                for old, new in ((">=", ">"), (">", ">="), ("<=", "<"), ("<", "<=")):
                    if old in code:
                        variants.append(code.replace(old, new, 1))
    # Operator 2: basis swap — a parameter used where the accumulator
    # should be, inside an augmented assignment's right-hand side.
    func = next((n for n in tree.body if isinstance(n, ast.FunctionDef)), None)
    if func is not None:
        params = [a.arg for a in func.args.args]
        accumulators = [t.id for stmt in func.body if isinstance(stmt, ast.Assign)
                        for t in stmt.targets if isinstance(t, ast.Name)
                        and isinstance(stmt.value, ast.Name)
                        and stmt.value.id in params]
        if accumulators:
            acc = accumulators[0]
            for param in params:
                pattern = re.compile(rf"\b{re.escape(param)}\b")
                for i, line in enumerate(lines):
                    if (" += " in line or " -= " in line) and pattern.search(line):
                        changed = lines.copy()
                        changed[i] = pattern.sub(acc, line, count=1)
                        variants.append("\n".join(changed) + "\n")
    # Operator 3: constant nudges (+-1) at spec-mentioned constants.
    for n in numbers:
        for delta in (-1, 1):
            variants.append(re.sub(rf"\b{n}\b", str(n + delta), code, count=1))
    # De-duplicate, keep order.
    seen: set[str] = set()
    unique = []
    for v in variants:
        if v != code and v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def solver_grammar(task: dict[str, Any], budget: Budget) -> str | None:
    """Greedy composition of authored operators, hill-climbing on shown."""
    current = task["buggy_code"]
    best = budget.score(current)
    improved = True
    while improved:
        improved = False
        for variant in _transform_variants(current, task["spec"]):
            if budget.used >= budget.limit:
                return current if best > 0 else None
            score = budget.score(variant)
            if score > best:
                current, best, improved = variant, score, True
                break
    return current


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|>=|<=|==|!=|>|<|\+=|-=|\*=|//|[+\-*/%=():.,]|\s+|[^\sA-Za-z0-9_]")


def _tokenize(code: str) -> list[str]:
    return _TOKEN_RE.findall(code)


def _token_variants(code: str, *, restrict_vocab: bool = False) -> list[str]:
    tokens = _tokenize(code)
    names = sorted({t for t in tokens if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t)})
    numbers = sorted({t for t in tokens if t.isdigit()})
    swaps: list[tuple[str, str]] = []
    for op in (">=", ">", "<=", "<"):
        for other in (">=", ">", "<=", "<"):
            if op != other:
                swaps.append((op, other))
    if not restrict_vocab:
        for name in names:
            for other in names:
                if name != other:
                    swaps.append((name, other))
        for num in numbers:
            swaps.append((num, str(int(num) + 1)))
            swaps.append((num, str(max(0, int(num) - 1))))
    variants = []
    seen: set[str] = set()
    for old, new in swaps:
        for i, tok in enumerate(tokens):
            if tok == old:
                changed = tokens.copy()
                changed[i] = new
                joined = "".join(changed)
                if joined not in seen:
                    seen.add(joined)
                    variants.append(joined)
    return variants


def solver_token_search(task: dict[str, Any], budget: Budget, *,
                        first_improvement_only: bool = False,
                        restrict_vocab: bool = False) -> str | None:
    """Best-first search over single-token substitutions."""
    start = task["buggy_code"]
    frontier = [(budget.score(start), start)]
    seen = {start}
    best_code, best_score = start, frontier[0][0]
    while frontier and budget.used < budget.limit:
        frontier.sort(key=lambda p: -p[0])
        score, code = frontier.pop(0)
        if first_improvement_only and score > best_score:
            return code
        for variant in _token_variants(code, restrict_vocab=restrict_vocab):
            if variant in seen:
                continue
            seen.add(variant)
            if budget.used >= budget.limit:
                break
            vscore = budget.score(variant)
            if vscore > best_score:
                best_code, best_score = variant, vscore
                if vscore == len(task["shown_cases"]):
                    return variant
            frontier.append((vscore, variant))
    return best_code if best_score > 0 else None


def solver_random(task: dict[str, Any], budget: Budget) -> str | None:
    rng = random.Random(task.get("seed", 0))
    current = task["buggy_code"]
    best = budget.score(current)
    best_code = current
    while budget.used < budget.limit:
        variants = _token_variants(current)
        if not variants:
            break
        candidate = rng.choice(variants)
        score = budget.score(candidate)
        if score > best:
            best, best_code = score, candidate
            current = candidate
    return best_code if best > 0 else None


SOLVERS: dict[str, Callable[..., str | None]] = {
    "grammar": solver_grammar,
    "token-search": solver_token_search,
    "random": solver_random,
}


# ---------------------------------------------------------------------------
# Experiment harness
# ---------------------------------------------------------------------------

def run_experiment(*, families: list[str], levels: list[int], seeds: list[int],
                   budget_limit: int = 60,
                   hypothesis: dict[str, Any] | None = None,
                   solvers: dict[str, Callable[..., str | None]] | None = None,
                   split: str = "holdout") -> dict[str, Any]:
    """Run the contrast on generated tasks of one split, budget-matched.

    hypothesis: {"subject": solver name, "claim": "solves_at_least_as_many_as",
                 "reference": solver name, "margin": int}
    Decision rule (declared here, before any run): SUPPORTED if
    subject_solved - reference_solved >= margin; FALSIFIED if
    reference_solved - subject_solved >= margin; else INCONCLUSIVE.
    """
    solvers = solvers or SOLVERS
    hypothesis = hypothesis or {"subject": "token-search",
                                "claim": "solves_at_least_as_many_as",
                                "reference": "grammar", "margin": 2}
    tasks = []
    for family in families:
        for level in levels:
            for seed in seeds:
                try:
                    task = generate_task(family, level, seed=seed)
                except Exception:
                    continue
                if split_of(task) == split:
                    tasks.append(task)
    per_solver: dict[str, dict[str, Any]] = {}
    for name, solver in solvers.items():
        solved = 0
        per_family: dict[str, dict[str, int]] = {}
        abstained = 0
        details = []
        for task in tasks:
            shown = [tuple(c) for c in task["shown_cases"]]
            expected_by_case = {tuple(c): e for c, e in
                                zip(task["cases"], task["expected"])}
            budget = Budget(budget_limit, entrypoint=task["entrypoint"],
                            shown_cases=shown,
                            shown_expected=[expected_by_case[c] for c in shown])
            public_task = {k: task[k] for k in
                           ("buggy_code", "spec", "shown_cases", "entrypoint", "seed")}
            repaired = solver(public_task, budget)
            if budget.used > budget_limit:
                abstained += 1
                details.append({"task": task["task_id"], "result": "abstain-budget"})
                continue
            if repaired is None:
                outcome = verify_candidate(task, task["buggy_code"])
                details.append({"task": task["task_id"], "result": "no-repair",
                                "passed": outcome["passed"]})
                fam = per_family.setdefault(task["family"], {"solved": 0, "total": 0})
                fam["total"] += 1
                continue
            outcome = verify_candidate(task, repaired)
            full = outcome["passed"] == outcome["total"]
            solved += 1 if full else 0
            fam = per_family.setdefault(task["family"], {"solved": 0, "total": 0})
            fam["solved"] += 1 if full else 0
            fam["total"] += 1
            details.append({"task": task["task_id"],
                            "result": "solved" if full else "partial",
                            "passed": outcome["passed"], "total": outcome["total"],
                            "budget_used": budget.used})
        per_solver[name] = {"solved": solved, "tasks": len(tasks),
                            "per_family": per_family, "abstained": abstained,
                            "details": details}
    subject = per_solver[hypothesis["subject"]]["solved"]
    reference = per_solver[hypothesis["reference"]]["solved"]
    margin = hypothesis["margin"]
    if subject - reference >= margin:
        verdict = "SUPPORTED"
    elif reference - subject >= margin:
        verdict = "FALSIFIED"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "split": split, "budget_limit": budget_limit,
        "task_count": len(tasks),
        "hypothesis": hypothesis,
        "hypothesis_verdict": verdict,
        "solvers": {name: {k: v for k, v in data.items() if k != "details"}
                    for name, data in per_solver.items()},
        "details": {name: data["details"] for name, data in per_solver.items()},
        "claims": {"novelty": "NOT_ASSESSED", "generalization": "NOT_ASSESSED"},
        "claims_note": ("Per the OMEGA-11 gate, novelty and generalization stay "
                        "NOT_ASSESSED until custody and transfer proof exist. "
                        "The numbers above are engineering data from generated "
                        "tasks, not capability claims."),
    }


def promote_claims(report: dict[str, Any], *, custody_proof: Any = None,
                   transfer_proof: Any = None) -> dict[str, Any]:
    """The gate: claims rise only with custody + transfer proof attached."""
    if not custody_proof or not transfer_proof:
        raise ClaimsGateError(
            "novelty/generalization claims require custody and transfer proof; "
            "they remain NOT_ASSESSED")
    raise ClaimsGateError(
        "proof verification is not implemented in this package; claims remain "
        "NOT_ASSESSED")
