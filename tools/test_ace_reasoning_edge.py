"""Edge-case unit tests for tools/ace_reasoning.py (read-only target)."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ace_reasoning as ar

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "ace_reasoning.py"


def _valid_problem(
    *,
    problem_id: str = "prob-01",
    goal: str = "x+y",
    train=None,
    validation=None,
) -> dict:
    return {
        "schema": "ace.reasoning.xy.v1",
        "id": problem_id,
        "goal": goal,
        "train": train if train is not None else [{"inputs": {"x": 1, "y": 2}, "output": 3}],
        "validation": validation if validation is not None else [{"inputs": {"x": 4, "y": 5}, "output": 9}],
    }


class AceReasoningEdgeTests(unittest.TestCase):
    """22 edge-case tests for read_bounded and CLI main() in tools/ace_reasoning.py."""

    def _run_main(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with patch("sys.argv", ["ace_reasoning.py", *argv]), contextlib.redirect_stdout(buf):
            rc = ar.main()
        return rc, buf.getvalue()

    def test_01_read_bounded_exact_65536_bytes_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "exact.json"
            base = json.dumps({"k": ""})
            pad = "a" * (65536 - len(base))
            raw = json.dumps({"k": pad}).encode("utf-8")
            self.assertEqual(len(raw), 65536)
            p.write_bytes(raw)
            self.assertEqual(ar.read_bounded(p), {"k": pad})

    def test_02_read_bounded_65537_bytes_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "over.json"
            base = json.dumps({"k": ""})
            pad = "a" * (65537 - len(base))
            raw = json.dumps({"k": pad}).encode("utf-8")
            self.assertEqual(len(raw), 65537)
            p.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "64 KiB"):
                ar.read_bounded(p)

    def test_03_read_bounded_empty_file_raises_json_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.json"
            p.write_text("", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                ar.read_bounded(p)

    def test_04_read_bounded_invalid_utf8_raises_unicode_decode_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bin.json"
            p.write_bytes(b"\xff\xfe\xfd")
            with self.assertRaises(UnicodeDecodeError):
                ar.read_bounded(p)

    def test_05_read_bounded_missing_or_directory_raises_oserror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                ar.read_bounded(Path(tmp) / "missing.json")
            with self.assertRaises(OSError):
                ar.read_bounded(Path(tmp))

    def test_06_main_valid_problem_synthesizes_add_and_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            ws = t / "ws"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(ws)])
            self.assertEqual(rc, 0)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "STAGED_EMPIRICAL")
            self.assertEqual(payload["origin"], "INTERNAL_SYNTHESIS")
            self.assertEqual(payload["release_gate"], "BLOCK_RELEASE")
            self.assertEqual(payload["scientific_status"], "NOT_ASSESSED")

    def test_07_main_valid_advice_used_before_internal_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            adv = t / "advice.json"
            ws = t / "ws"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            adv.write_text(
                json.dumps([{"op": "add", "args": [{"var": "x"}, {"var": "y"}]}]),
                encoding="utf-8",
            )
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(ws), "--advice", str(adv)])
            self.assertEqual(rc, 0)
            payload = json.loads(out)
            self.assertEqual(payload["origin"], "EXTERNAL_ADVICE_UNVERIFIED")
            self.assertEqual(payload["advice_trees_received"], 1)

    def test_08_main_advice_over_4_trees_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            adv = t / "advice.json"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            adv.write_text(json.dumps([{"const": 1}] * 5), encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws"), "--advice", str(adv)])
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_09_main_advice_non_list_dict_or_null_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            adv = t / "advice.json"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            for raw in ("{}", "null", "123"):
                adv.write_text(raw, encoding="utf-8")
                rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws"), "--advice", str(adv)])
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_10_main_advice_exceeding_64kib_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            adv = t / "big_adv.json"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            adv.write_text('["' + ("x" * 70000) + '"]', encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws"), "--advice", str(adv)])
            self.assertEqual(rc, 2)
            self.assertIn("64 KiB", json.loads(out)["reason"])

    def test_11_main_problem_exceeding_64kib_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "big_prob.json"
            p.write_text('{"x": "' + ("a" * 70000) + '"}', encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws")])
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_12_main_problem_missing_file_or_directory_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            for target in (t / "nope.json", t):
                rc, out = self._run_main(["--problem", str(target), "--workspace", str(t / "ws")])
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_13_main_problem_wrong_schema_or_extra_key_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "bad.json"
            bad = _valid_problem()
            bad["schema"] = "wrong.schema.v1"
            p.write_text(json.dumps(bad), encoding="utf-8")
            rc, _ = self._run_main(["--problem", str(p), "--workspace", str(t / "ws")])
            self.assertEqual(rc, 2)

            bad2 = _valid_problem()
            bad2["extra"] = 1
            p.write_text(json.dumps(bad2), encoding="utf-8")
            rc2, _ = self._run_main(["--problem", str(p), "--workspace", str(t / "ws2")])
            self.assertEqual(rc2, 2)

    def test_14_main_problem_out_of_range_xy_or_bool_xy_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "bad_xy.json"
            for bad_inputs in ({"x": 65, "y": 0}, {"x": -65, "y": 0}, {"x": True, "y": 1}, {"x": 1}):
                prob = _valid_problem(train=[{"inputs": bad_inputs, "output": 1}])
                p.write_text(json.dumps(prob), encoding="utf-8")
                rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws")])
                self.assertEqual(rc, 2)
                self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_15_main_problem_train_validation_overlap_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "overlap.json"
            row = [{"inputs": {"x": 2, "y": 3}, "output": 5}]
            p.write_text(json.dumps(_valid_problem(train=row, validation=row)), encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws")])
            self.assertEqual(rc, 2)
            self.assertIn("overlap", json.loads(out)["reason"])

    def test_16_main_problem_mixed_output_types_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "mixed.json"
            prob = _valid_problem(
                train=[
                    {"inputs": {"x": 1, "y": 1}, "output": 2},
                    {"inputs": {"x": 1, "y": 2}, "output": True},
                ]
            )
            p.write_text(json.dumps(prob), encoding="utf-8")
            rc, _ = self._run_main(["--problem", str(p), "--workspace", str(t / "ws")])
            self.assertEqual(rc, 2)

    def test_17_main_problem_empty_id_or_oversized_goal_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "meta.json"
            p.write_text(json.dumps(_valid_problem(problem_id="")), encoding="utf-8")
            rc1, _ = self._run_main(["--problem", str(p), "--workspace", str(t / "ws1")])
            self.assertEqual(rc1, 2)

            p.write_text(json.dumps(_valid_problem(goal="g" * 401)), encoding="utf-8")
            rc2, _ = self._run_main(["--problem", str(p), "--workspace", str(t / "ws2")])
            self.assertEqual(rc2, 2)

    def test_18_main_workspace_is_regular_file_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            bad_ws = t / "not_a_dir"
            bad_ws.write_text("file", encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(bad_ws)])
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")

    def test_19_main_invalid_advice_ir_falls_back_cleanly_to_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            adv = t / "bad_ir.json"
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            adv.write_text(json.dumps([{"op": "eval", "args": []}]), encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws"), "--advice", str(adv)])
            self.assertEqual(rc, 0)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "STAGED_EMPIRICAL")
            self.assertEqual(payload["origin"], "INTERNAL_SYNTHESIS")
            self.assertEqual(payload["counterexamples"][0]["reason"], "INVALID_IR")

    def test_20_main_unsolvable_problem_abstains_with_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "hard.json"
            # Outputs far outside depth-2 arithmetic over x,y -> abstains cleanly.
            prob = _valid_problem(
                train=[{"inputs": {"x": 1, "y": 1}, "output": 99991}],
                validation=[{"inputs": {"x": 2, "y": 2}, "output": 88882}],
            )
            p.write_text(json.dumps(prob), encoding="utf-8")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(t / "ws")])
            self.assertEqual(rc, 0)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "ABSTAIN")

    def test_21_cli_missing_required_args_exits_2_and_valid_subprocess_exits_0(self) -> None:
        p_missing = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p_missing.returncode, 2)

        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            prob = t / "prob.json"
            prob.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            p_ok = subprocess.run(
                [sys.executable, str(SCRIPT), "--problem", str(prob), "--workspace", str(t / "ws")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_ok.returncode, 0, p_ok.stderr)
            self.assertEqual(json.loads(p_ok.stdout)["status"], "STAGED_EMPIRICAL")

    # Bug suspicion: tools/ace_reasoning.py line 34 catches (ValueError, OSError, TypeError),
    # which does NOT catch sqlite3.DatabaseError (subclass of sqlite3.Error -> Exception) when
    # workspace contains a corrupted selfmodel_memory.sqlite3 file.
    @unittest.expectedFailure
    def test_22_corrupt_workspace_sqlite_should_return_exit_2_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            p = t / "prob.json"
            ws = t / "ws"
            ws.mkdir()
            p.write_text(json.dumps(_valid_problem()), encoding="utf-8")
            (ws / "selfmodel_memory.sqlite3").write_bytes(b"NOT A SQLITE DB")
            rc, out = self._run_main(["--problem", str(p), "--workspace", str(ws)])
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out)["status"], "INVALID_INPUT_OR_WORKSPACE")


if __name__ == "__main__":
    unittest.main()
