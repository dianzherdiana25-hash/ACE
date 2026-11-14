"""Tests for E4 Cross-Family AST & Operator Macro Abstraction Engine."""
from __future__ import annotations

import unittest

from ace_operational.abstraction_engine import (
    CrossFamilyAbstractionEngine,
    macro_prioritized_solve,
)
from ace_operational.family3_prototype import TEXT_ADAPTER, build_text_task
from ace_operational.lexical_ops import (
    SHIPPING_ADAPTER,
    build_shipping_task,
    discover_lexical_for_task,
    enumerate_lexical_variants,
)
from ace_operational.pricing_adapter import PRICING_ADAPTER, build_pricing_task
from ace_operational.reasoning_lab import Budget


class _QuotaAdapter:
    """Unseen fourth-shape structural domain to prove cross-family zero-shot macro transfer."""

    family_id = "quota_policy"

    def make_budget(self, task):
        return Budget(
            1_000_000,
            entrypoint="quota_ok",
            shown_cases=[tuple(c) for c in task["shown_cases"]],
            shown_expected=list(task["shown_truth"]),
        )

    def passes(self, code, cases, truth) -> int:
        def run_one(c):
            ns = {}
            try:
                exec(compile(code, "<quota>", "exec"), ns)
                return ns["quota_ok"](*c)
            except Exception:
                return None

        return sum(1 for c, w in zip(cases, truth) if run_one(tuple(c)) == w)

    def baseline_variants(self, code) -> list:
        return []

    def baseline_catalog_id(self) -> str:
        return "quota-empty-v0"

    def extra_string_candidates(self, code) -> set:
        return set()


def _build_unseen_quota_task(limit: int = 100) -> dict:
    """Has completely different variable names, line offsets, and parameter names from pricing/shipping."""
    ref = (
        "def quota_ok(usage, reserve, premium):\n"
        "    score = usage + reserve\n"
        "    badge = 1 if premium else 0\n"
        "    bonus = badge * 10\n"
        "    effective = score + bonus\n"
        f"    if effective >= {limit}:\n"
        "        return True\n"
        "    return False\n"
    )
    buggy = ref.replace(f"if effective >= {limit}:", f"if effective > {limit}:")
    cases = [(limit - 11, 0, True), (limit - 1, 1, False), (limit, 0, False), (limit + 5, 0, False), (50, 50, False)]
    truth = []
    for c in cases:
        ns = {}
        exec(compile(ref, "<qref>", "exec"), ns)
        truth.append(ns["quota_ok"](*c))
    return {
        "task_id": f"unseen-quota-{limit}",
        "family": "quota_policy",
        "buggy_code": buggy,
        "reference_code": ref,
        "shown_cases": [list(c) for c in cases[:4]],
        "shown_truth": truth[:4],
        "holdout_cases": [list(c) for c in cases[4:]],
        "holdout_truth": truth[4:],
        "defects": ["boundary_off_by_one"],
    }


class AbstractionEngineTests(unittest.TestCase):
    def test_cross_family_wake_sleep_compression_and_speedup(self):
        engine = CrossFamilyAbstractionEngine()

        # 1. Wake phase: learn from pricing L2 (threshold_boundary), shipping L2 (free_boundary), and text_transform L1 (condition + off_by_one)
        for seed in (10, 12, 14, 16, 18):
            pt = build_pricing_task(seed=seed, level=2)
            if pt["defects"] == ["threshold_boundary"]:
                ks = discover_lexical_for_task(pt, PRICING_ADAPTER)
                if ks:
                    engine.wake_record(task_id=pt["task_id"], family="pricing", buggy_code=pt["buggy_code"], repair_key=ks[0])

        ship_seeds = [100 + i for i in range(6)]
        for s in ship_seeds:
            st = build_shipping_task(seed=s, level=2)
            if st["defects"] == ["free_boundary"]:
                ks = discover_lexical_for_task(st, SHIPPING_ADAPTER)
                if ks:
                    engine.wake_record(task_id=st["task_id"], family="shipping", buggy_code=st["buggy_code"], repair_key=ks[0])

        for s in range(91000, 91040):
            tt = build_text_task(seed=s, level=1)
            if tt["defects"] in (["truncate_condition_boundary"], ["truncate_off_by_one"], ["split_whitespace_semantics"]):
                ks = discover_lexical_for_task(tt, TEXT_ADAPTER)
                if ks:
                    engine.wake_record(task_id=tt["task_id"], family="text_transform", buggy_code=tt["buggy_code"], repair_key=ks[0])

        summary = engine.sleep_compress(min_support=2)
        self.assertGreater(summary["traces_processed"], 4)
        self.assertGreaterEqual(summary["macros_promoted"], 2)
        self.assertGreaterEqual(summary["cross_family_macros"], 1)
        self.assertLess(summary["compressed_dl_bits"], summary["flat_dl_bits"])
        self.assertGreater(summary["compression_ratio"], 1.2)
        self.assertGreater(summary["dl_saved_bits"], 0.0)

        # 2. Empirical speedup vs unguided flat enumeration on unseen family + held-out text tasks
        unseen = _build_unseen_quota_task(limit=120)
        unseen_adapter = _QuotaAdapter()

        flat_engine = CrossFamilyAbstractionEngine()  # empty library = flat search only
        res_macro = macro_prioritized_solve(unseen, unseen_adapter, engine)
        res_flat = macro_prioritized_solve(unseen, unseen_adapter, flat_engine)

        self.assertTrue(res_macro["holdout_solved"])
        self.assertTrue(res_flat["holdout_solved"])
        self.assertTrue(res_macro["winning_source"].startswith("macro:"))
        self.assertGreaterEqual(res_macro["macro_hits"], 1)
        # Crucial efficiency proof: macro-prioritized search finds the boundary fix cleanly earlier
        self.assertLess(res_macro["score_calls"], res_flat["score_calls"])

        # 3. Also test cross-literal slice off-by-one macro on unseen limit=20 text_transform task
        target_tt = None
        for s in range(92500, 92600):
            cand = build_text_task(seed=s, level=1)
            if cand["defects"] == ["truncate_off_by_one"] and "len(slug) > 20" in cand["buggy_code"]:
                target_tt = cand
                break
        if target_tt is not None:
            r_m = macro_prioritized_solve(target_tt, TEXT_ADAPTER, engine)
            r_f = macro_prioritized_solve(target_tt, TEXT_ADAPTER, flat_engine)
            self.assertTrue(r_m["holdout_solved"])
            self.assertLess(r_m["score_calls"], r_f["score_calls"])

    def test_empty_engine_and_syntax_error_fail_closed(self):
        eng = CrossFamilyAbstractionEngine()
        empty = eng.sleep_compress(min_support=2)
        self.assertEqual(empty["macros_promoted"], 0)
        self.assertEqual(empty["compression_ratio"], 1.0)
        eng.wake_record(task_id="bad", family="text_transform", buggy_code="def broken(:", repair_key=("int_delta", (0,), 1))
        self.assertIsNone(eng.traces[0]["template"])


if __name__ == "__main__":
    unittest.main()
