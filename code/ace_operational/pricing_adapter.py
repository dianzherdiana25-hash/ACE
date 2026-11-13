"""Pricing family adapter for the discovery core (P2).

Binds `operator_discovery` to the pricing family from
`curriculum_lab` through the FamilyAdapter protocol —
the second family the core has ever served, which is the
point of the P1 decoupling.

Two honest labels, stated up front:

- `baseline_variants` is the authored pricing substrate
  (`pricing_substrate.pricing_variants`), bound at the
  B-3 freeze (2026-11-13): the dossier's baseline arm is
  a real mechanism, not an enumeration in disguise. The
  freeze digest is `baseline_catalog_id` below and in the
  freeze record (docs/research/ACE_B3_FREEZE_20261113.md).
  Before the freeze this adapter carried the generic
  schema enumeration as an interim comparator; numbers
  from that configuration were comparator measurements,
  not dossier figures.
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
from .pricing_substrate import pricing_variants
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
        # The frozen authored substrate (B-3 freeze,
        # 2026-11-13). Any change here is substrate v2.
        return pricing_variants(code)

    def baseline_catalog_id(self) -> str:
        return ("pricing-substrate-v1:"
                "658b9022681bcb9e658b7b3f1c85fd3bc8e106718dca8b5ff1fd6b8cffd6bd21")

    def extra_string_candidates(self, code) -> set:
        return set()


PRICING_ADAPTER = PricingAdapter()
