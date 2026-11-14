"""Tests for generic AST lexical/method/wrapper/arg discovery and Family 3/4 transfer."""
from __future__ import annotations

import ast
import unittest

from ace_operational.catalog_gap import STATUS_GAP, analyze_catalog_gaps
from ace_operational.curriculum_generator import LEVEL_DISCRIMINATING, generate_practice_set
from ace_operational.family3_prototype import (
    DEFECT_NAMES,
    TEXT_ADAPTER,
    _run_one as _run_text_one,
    build_text_task,
    render_reference,
    text_rivals,
)
from ace_operational.lexical_ops import (
    SHIPPING_ADAPTER,
    apply_lexical_chain,
    apply_lexical_operator,
    build_shipping_task,
    discover_lexical_chain_for_task,
    discover_lexical_for_task,
    discover_lexical_pairs_for_task,
    enumerate_lexical_variants,
    run_lexical_discovery,
    shipping_rivals,
    solve_lexical_task,
)


class TestLexicalOpsRoundtrip(unittest.TestCase):
    def test_enumerate_and_direct_apply_roundtrip_on_text_and_shipping(self):
        samples = [
            render_reference("lower", "-", 12),
            'def transform(text):\n    words = text.split(" ")\n    words = [w.upper() for w in words]\n    slug = "_".join(reversed(words))\n    if len(slug) >= 12:\n        slug = slug[:8] + "..."\n    return slug\n',
            build_shipping_task(seed=401, level=1)["buggy_code"],
        ]
        for code in samples:
            variants = enumerate_lexical_variants(code, string_seeds={"-", "_", " ", ""})
            self.assertGreater(len(variants), 10)
            schemas = {k[0] for k, _ in variants}
            self.assertTrue({"attribute_swap", "compare_swap"} & schemas)
            for key, variant in variants:
                self.assertEqual(apply_lexical_operator(code, key), variant, f"mismatch on {key}")
                ast.parse(variant)

    def test_unparseable_and_single_statement_negative_controls(self):
        self.assertEqual(enumerate_lexical_variants("def broken(:\n  pass"), [])
        self.assertIsNone(apply_lexical_operator("def broken(:\n  pass", ("attribute_swap", (0,), "lower")))
        self.assertIsNone(apply_lexical_operator("x = 1", ("attribute_swap", (0,), "lower")))


class TestFamily3TextTransformDiscoveryAndTransfer(unittest.TestCase):
    def _collect_all_classes_tasks(self, seed_start: int, count: int, level: int) -> list[dict]:
        tasks = []
        by_class: dict[str, list[dict]] = {d: [] for d in DEFECT_NAMES}
        seed = seed_start
        while any(len(v) < count for v in by_class.values()) and seed < seed_start + 500:
            task = build_text_task(seed=seed, level=level)
            seed += 1
            cls = task["defects"][0]
            if level == 1 and len(by_class[cls]) < count:
                by_class[cls].append(task)
            elif level == 2:
                tasks.append(task)
                if len(tasks) >= count:
                    break
        if level == 1:
            return [t for cls in DEFECT_NAMES for t in by_class[cls]]
        return tasks

    def test_discovers_all_six_defect_classes_and_transfers_heldout(self):
        pool = self._collect_all_classes_tasks(92000, 10, level=1)
        eval_tasks = self._collect_all_classes_tasks(93000, 3, level=1)
        # Negative controls: already-clean reference programs disguised as control tasks.
        controls = [
            {
                **t,
                "task_id": f"ctrl-{t['task_id']}",
                "buggy_code": t["reference_code"],
            }
            for t in eval_tasks[:6]
        ]
        # Synthetic L2 pair pool & mixed eval.
        pair_pool = self._collect_all_classes_tasks(94000, 6, level=2)
        mixed_eval = self._collect_all_classes_tasks(95000, 6, level=2)

        report = run_lexical_discovery(
            pool=pool,
            evaluation=eval_tasks + mixed_eval,
            control=controls,
            pair_pool=pair_pool,
            chain_pool=pair_pool,
            min_pool_fixes=2,
            adapter=TEXT_ADAPTER,
            guard=True,
            require_pool_holdout=True,
        )

        # Every defect class must discover & admit operators and improve held-out solve rate.
        for cls in DEFECT_NAMES:
            rec = report["by_class"][cls]
            self.assertGreaterEqual(len(rec["admitted_operators"]), 1, f"no operator admitted for {cls}: {rec}")
            self.assertGreaterEqual(
                rec["eval_solved_extended"],
                max(rec["eval_tasks"] - 1, 1),
                f"low holdout solve rate for {cls}: {rec}",
            )

        self.assertGreaterEqual(report["mixed_evaluation"]["solved_extended"], 5)
        self.assertEqual(report["control"]["solved_extended"], report["control"]["total"])

    def test_lineage_guard_preserves_base_on_control(self):
        t = build_text_task(seed=91015, level=1)
        clean_ctrl = {**t, "task_id": "ctrl-guard", "buggy_code": t["reference_code"]}
        # Even if a distractor key changes `lower` -> `upper`, clean control stays solved.
        distractor_key = ("attribute_swap", (1, 1, 0, 0, 0, 0), "upper")
        guard_stats: dict[str, int] = {}
        out = solve_lexical_task(
            clean_ctrl,
            TEXT_ADAPTER,
            extra_keys=[distractor_key],
            guard=True,
            guard_stats=guard_stats,
        )
        self.assertEqual(
            TEXT_ADAPTER.passes(out, clean_ctrl["holdout_cases"], clean_ctrl["holdout_truth"]),
            len(clean_ctrl["holdout_cases"]),
        )

    def test_pair_and_chain_discovery_and_negative_control_rejection(self):
        task_l2 = build_text_task(seed=94101, level=2)
        self.assertEqual(discover_lexical_for_task(task_l2, TEXT_ADAPTER), [])
        pairs = discover_lexical_pairs_for_task(task_l2, TEXT_ADAPTER)
        chain = discover_lexical_chain_for_task(task_l2, TEXT_ADAPTER)
        self.assertTrue(len(pairs) >= 1 or chain is not None)
        if chain is not None:
            fixed = apply_lexical_chain(task_l2["buggy_code"], chain)
            self.assertIsNotNone(fixed)
            self.assertEqual(
                TEXT_ADAPTER.passes(fixed, task_l2["holdout_cases"], task_l2["holdout_truth"]),
                len(task_l2["holdout_cases"]),
            )

        # Negative control: unrepairable dummy code passes nothing.
        impossible = {
            **task_l2,
            "task_id": "impossible-ctrl",
            "buggy_code": "def transform(text):\n    return None\n",
        }
        self.assertEqual(discover_lexical_for_task(impossible, TEXT_ADAPTER), [])
        self.assertEqual(discover_lexical_pairs_for_task(impossible, TEXT_ADAPTER), [])


class TestShippingDiscoveryAndCurriculumIntegration(unittest.TestCase):
    def test_shipping_single_and_l2_discovery(self):
        pool = [build_shipping_task(seed=100 + i, level=1) for i in range(6)]
        eval_tasks = [build_shipping_task(seed=200 + i, level=1) for i in range(4)]
        controls = [{**t, "task_id": f"ctrl-{t['task_id']}", "buggy_code": t["reference_code"]} for t in eval_tasks]
        pair_pool = [build_shipping_task(seed=300 + i, level=2) for i in range(4)]

        report = run_lexical_discovery(
            pool=pool,
            evaluation=eval_tasks + pair_pool[:2],
            control=controls,
            pair_pool=pair_pool,
            min_pool_fixes=2,
            adapter=SHIPPING_ADAPTER,
            guard=True,
        )
        self.assertGreaterEqual(report["control"]["solved_extended"], len(controls))
        for cls, rec in report["by_class"].items():
            self.assertEqual(rec["eval_solved_extended"], rec["eval_tasks"], f"{cls} failed: {rec}")

    def test_text_transform_and_shipping_discriminating_curriculum(self):
        empty_report = {
            "by_class": {
                "case_mode_swap": {
                    "pool_tasks": 3,
                    "candidate_operators": 0,
                    "admitted_operators": [],
                    "admitted_chains": [],
                    "eval_tasks": 3,
                    "eval_solved_baseline": 0,
                    "eval_solved_extended": 0,
                }
            }
        }
        empty_catalog = {"classes": {}}
        gap = analyze_catalog_gaps(
            empty_report,
            empty_catalog,
            universe_classes=["case_mode_swap"],
        )
        self.assertEqual(gap["per_class"]["case_mode_swap"]["status"], STATUS_GAP)

        def build_for_class(cls: str, seed: int) -> dict | None:
            for offset in range(30):
                t = build_text_task(seed=seed + offset, level=1)
                if cls in t["defects"]:
                    return t
            return None

        practice = generate_practice_set(
            gap,
            task_source={
                "name": "text_transform",
                "build": build_for_class,
                "run": lambda code, case: _run_text_one(code, tuple(case)),
                "rivals": text_rivals,
            },
            tasks_per_gap=2,
            seed=20261114,
        )
        self.assertEqual(len(practice["tasks"]), 2)
        for item in practice["tasks"]:
            self.assertEqual(item["identifiability"]["level"], LEVEL_DISCRIMINATING)

        # Also check shipping_rivals yields clean rivals
        ship_t = build_shipping_task(seed=501, level=1)
        self.assertGreaterEqual(len(shipping_rivals(ship_t)), 1)


if __name__ == "__main__":
    unittest.main()
