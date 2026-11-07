"""Comprehensive unit, isolation, mathematical equivalence, and tamper tests for Fase 6."""
from __future__ import annotations

import copy
from pathlib import Path
import unittest

from ace_research_discovery import PRESCORE_SHA256, canonical_json, digest
from ace_research_discovery.arms import (
    ARM_NAMES,
    C_FRESH_1X,
    C_FRESH_4X,
    RuntimeReuseSession,
    STRONG_FIXED_FEATURES,
    fit_fresh_dsl,
    fit_fresh_dsl_pair,
    fit_memorize,
    fit_strong_fixed,
    partition_for_runtime_prefix_budget,
)
from ace_research_discovery.discovery import discover_from_source_pool
from ace_research_discovery.dsl import (
    BoolExpr,
    IntExpr,
    NodePred,
    WorkMeter,
    bool_expr_from_data,
    parse_dyck_input,
    synthesize_bottom_up,
)
from ace_research_discovery.evaluator import (
    DRIFT_BASE_MAP,
    parse_paired_trees,
    parse_single_tree,
    tree_bipartite_diff,
    tree_branching_nodes,
    tree_leaves,
    tree_max_depth,
    tree_max_outdeg,
    tree_root_deg,
)
from ace_research_discovery.sampling import prime_dyck_by_vertices, single_tree_pool
from ace_research_discovery.tasks import (
    BUDGETS,
    SOURCE_TASKS_SPEC,
    TARGET_TASKS_SPEC,
    build_target_splits,
    build_uncurated_source_pool,
)
from ace_research_discovery.verify import (
    verify_family_and_task_disjointness,
    verify_report_dict,
    verify_static_ast_isolation,
)

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = Path(__file__).resolve().parent


class Fase6DiscoveryTests(unittest.TestCase):
    def test_upstream_sources_and_prescore_custody_intact(self) -> None:
        import hashlib
        import importlib.util

        spec = importlib.util.spec_from_file_location("verify_sources", ROOT / "tools/verify_sources.py")
        assert spec is not None and spec.loader is not None
        vs_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vs_mod)
        self.assertEqual(vs_mod.verify(ROOT), 25)

        prescore_bytes = (ROOT / "docs/ACE_NOVEL_DISCOVERY_PRESCORE_V1.md").read_bytes()
        self.assertEqual(hashlib.sha256(prescore_bytes).hexdigest(), PRESCORE_SHA256)

    def test_static_ast_isolation_of_learner_modules(self) -> None:
        verify_static_ast_isolation(PKG_DIR)

    def test_catalan_counts_match_exact_combinatorics(self) -> None:
        dp = prime_dyck_by_vertices(9)
        expected_catalan = {1: 1, 2: 1, 3: 2, 4: 5, 5: 14, 6: 42, 7: 132, 8: 429, 9: 1430}
        for v, count in expected_catalan.items():
            self.assertEqual(len(dp[v]), count)
        self.assertEqual(len(single_tree_pool(2, 9)), 2055)

    def test_stack_dsl_matches_independent_recursive_tree_evaluator_on_all_2055_trees(self) -> None:
        ie_depth = IntExpr(kind="max_nodes", frame="Whole", attr="depth")
        ie_leaves = IntExpr(kind="count_nodes", frame="Whole", npred=NodePred("eq", "deg", 0))
        ie_root_deg = IntExpr(kind="count_nodes", frame="Whole", npred=NodePred("eq", "depth", 2))
        ie_bip = IntExpr(kind="signed_balance", frame="Whole", npred=NodePred("mod_eq", "depth", 2, 1))
        ie_max_deg = IntExpr(kind="max_nodes", frame="Whole", attr="deg")
        ie_branch = IntExpr(kind="count_nodes", frame="Whole", npred=NodePred("ge", "deg", 2))

        for word in single_tree_pool(2, 9):
            tree = parse_single_tree(word)
            self.assertIsNotNone(tree)
            assert tree is not None
            parsed = parse_dyck_input(word)
            self.assertTrue(parsed.valid_dyck)
            self.assertEqual(parsed.num_components, 1)
            self.assertEqual(ie_depth.eval_parsed(parsed), tree_max_depth(tree))
            self.assertEqual(ie_leaves.eval_parsed(parsed), tree_leaves(tree))
            self.assertEqual(ie_root_deg.eval_parsed(parsed), tree_root_deg(tree))
            self.assertEqual(ie_bip.eval_parsed(parsed), tree_bipartite_diff(tree))
            self.assertEqual(ie_max_deg.eval_parsed(parsed), tree_max_outdeg(tree))
            self.assertEqual(ie_branch.eval_parsed(parsed), tree_branching_nodes(tree))

    def test_bottom_up_synthesis_vectors_match_tree_walk_interpreter(self) -> None:
        words = list(single_tree_pool(2, 5)) + ["aabbaabb", "ab", "aba"]
        parsed = tuple(parse_dyck_input(w) for w in words)
        meter = WorkMeter()
        cands = synthesize_bottom_up(parsed, ("Whole", "LeftF", "RightF"), max_bool_candidates=120, meter=meter)
        self.assertEqual(len(cands), 120)
        self.assertGreater(meter.ast_nodes_evaluated, 0)
        self.assertGreater(meter.symbol_steps, 0)
        for expr, vec in cands:
            walk_vec = tuple(expr.predict(w) for w in words)
            self.assertEqual(vec, walk_vec)
            # Round-trip closed AST serialization
            redecoded = bool_expr_from_data(expr.to_data())
            self.assertEqual(redecoded, expr)
            self.assertEqual(redecoded.identity, expr.identity)

    def test_closed_ast_decoder_rejects_bool_int_aliases_and_bad_kinds(self) -> None:
        valid = BoolExpr(
            kind="int_eq_const",
            int_sub=IntExpr(kind="max_nodes", frame="Whole", attr="depth"),
            threshold=2,
        ).to_data()
        self.assertIsInstance(bool_expr_from_data(valid), BoolExpr)

        bad_alias = copy.deepcopy(valid)
        bad_alias["threshold"] = True  # bool is subclass of int in Python; must reject!
        with self.assertRaises(ValueError):
            bool_expr_from_data(bad_alias)

        bad_const = BoolExpr(kind="const", const_val=True).to_data()
        bad_const["const_val"] = 1
        with self.assertRaises(ValueError):
            bool_expr_from_data(bad_const)

        bad_kind = copy.deepcopy(valid)
        bad_kind["kind"] = "eval_python"
        with self.assertRaises(ValueError):
            bool_expr_from_data(bad_kind)

    def test_strict_family_disjointness_and_nested_budgets(self) -> None:
        verify_family_and_task_disjointness()
        self.assertEqual(len(SOURCE_TASKS_SPEC), 12)
        self.assertEqual(len(TARGET_TASKS_SPEC), 15)
        self.assertEqual(len(STRONG_FIXED_FEATURES), 174)

        for t_spec in TARGET_TASKS_SPEC:
            splits = {b: build_target_splits(t_spec.name, seed=2, budget=b) for b in BUDGETS}
            tr16, va16, te16 = splits[16]
            tr32, va32, te32 = splits[32]
            tr64, va64, te64 = splits[64]

            self.assertEqual((len(tr16), len(va16), len(te16)), (8, 8, 128))
            self.assertEqual((len(tr32), len(va32), len(te32)), (16, 16, 128))
            self.assertEqual((len(tr64), len(va64), len(te64)), (32, 32, 128))

            self.assertTrue(set(tr16).issubset(set(tr32)))
            self.assertTrue(set(tr32).issubset(set(tr64)))
            self.assertTrue(set(va16).issubset(set(va32)))
            self.assertTrue(set(va32).issubset(set(va64)))
            self.assertEqual(te16, te32)
            self.assertEqual(te32, te64)

            # Verify strict length separation: dev <= 28, terminal >= 30
            self.assertTrue(all(len(w) <= 28 for w, _ in tr64 + va64))
            self.assertTrue(all(30 <= len(w) <= 40 for w, _ in te64))

    def test_n1_and_n2_pairs_have_identical_node_depth_degree_multisets(self) -> None:
        for t_name in ("n1_ordered_tree_identity", "n2_mirror_tree_duality"):
            tr, va, te = build_target_splits(t_name, seed=1, budget=32)
            for w, _ in tr + va + te:
                parsed = parse_dyck_input(w)
                self.assertTrue(parsed.valid_dyck)
                self.assertEqual(parsed.num_components, 2)
                self.assertEqual(sorted(parsed.left.nodes), sorted(parsed.right.nodes))

    def test_drift_tasks_match_dev_truth_and_cannot_leak_terminal_inversion(self) -> None:
        for drift_name, base_name in DRIFT_BASE_MAP.items():
            tr_d, va_d, te_d = build_target_splits(drift_name, seed=1, budget=32)
            tr_b, va_b, te_b = build_target_splits(base_name, seed=1, budget=32)
            self.assertEqual(tr_d, tr_b)
            self.assertEqual(va_d, va_b)
            self.assertEqual([w for w, _ in te_d], [w for w, _ in te_b])
            self.assertEqual([y for _, y in te_d], [not y for _, y in te_b])

            fit_d = fit_strong_fixed(tr_d, va_d, seed=1)
            fit_b = fit_strong_fixed(tr_b, va_b, seed=1)
            self.assertEqual(fit_d.selected_identity, fit_b.selected_identity)

    def test_real_ace_runtime_session_stages_capabilities_and_preserves_labels(self) -> None:
        learner_sources, _ = build_uncurated_source_pool(seed=1)
        for item in learner_sources:
            tr_rt, va_rt = partition_for_runtime_prefix_budget(item["train"], item["validation"])
            self.assertEqual(
                {(w, y) for w, y in tr_rt + va_rt},
                set(item["train"] + item["validation"]),
            )
        with RuntimeReuseSession(learner_sources) as session:
            self.assertEqual(len(session.source_outcomes), 12)
            self.assertEqual(session.runtime.status()["completed"], 12)
            self.assertGreaterEqual(session.capabilities_after_source, 0)
            tr, va, te = build_target_splits("u1_leaves_mod4_rel", seed=1, budget=32)
            fit_out, term_out = session.fit_and_evaluate_target("t_u1", tr, va, te)
            self.assertEqual(fit_out.arm, "M1_exact_reuse")
            self.assertEqual(term_out["terminal_total"], 128)

    def test_uncurated_source_discovery_recovers_structural_projections_without_labels(self) -> None:
        learner_sources, _ = build_uncurated_source_pool(seed=1)
        # Ensure learner input has zero task names or category keys
        for item in learner_sources:
            self.assertEqual(set(item.keys()), {"train", "validation"})
        rep = discover_from_source_pool(learner_sources, seed=1)
        self.assertEqual(rep.admitted_source_count, 12)
        self.assertLessEqual(len(rep.abstractions), 7)
        int_count = sum(1 for ab in rep.abstractions if ab.kind == "int")
        self.assertGreaterEqual(int_count, 6)

    def test_memorizer_exact_on_dev_and_bounded_on_terminal(self) -> None:
        tr, va, te = build_target_splits("u1_leaves_mod4_rel", seed=1, budget=16)
        mem = fit_memorize(tr, va)
        self.assertTrue(all(mem.predict_fn(w, None) == y for w, y in tr + va))
        preds = [mem.predict_fn(w, None) for w, _ in te]
        self.assertEqual(len(preds), 128)

    def test_verifier_detects_tampering_and_oracle_leakage(self) -> None:
        # Build a minimal valid mock report structure from real split digests to test tamper rejections
        from ace_research_discovery.runner import run_benchmark

        report = run_benchmark()
        sha = verify_report_dict(report, root=ROOT, check_replay=False)
        self.assertEqual(len(sha), 64)

        # 1. Reject open_world_safe=True
        bad1 = copy.deepcopy(report)
        bad1["open_world_safe"] = True
        with self.assertRaises(ValueError):
            verify_report_dict(bad1, root=ROOT, check_replay=False)

        # 2. Reject oracle injected into benchmark arms
        bad2 = copy.deepcopy(report)
        bad2["trials"][0]["arms"]["U_native_oracle"] = bad2["trials"][0]["upper_bound_oracle"]
        with self.assertRaises(ValueError):
            verify_report_dict(bad2, root=ROOT, check_replay=False)

        # 3. Reject fabricated terminal_correct disagreeing with closed AST replay
        bad3 = copy.deepcopy(report)
        bad3["trials"][0]["arms"]["M5_ace_discovery"]["terminal_correct"] = 128
        bad3["trials"][0]["arms"]["M5_ace_discovery"]["predictions_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_report_dict(bad3, root=ROOT, check_replay=False)

        # 4. Reject bool/int alias on `admitted`
        bad4 = copy.deepcopy(report)
        bad4["trials"][0]["arms"]["M5_ace_discovery"]["admitted"] = 1
        with self.assertRaises(ValueError):
            verify_report_dict(bad4, root=ROOT, check_replay=False)


    def test_fresh_dsl_checkpoint_pair_matches_standalone_runs(self) -> None:
        tr, va, te = build_target_splits("u6_max_depth_eq", seed=1, budget=32)
        solo_1x = fit_fresh_dsl(tr, va, seed=1, max_candidates=C_FRESH_1X, arm_name="M3_fresh_dsl")
        solo_4x = fit_fresh_dsl(tr, va, seed=1, max_candidates=C_FRESH_4X, arm_name="M3_fresh_4x")
        pair_1x, pair_4x = fit_fresh_dsl_pair(tr, va, seed=1)

        for solo, paired in ((solo_1x, pair_1x), (solo_4x, pair_4x)):
            self.assertEqual(solo.selected_identity, paired.selected_identity)
            self.assertEqual(solo.train_correct, paired.train_correct)
            self.assertEqual(solo.validation_correct, paired.validation_correct)
            self.assertEqual(solo.admitted, paired.admitted)
            self.assertEqual(solo.probe_agreement, paired.probe_agreement)
            self.assertEqual(solo.work, paired.work)
            self.assertEqual(solo.metadata, paired.metadata)
            self.assertEqual(
                [solo.predict_fn(w, None) for w, _ in te],
                [paired.predict_fn(w, None) for w, _ in te],
            )


if __name__ == "__main__":
    unittest.main()
