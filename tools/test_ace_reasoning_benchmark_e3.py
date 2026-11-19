"""Tes tepi luring untuk tools/ace_reasoning_benchmark.py (E3 #2, TESTS ONLY)."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import ace_reasoning_benchmark as arb  # noqa: E402

BudgetExhausted = arb.BudgetExhausted
Problem = arb.Problem


class TestAceReasoningBenchmarkE3(unittest.TestCase):
    """Uji unit tepi dan kontrak schema untuk ace_reasoning_benchmark."""

    def test_01_op_builds_nested_operator_tree(self):
        tree = arb.op("add", {"var": "x"}, arb.op("mul", {"const": 2}, {"var": "y"}))
        self.assertEqual(
            tree,
            {
                "op": "add",
                "args": [
                    {"var": "x"},
                    {"op": "mul", "args": [{"const": 2}, {"var": "y"}]},
                ],
            },
        )

    def test_02_sample_splits_disjoint_sizes_and_radii(self):
        train, val, terminal = arb.sample_splits(20261110)
        self.assertEqual(len(train), 12)
        self.assertEqual(len(val), 12)
        self.assertEqual(len(terminal), 24)
        all_pts = train + val + terminal
        self.assertEqual(len(set(all_pts)), 48)
        for x, y in train:
            self.assertLessEqual(max(abs(x), abs(y)), 3)
        for x, y in val:
            self.assertLessEqual(max(abs(x), abs(y)), 6)
        for x, y in terminal:
            self.assertLessEqual(max(abs(x), abs(y)), 12)
        self.assertEqual(arb.sample_splits(20261110), [train, val, terminal])
        self.assertNotEqual(arb.sample_splits(20261110), arb.sample_splits(20261111))

    def test_03_sample_splits_extreme_seeds(self):
        for seed in (0, -1, 2**31 - 1):
            splits = arb.sample_splits(seed)
            self.assertEqual([len(s) for s in splits], [12, 12, 24])
            merged = splits[0] + splits[1] + splits[2]
            self.assertEqual(len(set(merged)), 48)

    def test_04_make_problem_schema_id_and_labels(self):
        rule = arb.RULES[0]
        task, terminal = arb.make_problem(rule, 42, "_suf")
        self.assertEqual(task["schema"], arb.SCHEMA)
        self.assertEqual(task["id"], "add_42_suf")
        self.assertEqual(len(task["train"]), 12)
        self.assertEqual(len(task["validation"]), 12)
        self.assertEqual(len(terminal), 24)
        for row in task["train"] + task["validation"] + terminal:
            self.assertEqual(row["output"], row["inputs"]["x"] + row["inputs"]["y"])

    def test_05_make_problem_preserves_bool_and_zero_suffix_default(self):
        custom = ("eq_zero", lambda x, y: (x + y) == 0, {"const": False})
        task, terminal = arb.make_problem(custom, 7)
        self.assertEqual(task["id"], "eq_zero_7")
        for row in task["train"] + terminal:
            self.assertIsInstance(row["output"], bool)
            self.assertEqual(row["output"], (row["inputs"]["x"] + row["inputs"]["y"]) == 0)

    def test_06_measured_returns_value_and_metrics(self):
        val, profile = arb.measured(lambda: {"ok": False, "n": 0})
        self.assertEqual(val, {"ok": False, "n": 0})
        self.assertGreaterEqual(profile["cpu_seconds"], 0.0)
        self.assertGreaterEqual(profile["wall_seconds"], 0.0)
        self.assertGreater(profile["process_peak_rss_kib"], 0)

    def test_07_measured_propagates_inner_exception(self):
        def boom():
            raise ValueError("probe failure")

        with self.assertRaisesRegex(ValueError, "probe failure"):
            arb.measured(boom)

    def test_08_fresh_baseline_synthesizes_add_rule(self):
        task, terminal = arb.make_problem(arb.RULES[0], arb.SEEDS[0])
        res = arb.fresh_baseline(Problem.from_data(task))
        self.assertEqual(res["status"], "STAGED_EMPIRICAL")
        self.assertIsNotNone(res["program"])
        self.assertGreater(res["search_candidates"], 0)
        self.assertGreater(res["primitive_operations"], 0)
        scored = arb.terminal_score(res["program"], terminal)
        self.assertEqual(scored["correct"], len(terminal))

    def test_09_fresh_baseline_handles_budget_exhausted(self):
        task, _ = arb.make_problem(arb.RULES[0], arb.SEEDS[0])
        with mock.patch.object(arb.ComponentSynthesizer, "synthesize", side_effect=BudgetExhausted("cap")):
            res = arb.fresh_baseline(Problem.from_data(task))
        self.assertEqual(res["status"], "ABSTAIN")
        self.assertIsNone(res["program"])
        self.assertIsNone(res["search_candidates"])
        self.assertGreaterEqual(res["primitive_operations"], 0)

    def test_10_fresh_baseline_abstains_when_validation_contradicts_train(self):
        task, _ = arb.make_problem(arb.RULES[0], arb.SEEDS[0])
        bad_val = [dict(r, output=r["output"] + 999) for r in task["validation"]]
        bad_task = dict(task, validation=bad_val)
        res = arb.fresh_baseline(Problem.from_data(bad_task))
        self.assertEqual(res["status"], "ABSTAIN")
        self.assertIsNone(res["program"])

    def test_11_terminal_score_none_program_abstains_every_row(self):
        rows = [{"inputs": {"x": 1, "y": 2}, "output": 3}]
        self.assertEqual(
            arb.terminal_score(None, rows),
            {
                "correct": 0,
                "total": 1,
                "abstained": 1,
                "predictions": [],
                "primitive_operations": 0,
            },
        )
        empty = arb.terminal_score(None, [])
        self.assertEqual(empty["total"], 0)
        self.assertEqual(empty["abstained"], 0)

    def test_12_terminal_score_strict_bool_vs_int_distinction(self):
        # Program x + y predicts integers (0, 1); bool ground truths True/False must miss.
        task, _ = arb.make_problem(arb.RULES[0], arb.SEEDS[0])
        prog = arb.fresh_baseline(Problem.from_data(task))["program"]
        mixed_rows = [
            {"inputs": {"x": 0, "y": 1}, "output": True},   # 1 != True (strict type)
            {"inputs": {"x": 0, "y": 0}, "output": False},  # 0 != False (strict type)
            {"inputs": {"x": -2, "y": 5}, "output": 3},     # 3 == 3 (int)
        ]
        scored = arb.terminal_score(prog, mixed_rows)
        self.assertEqual(scored["predictions"], [1, 0, 3])
        self.assertEqual(scored["correct"], 1)
        self.assertEqual(scored["total"], 3)
        self.assertEqual(scored["abstained"], 0)

    def test_13_terminal_score_empty_rows_with_valid_program(self):
        task, _ = arb.make_problem(arb.RULES[0], arb.SEEDS[0])
        prog = arb.fresh_baseline(Problem.from_data(task))["program"]
        scored = arb.terminal_score(prog, [])
        self.assertEqual(scored["correct"], 0)
        self.assertEqual(scored["total"], 0)
        self.assertEqual(scored["abstained"], 0)
        self.assertEqual(scored["predictions"], [])

    def test_14_run_single_cell_contract_and_retention(self):
        with mock.patch.object(arb, "SEEDS", (20261110,)), mock.patch.object(arb, "RULES", arb.RULES[:1]):
            report, profile = arb.run()
        self.assertEqual(report["schema"], "ace.reasoning.public.v1")
        self.assertEqual(len(report["cells"]), 1)
        self.assertEqual(len(report["retention"]), 1)
        self.assertTrue(report["summary"]["H3_within_rule_retention_pass"])
        self.assertEqual(report["summary"]["external_model_calls"], 0)
        self.assertEqual(report["summary"]["release_gate"], "BLOCK_RELEASE")
        self.assertFalse(report["summary"]["H1_engineering_pass"])
        self.assertEqual(len(profile["per_task"]), 1)
        self.assertGreater(profile["peak_rss_kib"], 0)

    def test_15_run_hidden_shift_captures_false_admission(self):
        with mock.patch.object(arb, "SEEDS", (20261110,)), mock.patch.object(arb, "RULES", arb.RULES[:1]):
            report, _ = arb.run()
        hs = report["hidden_shift"]
        self.assertTrue(hs["false_admission"])
        self.assertEqual(hs["terminal"]["correct"], 0)
        self.assertEqual(hs["terminal"]["total"], 24)

    def test_16_main_writes_output_profile_and_requires_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "report.json"
            prof_path = Path(tmp) / "profile.json"
            fake_report = {"summary": {"A_correct": 1}}
            fake_profile = {"pid": 123}
            buf = io.StringIO()
            with (
                mock.patch.object(arb, "run", return_value=(fake_report, fake_profile)),
                mock.patch.object(sys, "argv", ["arb", "--output", str(out_path), "--profile", str(prof_path)]),
                redirect_stdout(buf),
            ):
                arb.main()
            printed = json.loads(buf.getvalue())
            expected_sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
            self.assertEqual(printed["sha256"], expected_sha)
            self.assertEqual(printed["summary"], {"A_correct": 1})
            self.assertEqual(json.loads(prof_path.read_text()), fake_profile)
            self.assertTrue(out_path.read_text().endswith("\n"))

        with mock.patch.object(sys, "argv", ["arb"]), mock.patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                arb.main()
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
