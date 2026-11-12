"""Pricing family adapter for the discovery core (P2).

Binds `operator_discovery` to the pricing family from
`curriculum_lab` through the FamilyAdapter protocol —
the second family the core has ever served, which is the
point of the P1 decoupling.

Two honest labels, stated up front:

- `baseline_variants` is the INTERIM comparator: the
  generic schema enumeration (`enumerate_variants`). The
  authored pricing substrate (stage B-3, bench Task 06
  design) replaces it at the B-3 freeze, so the dossier's
  baseline arm becomes a real mechanism and not an
  enumeration in disguise. Until then, any number
  produced with this adapter is a comparator measurement,
  not a dossier figure.
- Defect classes are the lab's own three:
  threshold_boundary, tax_basis, member_basis.

Task builder: `build_pricing_task` translates a
curriculum_lab task into the discovery core's contract
(buggy_code, shown_cases/shown_truth, holdout_cases/
holdout_truth, defects as class names, task_id). Shown
truth is computed from the reference program; holdout is
every generated case the lab did not show, with the
lab's own expected values — the lab's shown-selection
already guarantees partial fixes fail shown cases (the
identifiability property), and holdout is never visible
to the budget.
"""
from __future__ import annotations

from typing import Any

from .curriculum_lab import _run_cases, generate_task
from .operator_discovery import enumerate_variants
from .reasoning_lab import Budget


def build_pricing_task(*, seed: int, level: int) -> dict[str, Any]:
    task = generate_task("pricing", level, seed=seed)
    cases = [tuple(c) for c in task["cases"]]
    expected = list(task["expected"])
    shown = [tuple(c) for c in task["shown_cases"]]
    shown_set = set(shown)
    shown_truth = _run_cases(task["reference_code"], "total", shown)
    holdout_cases = [c for c in cases if c not in shown_set]
    truth_by_case = dict(zip(cases, expected))
    holdout_truth = [truth_by_case[c] for c in holdout_cases]
    return {
        "task_id": task["task_id"],
        "family": "pricing",
        "level": level,
        "seed": seed,
        "buggy_code": task["buggy_code"],
        "reference_code": task["reference_code"],
        "shown_cases": [list(c) for c in shown],
        "shown_truth": shown_truth,
        "holdout_cases": [list(c) for c in holdout_cases],
        "holdout_truth": holdout_truth,
        "defects": [r["name"] for r in task["defects"]],
    }


def _run_one(code: str, case: tuple) -> Any:
    try:
        namespace: dict[str, Any] = {}
        exec(compile(code, "<cand>", "exec"), namespace)
        return namespace["total"](*case)
    except Exception:
        return None


class PricingAdapter:
    family_id = "pricing"

    def make_budget(self, task):
        return Budget(1_000_000, entrypoint="total",
                      shown_cases=[tuple(c)
                                   for c in task["shown_cases"]],
                      shown_expected=list(task["shown_truth"]))

    def passes(self, code, cases, truth) -> int:
        return sum(1 for case, want in zip(cases, truth)
                   if _run_one(code, tuple(case)) == want)

    def baseline_variants(self, code) -> list:
        # INTERIM comparator (see module docstring): the
        # generic schema enumeration, change-only and
        # deduplicated, mirroring the substrate union
        # contract. Rebound to pricing_variants at the
        # B-3 freeze.
        out: list[str] = []
        for _, text in enumerate_variants(code):
            if text != code and text not in out:
                out.append(text)
        return out

    def baseline_catalog_id(self) -> str:
        return "generic-schema-enumeration-interim"

    def extra_string_candidates(self, code) -> set:
        return set()


PRICING_ADAPTER = PricingAdapter()
