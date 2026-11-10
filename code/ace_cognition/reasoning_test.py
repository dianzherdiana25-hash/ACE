from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ace_cognition.reasoning import (Meter, Problem, ReasoningMemory, SCHEMA,
                                    decode_program, predict, solve)


def problem(rule=lambda x, y: x + y):
    def rows(pairs):
        return [{"inputs": {"x": x, "y": y}, "output": rule(x, y)} for x, y in pairs]
    return {"schema": SCHEMA, "id": "test", "goal": "infer from observations",
            "train": rows([(0, 0), (1, 2), (3, -1), (-2, 3)]),
            "validation": rows([(4, 5), (-4, 2), (2, -3)])}


class ReasoningIntegrationTests(unittest.TestCase):
    def test_existing_solver_synthesizes_without_model_or_source_execution(self):
        with patch("subprocess.run", side_effect=AssertionError("no process/model call")), \
             patch("builtins.eval", side_effect=AssertionError("no eval")), \
             patch("builtins.exec", side_effect=AssertionError("no exec")):
            out = solve(problem(lambda x, y: x * y))
            self.assertEqual(out["status"], "STAGED_EMPIRICAL")
            self.assertEqual(out["origin"], "INTERNAL_SYNTHESIS")
            self.assertEqual(predict(out["program"], {"x": 11, "y": -7}), -77)
            self.assertEqual(out["external_ai_calls"], 0)

    def test_wrong_typed_advice_has_a_counterexample_and_internal_recovery(self):
        out = solve(problem(), advice=[{"const": 0}])
        self.assertEqual(out["status"], "STAGED_EMPIRICAL")
        self.assertEqual(out["origin"], "INTERNAL_SYNTHESIS")
        self.assertEqual(out["counterexamples"][0]["expected"], 3)

    def test_source_payload_never_runs(self):
        with tempfile.TemporaryDirectory() as d:
            sentinel = Path(d) / "executed"
            payload = {"source": f"open({str(sentinel)!r},'w').write('bad')"}
            out = solve(problem(), advice=[payload])
            self.assertEqual(out["counterexamples"][0]["reason"], "INVALID_IR")
            self.assertFalse(sentinel.exists())

    def test_validation_rejects_training_only_fit(self):
        data = problem()
        data["train"] = [{"inputs": {"x": 0, "y": 0}, "output": 0}]
        out = solve(data)
        self.assertEqual(out["status"], "ABSTAIN")
        self.assertIsNone(out["program"])
        self.assertEqual(out["counterexamples"][-1]["split"], "validation")

    def test_hard_primitive_budget_escapes_upstream_exception_handling(self):
        out = solve(problem(lambda x, y: x * x + y), max_operations=1)
        self.assertEqual(out["status"], "ABSTAIN")
        self.assertEqual(out["reason"], "OPERATION_BUDGET")
        self.assertEqual(out["primitive_operations"], 1)
        self.assertIsNone(out["search_candidates"])

    def test_terminal_labels_cannot_enter_solver_contract(self):
        data = problem()
        data["terminal"] = []
        with self.assertRaises(ValueError):
            Problem.from_data(data)

    def test_conflicting_labels_are_invalid_input(self):
        data = problem()
        data["train"].append({"inputs": {"x": 0, "y": 0}, "output": 1})
        with self.assertRaises(ValueError):
            Problem.from_data(data)

    def test_type_and_size_limits(self):
        lib = Meter().library()
        for tree in ({"var": "__import__"}, {"op": "exec", "args": []},
                     {"op": "add", "args": [{"const": True}, {"const": 1}]}):
            with self.assertRaises(ValueError):
                decode_program(tree, lib)
        tree = {"var": "x"}
        for _ in range(8):
            tree = {"op": "add", "args": [tree, {"const": 1}]}
        with self.assertRaises(ValueError):
            decode_program(tree, lib)
        with self.assertRaises(ValueError):
            predict({"var": "x"}, {"x": True, "y": 0})

    def test_boolean_outputs_are_strict_and_reused(self):
        out = solve(problem(lambda x, y: x < y))
        self.assertIs(predict(out["program"], {"x": 5, "y": -1}), False)

    def test_cross_process_recall_revalidates_executable_knowledge(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(__file__).resolve().parents[2]
            task_path = Path(d) / "task.json"
            task_path.write_text(json.dumps(problem()))
            cmd = [sys.executable, str(root / "tools/ace_reasoning.py"), "--problem", str(task_path),
                   "--workspace", str(Path(d) / "memory")]
            a = json.loads(subprocess.check_output(cmd, text=True))
            b = json.loads(subprocess.check_output(cmd, text=True))
            self.assertEqual(b["origin"], "REVALIDATED_MEMORY")
            self.assertEqual(b["search_candidates"], 0)
            self.assertEqual(a["program_digest"], b["program_digest"])
            self.assertEqual(predict(b["program"], {"x": 9, "y": 13}), 22)

    def test_corrupt_memory_abstains(self):
        with tempfile.TemporaryDirectory() as d, ReasoningMemory(d) as mem:
            solve(problem(), memory=mem)
            mem.db.execute("UPDATE reasoning_knowledge SET payload='{}'")
            out = solve(problem(), memory=mem)
            self.assertEqual(out["status"], "ABSTAIN")
            self.assertIn("checksum", out["reason"])

    def test_memory_is_not_trusted_by_task_name(self):
        with tempfile.TemporaryDirectory() as d, ReasoningMemory(d) as mem:
            solve(problem(), memory=mem)
            out = solve(problem(lambda x, y: x - y), memory=mem)
            self.assertEqual(out["origin"], "INTERNAL_SYNTHESIS")
            self.assertTrue(out["counterexamples"])
            self.assertEqual(predict(out["program"], {"x": 4, "y": 9}), -5)


if __name__ == "__main__":
    unittest.main()
