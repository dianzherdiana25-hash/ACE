"""Tes tepi luring terisolasi untuk tools/ctrlreg_stage0_replay.py (E3 #8, TESTS ONLY)."""

from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "code"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_IMPORT_TMP_DIR = tempfile.TemporaryDirectory(prefix="ace-stage0-import-")
_FAKE_BASE = Path(_IMPORT_TMP_DIR.name)
(_FAKE_BASE / "abc-v3-run-state").mkdir(parents=True, exist_ok=True)
(_FAKE_BASE / "evidence").mkdir(parents=True, exist_ok=True)
(_FAKE_BASE / "abc-v3-run-state" / "discovery_20261501.json").write_text(
    json.dumps({"keys": ["k_alpha"], "chains": [("k_alpha", "k_beta")]}),
    encoding="utf-8",
)

_EXPECTED_DIGEST = "a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68"


def _load_stage0_isolated():
    fake_drv = types.ModuleType("abc_v3_run")
    fake_drv.CAP = 12
    fake_drv.WALL_PER_TASK = 1.5
    fake_drv.split_universe = lambda tasks: {"control": list(tasks[:34])}
    fake_drv._extract_admitted = lambda disc: (list(disc.get("keys", [])), list(disc.get("chains", [])))
    fake_drv.catalog_digest = lambda _k, _c: _EXPECTED_DIGEST
    fake_drv._run_with_wall = lambda fn, _wall: (fn(), False)

    orig_path = pathlib.Path

    def _redirect_path(arg, *rest):
        if str(arg) == "/home/hatch/workspace/ace-omega":
            return _FAKE_BASE
        return orig_path(arg, *rest)

    prev_drv = sys.modules.get("abc_v3_run")
    sys.modules["abc_v3_run"] = fake_drv
    try:
        with mock.patch("pathlib.Path", side_effect=_redirect_path), redirect_stdout(io.StringIO()):
            from tools import ctrlreg_stage0_replay as stage0_mod
    finally:
        if prev_drv is None:
            sys.modules.pop("abc_v3_run", None)
        else:
            sys.modules["abc_v3_run"] = prev_drv
    return stage0_mod


stage0 = _load_stage0_isolated()


def tearDownModule():
    stage0.od._safe_score = stage0._orig_safe_score
    _IMPORT_TMP_DIR.cleanup()


def _sample_task(task_id: str = "t_01") -> dict:
    return {
        "task_id": task_id,
        "shown_cases": [[[1, 2]], [[3, 4]]],
        "shown_truth": [[1, 2], [3, 4]],
        "holdout_cases": [[[5, 6]], [[7, 8]]],
        "holdout_truth": [[5, 6], [7, 8]],
    }


class TestCtrlregStage0ReplayE3(unittest.TestCase):
    """Uji unit tepi untuk replay_task, run_config, main, dan helper atomik stage0."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.state_dir = self.tmp_path / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_file = self.tmp_path / "evidence" / "ctrlreg_stage0_replay.json"
        self.evidence_file.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        stage0._counter["active"] = False
        stage0._counter["calls"] = 0
        stage0._counter["scored"] = []
        self._tmp.cleanup()

    def test_01_import_bootstrap_builds_34_control_tasks_and_arms(self):
        self.assertEqual(len(stage0.control), 34)
        self.assertEqual(stage0.digest, _EXPECTED_DIGEST)
        self.assertEqual(stage0.ARMS["A"], ((), ()))
        self.assertEqual(stage0.ARMS["B"][0], ("k_alpha",))
        self.assertEqual(stage0.ARMS["B"][1], ())
        self.assertEqual(len(stage0.ARMS["C"][1]), 1)

    def test_02_atomic_write_replaces_existing_file_without_leaving_tmp(self):
        target = self.tmp_path / "ckpt.json"
        stage0._atomic_write(target, '{"v": 1}')
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"v": 1})
        stage0._atomic_write(target, '{"v": 2, "text": "unicode-α"}')
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"v": 2, "text": "unicode-α"})
        self.assertFalse(target.with_name(target.name + ".tmp").exists())

    def test_03_counting_safe_score_tracks_only_when_counter_active(self):
        with mock.patch.object(stage0, "_orig_safe_score", return_value=2) as orig_mock:
            stage0._counter["active"] = False
            self.assertEqual(stage0._counting_safe_score("b", "def f(x): return x", 0.25), 2)
            self.assertEqual(stage0._counter["calls"], 0)
            self.assertEqual(stage0._counter["scored"], [])

            stage0._counter["active"] = True
            self.assertEqual(stage0._counting_safe_score("b", "def f(x): return x", 0.25), 2)
            self.assertEqual(stage0._counter["calls"], 1)
            self.assertEqual(
                stage0._counter["scored"],
                [hashlib.sha256(b"def f(x): return x").hexdigest()],
            )
            orig_mock.assert_called_with("b", "def f(x): return x", 0.25)

    def test_04_replay_task_solved_records_hashes_trace_and_cap_hit_false(self):
        task = _sample_task("task_ok")

        def fake_solve(_t, _adapter, _keys, _chains, max_score_calls=None, trace=None):
            stage0._counting_safe_score("b", "cand_1")
            stage0._counting_safe_score("b", "cand_2")
            if trace is not None:
                trace.append(("admitted", {"k": 1}))
                trace.append(("empty_payload", None))
            return "def solve(g): return g"

        with (
            mock.patch.object(stage0, "solve_task", side_effect=fake_solve),
            mock.patch.object(stage0, "_orig_safe_score", return_value=2),
            mock.patch.object(stage0.GRID_ADAPTER, "make_budget", return_value="b"),
            mock.patch.object(stage0.GRID_ADAPTER, "passes", return_value=2),
            mock.patch.object(stage0.drv, "_run_with_wall", side_effect=lambda fn, _w: (fn(), False)),
        ):
            rec = stage0.replay_task(task, ("k1",), (), cap=5)

        self.assertEqual(rec["task_id"], "task_ok")
        self.assertTrue(rec["solved"])
        self.assertFalse(rec["timeout"])
        self.assertEqual(rec["holdout_passes"], 2)
        self.assertEqual(rec["holdout_total"], 2)
        self.assertEqual(rec["shown_score"], 2)
        self.assertEqual(rec["shown_total"], 2)
        self.assertEqual(rec["score_calls"], 2)
        self.assertEqual(rec["scored_variants"], 2)
        self.assertFalse(rec["cap_hit"])
        self.assertEqual(rec["returned_sha256"], hashlib.sha256(b"def solve(g): return g").hexdigest())
        self.assertEqual(rec["trace"], [["admitted", "{'k': 1}"], ["empty_payload", None]])
        self.assertFalse(stage0._counter["active"])

    def test_05_replay_task_cap_hit_true_and_unsolved_when_holdout_partial(self):
        task = _sample_task("task_cap")

        def fake_solve(_t, _adapter, _keys, _chains, max_score_calls=None, trace=None):
            for i in range(3):
                stage0._counting_safe_score("b", f"c_{i}")
            return "code_v"

        with (
            mock.patch.object(stage0, "solve_task", side_effect=fake_solve),
            mock.patch.object(stage0, "_orig_safe_score", return_value=1),
            mock.patch.object(stage0.GRID_ADAPTER, "make_budget", return_value="b"),
            mock.patch.object(stage0.GRID_ADAPTER, "passes", return_value=1),
            mock.patch.object(stage0.drv, "_run_with_wall", side_effect=lambda fn, _w: (fn(), False)),
        ):
            rec = stage0.replay_task(task, (), (), cap=3)

        self.assertFalse(rec["solved"])
        self.assertTrue(rec["cap_hit"])
        self.assertEqual(rec["score_calls"], 3)

    def test_06_replay_task_uncapped_never_marks_cap_hit(self):
        task = _sample_task("task_uncapped")

        def fake_solve(_t, _adapter, _keys, _chains, max_score_calls=None, trace=None):
            stage0._counting_safe_score("b", "c0")
            return "code_u"

        with (
            mock.patch.object(stage0, "solve_task", side_effect=fake_solve),
            mock.patch.object(stage0, "_orig_safe_score", return_value=2),
            mock.patch.object(stage0.GRID_ADAPTER, "make_budget", return_value="b"),
            mock.patch.object(stage0.GRID_ADAPTER, "passes", return_value=2),
            mock.patch.object(stage0.drv, "_run_with_wall", side_effect=lambda fn, _w: (fn(), False)),
        ):
            rec = stage0.replay_task(task, (), (), cap=None)

        self.assertFalse(rec["cap_hit"])
        self.assertTrue(rec["solved"])

    def test_07_replay_task_timeout_returns_minimal_unsolved_record(self):
        task = _sample_task("task_to")
        with mock.patch.object(stage0.drv, "_run_with_wall", return_value=(None, True)):
            rec = stage0.replay_task(task, (), (), cap=10)
        self.assertEqual(rec, {"task_id": "task_to", "solved": False, "timeout": True})

    def test_08_replay_task_resets_counter_active_flag_if_solve_raises(self):
        task = _sample_task("task_err")
        with (
            mock.patch.object(stage0, "solve_task", side_effect=RuntimeError("solver crash")),
            mock.patch.object(stage0.drv, "_run_with_wall", side_effect=lambda fn, _w: (fn(), False)),
        ):
            with self.assertRaisesRegex(RuntimeError, "solver crash"):
                stage0.replay_task(task, (), (), cap=5)
        self.assertFalse(stage0._counter["active"])

    def test_09_run_config_skips_immediately_when_checkpoint_already_complete(self):
        ckpt = self.state_dir / "A_capped.json"
        saved = {"arm": "A", "cap": 12, "complete": True, "solved": 34, "total": 34, "wall_seconds": 1.2, "records": []}
        ckpt.write_text(json.dumps(saved), encoding="utf-8")
        with (
            mock.patch.object(stage0, "STATE", self.state_dir),
            mock.patch.object(stage0, "replay_task") as rep_mock,
            redirect_stdout(io.StringIO()),
        ):
            out = stage0.run_config("A", 12)
        rep_mock.assert_not_called()
        self.assertEqual(out, saved)

    def test_10_run_config_resumes_incomplete_checkpoint_and_accumulates_wall(self):
        tasks = [{"task_id": "t1"}, {"task_id": "t2"}, {"task_id": "t3"}]
        ckpt = self.state_dir / "B_capped.json"
        ckpt.write_text(
            json.dumps(
                {
                    "arm": "B",
                    "cap": 12,
                    "complete": False,
                    "solved": 1,
                    "total": 1,
                    "wall_seconds": 3.5,
                    "records": [{"task_id": "t1", "solved": True, "score_calls": 2}],
                }
            ),
            encoding="utf-8",
        )
        seen = []

        def fake_replay(task, _k, _c, _cap):
            seen.append(task["task_id"])
            return {"task_id": task["task_id"], "solved": task["task_id"] == "t2", "score_calls": 4}

        with (
            mock.patch.object(stage0, "STATE", self.state_dir),
            mock.patch.object(stage0, "control", tasks),
            mock.patch.object(stage0, "replay_task", side_effect=fake_replay),
            redirect_stdout(io.StringIO()),
        ):
            out = stage0.run_config("B", 12)

        self.assertEqual(seen, ["t2", "t3"])
        self.assertTrue(out["complete"])
        self.assertEqual(out["solved"], 2)
        self.assertEqual(out["total"], 3)
        self.assertGreaterEqual(out["wall_seconds"], 3.5)
        persisted = json.loads(ckpt.read_text(encoding="utf-8"))
        self.assertTrue(persisted["complete"])
        self.assertEqual(len(persisted["records"]), 3)

    def test_11_run_config_uncapped_uses_uncapped_checkpoint_filename(self):
        tasks = [{"task_id": "u1"}]
        with (
            mock.patch.object(stage0, "STATE", self.state_dir),
            mock.patch.object(stage0, "control", tasks),
            mock.patch.object(
                stage0, "replay_task", return_value={"task_id": "u1", "solved": True, "score_calls": 1}
            ),
            redirect_stdout(io.StringIO()),
        ):
            out = stage0.run_config("C", None)
        self.assertTrue((self.state_dir / "C_uncapped.json").exists())
        self.assertIsNone(out["cap"])
        self.assertEqual(out["solved"], 1)

    def test_12_run_config_rejects_unknown_arm_key_error(self):
        with mock.patch.object(stage0, "STATE", self.state_dir):
            with self.assertRaises(KeyError):
                stage0.run_config("Z", 12)

    def test_13_main_fence_failure_writes_artifact_suspect_and_skips_uncapped(self):
        calls = []

        def fake_run_config(arm, cap):
            calls.append((arm, cap))
            solved = 34 if arm == "A" else (31 if arm == "B" else 32)  # B misses 32 fence
            return {"solved": solved, "total": 34, "wall_seconds": 0.1, "records": []}

        with (
            mock.patch.object(stage0, "EVIDENCE", self.evidence_file),
            mock.patch.object(stage0, "run_config", side_effect=fake_run_config),
            redirect_stdout(io.StringIO()),
        ):
            stage0.main()

        self.assertEqual(calls, [("A", stage0.CAP), ("B", stage0.CAP), ("C", stage0.CAP)])
        ev = json.loads(self.evidence_file.read_text(encoding="utf-8"))
        self.assertFalse(ev["fence_reproduced"])
        self.assertEqual(ev["verdict"], "ARTIFACT_SUSPECT")
        self.assertNotIn("A_uncapped", ev["configurations"])

    def test_14_main_fence_reproduced_runs_uncapped_and_compares_same_failed_tasks(self):
        calls = []

        def make_records(fail_ids):
            return [
                {"task_id": f"t_{i:02d}", "solved": f"t_{i:02d}" not in fail_ids}
                for i in range(34)
            ]

        def fake_run_config(arm, cap):
            calls.append((arm, cap))
            if cap is not None:
                if arm == "A":
                    recs = make_records(set())
                else:
                    recs = make_records({"t_03", "t_09"})
            else:
                recs = make_records(set())
            return {
                "solved": sum(1 for r in recs if r["solved"]),
                "total": len(recs),
                "wall_seconds": 0.2,
                "records": recs,
            }

        with (
            mock.patch.object(stage0, "EVIDENCE", self.evidence_file),
            mock.patch.object(stage0, "run_config", side_effect=fake_run_config),
            redirect_stdout(io.StringIO()),
        ):
            stage0.main()

        self.assertEqual(len(calls), 6)
        ev = json.loads(self.evidence_file.read_text(encoding="utf-8"))
        self.assertTrue(ev["fence_reproduced"])
        self.assertEqual(ev["verdict"], "REPRODUCED")
        self.assertTrue(ev["same_tasks_B_C"])
        self.assertEqual(ev["capped_failed_task_ids"]["B"], ["t_03", "t_09"])
        self.assertEqual(ev["configurations"]["C_uncapped"]["solved"], 34)

    def test_15_main_fence_reproduced_detects_different_failed_tasks_between_b_and_c(self):
        def make_records(fail_ids):
            return [
                {"task_id": f"t_{i:02d}", "solved": f"t_{i:02d}" not in fail_ids}
                for i in range(34)
            ]

        def fake_run_config(arm, cap):
            if cap is not None:
                if arm == "A":
                    recs = make_records(set())
                elif arm == "B":
                    recs = make_records({"t_01", "t_02"})
                else:
                    recs = make_records({"t_01", "t_99"} if False else {"t_01", "t_05"})
            else:
                recs = make_records(set())
            return {
                "solved": sum(1 for r in recs if r["solved"]),
                "total": len(recs),
                "wall_seconds": 0.1,
                "records": recs,
            }

        with (
            mock.patch.object(stage0, "EVIDENCE", self.evidence_file),
            mock.patch.object(stage0, "run_config", side_effect=fake_run_config),
            redirect_stdout(io.StringIO()),
        ):
            stage0.main()

        ev = json.loads(self.evidence_file.read_text(encoding="utf-8"))
        self.assertEqual(ev["verdict"], "REPRODUCED")
        self.assertFalse(ev["same_tasks_B_C"])


if __name__ == "__main__":
    unittest.main()
