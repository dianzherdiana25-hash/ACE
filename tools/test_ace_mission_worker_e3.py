"""Tes tepi luring untuk tools/ace_mission_worker.py (E3 #5, TESTS ONLY)."""

from __future__ import annotations

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

from tools import ace_mission_worker as mw  # noqa: E402
from tools.ace_reasoning_benchmark import RULES, SEEDS, make_problem  # noqa: E402


class TestAceMissionWorkerE3(unittest.TestCase):
    """Uji unit tepi untuk 4 simbol publik tools/ace_mission_worker.py."""

    def test_01_log_formats_utc_timestamp_and_prefix(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            mw.log("pesan uji")
        out = buf.getvalue().strip()
        self.assertRegex(out, r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\] \[MissionWorker\] pesan uji$")

    def test_02_solve_mission_rejects_invalid_and_traversal_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            arts = Path(tmp)
            for bad_id in ("../escape", "", "a/b", "m" * 101, 123, None):
                mission = {"id": bad_id, "goal": "g", "hypothesis": "h"}
                with self.assertRaisesRegex(ValueError, "invalid mission artifact id"):
                    mw.solve_mission(mission, arts)

    def test_03_solve_mission_reasoning_insufficient_or_non_int_budget_abstains(self):
        task, _ = make_problem(RULES[0], SEEDS[0])
        with tempfile.TemporaryDirectory() as tmp:
            arts = Path(tmp)
            for bad_cap in (4999, 0, -1, True, "5000", None):
                mission = {
                    "id": f"m_{type(bad_cap).__name__}",
                    "goal": "g",
                    "hypothesis": "h",
                    "budget": {"max_candidates": bad_cap, "time_sec": 5},
                    "reasoning_problem": task,
                }
                with mock.patch.object(mw, "solve") as solve_mock:
                    path, dec, reason = mw.solve_mission(mission, arts)
                solve_mock.assert_not_called()
                self.assertEqual(dec, "INCONCLUSIVE")
                self.assertEqual(reason, "INSUFFICIENT_SEARCH_BUDGET")
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["schema"], mw.ARTIFACT_SCHEMA)
                self.assertIsNone(payload["program"])

    def test_04_solve_mission_reasoning_valid_budget_caps_seconds_and_stages(self):
        task, _ = make_problem(RULES[0], SEEDS[0])
        with tempfile.TemporaryDirectory() as tmp:
            arts = Path(tmp)
            mission = {
                "id": "m_reason_ok",
                "goal": "Infer",
                "hypothesis": "Add",
                "budget": {"max_candidates": 5000, "time_sec": 99.0, "max_primitive_operations": 300_000},
                "reasoning_problem": task,
            }
            with mock.patch.object(mw, "solve", wraps=mw.solve) as spy_solve:
                path, dec, _reason = mw.solve_mission(mission, arts)
            spy_solve.assert_called_once()
            self.assertEqual(spy_solve.call_args.kwargs["seconds"], 5.0)
            self.assertEqual(dec, "STAGED_EMPIRICAL")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(payload["program"])
            self.assertEqual(payload["problem_digest"], mw.digest(task))

    def test_05_solve_mission_reasoning_returns_inconclusive_when_solver_abstains(self):
        task, _ = make_problem(RULES[0], SEEDS[0])
        with tempfile.TemporaryDirectory() as tmp:
            arts = Path(tmp)
            mission = {
                "id": "m_reason_abstain",
                "goal": "Infer",
                "hypothesis": "None",
                "budget": {"max_candidates": 5000, "time_sec": 2.0},
                "reasoning_problem": task,
            }
            with mock.patch.object(mw, "solve", return_value={"program": None, "reason": "NO_MATCH"}):
                path, dec, reason = mw.solve_mission(mission, arts)
            self.assertEqual(dec, "INCONCLUSIVE")
            self.assertEqual(reason, "NO_MATCH")
            self.assertIsNone(json.loads(path.read_text(encoding="utf-8"))["program"])

    def test_06_solve_mission_template_families_produce_valid_python_files(self):
        cases = [
            (["late_flip_drift"], "SemanticDriftQuarantine"),
            (["boundary"], "word.startswith"),
            (["graph_connectivity"], "GraphAdjacencyPrimitive"),
            (["modular_congruence"], "def solve_m_case"),
            (["active_query_boundary"], "abs(word.count"),
            (["ratio_4_1_noise"], "def solve_m_case"),
            (["unknown_family"], "len(word) > 0"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            arts = Path(tmp)
            for idx, (families, marker) in enumerate(cases):
                mission = {
                    "id": f"m_case_{idx}" if idx not in (3, 5) else "m_case",
                    "goal": "g",
                    "hypothesis": "h",
                    "task_family_ids": families,
                }
                path, dec, _ = mw.solve_mission(mission, arts)
                self.assertTrue(path.name.endswith(".py"))
                self.assertEqual(dec, "PENDING_EVALUATION")
                self.assertIn(marker, path.read_text(encoding="utf-8"))

    def test_07_solve_mission_marks_rejected_when_integrity_check_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            arts = Path(tmp)
            mission = {"id": "m-cheat", "goal": "g", "hypothesis": "h", "task_family_ids": ["boundary"]}
            with mock.patch.object(
                mw, "evaluate_candidate_integrity", return_value={"admitted": False, "reasons": ["forbidden"]}
            ):
                _path, dec, reason = mw.solve_mission(mission, arts)
            self.assertEqual(dec, "REJECTED")
            self.assertIn("Cheating detection triggered:", reason)

    def test_08_run_worker_loop_zero_max_missions_does_no_work(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            processed, status = mw.run_worker_loop(Path(tmp), max_missions_to_process=0)
        self.assertEqual(processed, 0)
        self.assertEqual(status["total_submissions"], 0)
        self.assertTrue(status["hash_chain_valid"])

    def test_09_run_worker_loop_breaks_cleanly_if_generator_produces_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(mw.MissionGenerator, "generate_from_diagnostics", return_value=[]) as gen_mock,
                redirect_stdout(io.StringIO()) as buf,
            ):
                processed, _status = mw.run_worker_loop(Path(tmp), max_missions_to_process=3)
            gen_mock.assert_called_once()
            self.assertEqual(processed, 0)
            self.assertIn("Queue completed and no further missions generated.", buf.getvalue())

    def test_10_run_worker_loop_autogenerates_and_submits_with_supplied_template_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(mw.MissionBus, "submit_mission", wraps=None) as submit_spy:
                submit_spy.side_effect = lambda **kw: {
                    "decision": kw["decision"],
                    "evaluation": {"reason": "mocked"},
                    "artifact_sha": "a" * 64,
                }
                with redirect_stdout(io.StringIO()):
                    processed, _status = mw.run_worker_loop(Path(tmp), max_missions_to_process=1)
            self.assertEqual(processed, 1)
            self.assertEqual(submit_spy.call_args.kwargs["provenance"], "SUPPLIED_TEMPLATE")

    def test_11_run_worker_loop_processes_enqueued_reasoning_mission_with_internal_provenance(self):
        task, _ = make_problem(RULES[0], SEEDS[0])
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            mw.MissionBus(ws / "mission_bus.sqlite3").create_mission(
                goal="Infer addition",
                hypothesis="Add xy",
                task_family_ids=["arithmetic_xy"],
                inputs=[],
                forbidden=[],
                budget={"time_sec": 5, "max_candidates": 5000, "max_primitive_operations": 300_000},
                acceptance={"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
                reasoning_problem=task,
            )
            with mock.patch.object(mw.MissionBus, "submit_mission", wraps=mw.MissionBus(ws / "mission_bus.sqlite3").submit_mission) as sub:
                with redirect_stdout(io.StringIO()):
                    processed, status = mw.run_worker_loop(ws, max_missions_to_process=1)
            self.assertEqual(processed, 1)
            self.assertEqual(sub.call_args.kwargs["provenance"], "INTERNAL_SYNTHESIS")
            self.assertTrue(status["hash_chain_valid"])

    def test_12_main_rejects_problem_combined_with_continuous(self):
        with (
            mock.patch.object(sys, "argv", ["mw", "--problem", "/tmp/p.json", "--continuous"]),
            mock.patch("sys.stderr", new=io.StringIO()) as err,
        ):
            with self.assertRaises(SystemExit) as ctx:
                mw.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("--problem is one-shot", err.getvalue())

    def test_13_main_rejects_oversized_problem_file_over_64kib(self):
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.json"
            big.write_bytes(b"x" * 65_537)
            with (
                mock.patch.object(sys, "argv", ["mw", "--workspace", tmp, "--problem", str(big)]),
                mock.patch("sys.stderr", new=io.StringIO()) as err,
            ):
                with self.assertRaises(SystemExit) as ctx:
                    mw.main()
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("64 KiB", err.getvalue())

    def test_14_main_rejects_malformed_json_problem_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not-json", encoding="utf-8")
            with mock.patch.object(sys, "argv", ["mw", "--workspace", tmp, "--problem", str(bad)]):
                with self.assertRaises(json.JSONDecodeError):
                    mw.main()

    def test_15_main_problem_runs_one_shot_worker_end_to_end(self):
        task, _ = make_problem(RULES[0], SEEDS[0])
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            prob = Path(tmp) / "problem.json"
            prob.write_text(json.dumps(task), encoding="utf-8")
            with (
                mock.patch.object(sys, "argv", ["mw", "--workspace", str(ws), "--problem", str(prob)]),
                mock.patch.object(mw, "run_worker_loop") as loop_mock,
            ):
                mw.main()
            loop_mock.assert_called_once_with(ws, max_missions_to_process=1)
            status = mw.MissionBus(ws / "mission_bus.sqlite3").status()
            self.assertEqual(sum(status["mission_counts"].values()), 1)

    def test_16_main_continuous_mode_sleeps_between_iterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    sys,
                    "argv",
                    ["mw", "--workspace", tmp, "--continuous", "--max-missions", "2", "--sleep-seconds", "7"],
                ),
                mock.patch.object(mw, "run_worker_loop") as loop_mock,
                mock.patch.object(mw.time, "sleep", side_effect=[None, KeyboardInterrupt()]) as sleep_mock,
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    mw.main()
            self.assertEqual(loop_mock.call_count, 2)
            loop_mock.assert_called_with(Path(tmp), max_missions_to_process=2)
            sleep_mock.assert_called_with(7)


if __name__ == "__main__":
    unittest.main()
