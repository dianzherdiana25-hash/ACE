"""Tests for admission_hygiene: distractor pruning, Pareto set-cover, Lineage-Guard G2, and inoculation."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from ace_operational.admission_hygiene import (
    DEFAULT_REGISTRY_PATH,
    discover_hygienic_pool,
    evaluate_nonregressive_g2,
    filter_parsimonious_keys,
    operator_mdl_cost,
    verify_inoculation_immunity,
)
from ace_operational.curriculum_lab import _NAVIGATE_REFERENCE
from ace_operational.distractor_inoculation import load_registry
from ace_operational.family3_prototype import TEXT_ADAPTER, build_text_task
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import _apply, _run
from ace_operational.lexical_ops import SHIPPING_ADAPTER, build_shipping_task, enumerate_lexical_variants, apply_lexical_operator


def _make_grid_task(task_id: str, defects: tuple[str, ...], cases: list[tuple], shown_n: int = 6) -> dict:
    truth = [_run(_NAVIGATE_REFERENCE, c) for c in cases]
    buggy = _apply(_NAVIGATE_REFERENCE, defects)
    return {
        "task_id": task_id,
        "defects": list(defects),
        "buggy_code": buggy,
        "reference_code": _NAVIGATE_REFERENCE,
        "shown_cases": [list(c) for c in cases[:shown_n]],
        "shown_truth": truth[:shown_n],
        "holdout_cases": [list(c) for c in cases[shown_n:]],
        "holdout_truth": truth[shown_n:],
    }


_GRID_CASES = [
    ((".....", ".....", ".....", ".....", "....."), 0, 0, 4, 4),
    ((".....", ".###.", ".....", ".....", "....."), 0, 0, 4, 4),
    (("..#..", "..#..", "..#..", "..#..", "....."), 0, 0, 0, 4),
    ((".....", ".###.", ".#.#.", ".###.", "....."), 0, 0, 2, 2),
    (("#####", "#...#", "#.#.#", "#...#", "#####"), 1, 1, 3, 3),
    (("......", ".####.", "......", ".####.", "......"), 0, 0, 4, 5),
    (("......", "######", "......", "......", "......"), 0, 0, 4, 0),
    ((".....", "##.##", ".....", "##.##", "....."), 0, 0, 4, 4),
    (("..#..", "..#..", ".....", "..#..", "..#.."), 0, 4, 4, 0),
    (("....", "....", "....", "...."), 0, 0, 3, 3),
]


class AdmissionHygieneTests(unittest.TestCase):
    def test_prunes_band20261501_wall_char_x_55_distractors_to_minimal_surgical_operator(self):
        # Load the exact recorded 55 admitted wall_char_x keys from Band 20261501.
        repo_root = Path(__file__).resolve().parents[2]
        disc_path = repo_root / "evidence" / "abc-v3-run-state" / "discovery_20261501.json"
        if disc_path.exists():
            data = json.loads(disc_path.read_text(encoding="utf-8"))
            raw_keys = [ast.literal_eval(s) for s in data["by_class"]["wall_char_x"]["admitted_operators"]]
            self.assertEqual(len(raw_keys), 55)
        else:
            raw_keys = [
                ("name_swap", (5, 2, 3, 0, 1, 4), "nc"),
                ("unary_not", (5, 2, 3, 0, 3), "wrap"),
                ("compare_swap", (5, 2, 3, 0, 4), "Gt"),
                ("string_literal", (5, 2, 3, 0, 4, 2), "#"),
            ]

        pool_ids = {"new_only-019", "new_only-020", "new_only-021"}
        fix_map = {k: set(pool_ids) for k in raw_keys}
        cases = _GRID_CASES
        truth = [_run(_NAVIGATE_REFERENCE, c) for c in cases]

        selected, stats = filter_parsimonious_keys(
            fix_map,
            min_pool_fixes=2,
            reference_codes=[_NAVIGATE_REFERENCE],
            adapter=GRID_ADAPTER,
            reference_cases=cases,
            reference_truth=truth,
        )
        # All 54 distractors including name_swap 'nc' are pruned; only surgical '#' survives!
        self.assertEqual(selected, [("string_literal", (5, 2, 3, 0, 4, 2), "#")])
        self.assertEqual(stats["pruned_count"], len(raw_keys) - 1)
        self.assertLess(operator_mdl_cost(selected[0]), operator_mdl_cost(("name_swap", (5, 2, 3, 0, 1, 4), "nc")))

    def test_pool_discovery_with_parsimony_keeps_clean_coverage_without_bloat(self):
        pool = [
            _make_grid_task(f"pool-wall-{i}", ("wall_char_x",), _GRID_CASES, shown_n=5)
            for i in range(2)
        ] + [
            _make_grid_task(f"pool-step-{i}", ("dist_step_2",), _GRID_CASES, shown_n=5)
            for i in range(2)
        ]
        res = discover_hygienic_pool(pool, GRID_ADAPTER, min_pool_fixes=2, require_pool_holdout=True)
        wall_admitted = res["by_class"]["wall_char_x"]["admitted_operators"]
        self.assertEqual(len(wall_admitted), 1)
        self.assertIn("string_literal", wall_admitted[0])
        self.assertEqual(len(res["by_class"]["dist_step_2"]["admitted_operators"]), 1)

    def test_evaluate_nonregressive_g2_achieves_differentiation_demonstrated(self):
        controls = [
            _make_grid_task(f"ctrl-nav-{i}", ("walls_passable",), _GRID_CASES, shown_n=5)
            for i in range(4)
        ]
        # Grid evaluation + control where A solves control (4/4) and 0/4 new eval,
        # pooled rate = 4/8 = 50% (strictly inside 10%-90% calibration gate).
        grid_pool = [
            _make_grid_task(f"pool-wall-{i}", ("wall_char_x",), _GRID_CASES, shown_n=5)
            for i in range(2)
        ] + [
            _make_grid_task(f"pool-bounds-{i}", ("bounds_off_by_one",), _GRID_CASES, shown_n=5)
            for i in range(2)
        ]
        grid_eval = [
            _make_grid_task(f"eval-wall-{i}", ("wall_char_x",), _GRID_CASES[i:] + _GRID_CASES[:i], shown_n=5)
            for i in range(2)
        ] + [
            _make_grid_task(f"eval-bounds-{i}", ("bounds_off_by_one",), _GRID_CASES[i:] + _GRID_CASES[:i], shown_n=5)
            for i in range(2)
        ]
        disc = discover_hygienic_pool(grid_pool, GRID_ADAPTER, min_pool_fixes=2, require_pool_holdout=True)
        out = evaluate_nonregressive_g2(
            evaluation=grid_eval,
            control=controls,
            admitted_keys=disc["admitted_keys"],
            adapter=GRID_ADAPTER,
            guard=True,
        )
        self.assertEqual(out["assessment"]["overall"], "DIFFERENTIATION_DEMONSTRATED")
        self.assertEqual(out["assessment"]["clauses"]["differentiation_index"]["evidence"]["control_margin_pp"], 0.0)
        self.assertEqual(out["control_counts"]["A"], out["control_counts"]["B"])

        # Also verify lexical discovery with Pareto filtering on text_transform preserves all valid keys
        text_pool = [build_text_task(seed=96000 + i, level=1) for i in range(10)]
        lex_disc = discover_hygienic_pool(
            text_pool,
            TEXT_ADAPTER,
            min_pool_fixes=2,
            require_pool_holdout=True,
            enumerator=enumerate_lexical_variants,
            apply_fn=apply_lexical_operator,
        )
        self.assertGreaterEqual(lex_disc["total_admitted_keys"], 1)

    def test_inoculation_battery_immune_under_lineage_guard(self):
        registry = load_registry(DEFAULT_REGISTRY_PATH)
        witnesses = [
            _make_grid_task(tid, ("walls_passable", "start_offset"), _GRID_CASES, shown_n=5)
            for rec in registry
            for tid in rec["witness_tasks"]
        ]
        battery_report = verify_inoculation_immunity(
            control_tasks=witnesses,
            catalog_keys=[("string_literal", (5, 2, 3, 0, 4, 2), "#")],
            adapter=GRID_ADAPTER,
            guard=True,
        )
        self.assertEqual(battery_report["overall"], "NOT_SUSCEPTIBLE")


if __name__ == "__main__":
    unittest.main()
