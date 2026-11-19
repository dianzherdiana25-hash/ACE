"""Tes tepi luring terisolasi untuk tools/ctrlreg_stage1_counterfactual.py (E3 #9, TESTS ONLY)."""

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

_DIGEST = "a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68"
_TASKS = ("catalog_control-020", "catalog_control-021")
_KEYS = [("k", 1), ("k", 2), ("k", 3)]
_A_WIN = {t: hashlib.sha256(f"awin-{t}".encode()).hexdigest() for t in _TASKS}

_IMPORT_TMP = tempfile.TemporaryDirectory(prefix="ace-stage1-import-")
_FAKE_BASE = Path(_IMPORT_TMP.name)
(_FAKE_BASE / "abc-v3-run-state").mkdir(parents=True)
(_FAKE_BASE / "ctrlreg-stage0-state").mkdir(parents=True)
(_FAKE_BASE / "evidence").mkdir(parents=True)
(_FAKE_BASE / "abc-v3-run-state" / "discovery_20261501.json").write_text("{}", encoding="utf-8")
(_FAKE_BASE / "ctrlreg-stage0-state" / "A_capped.json").write_text(
    json.dumps({"records": [{"task_id": t, "returned_sha256": _A_WIN[t]} for t in _TASKS]}),
    encoding="utf-8",
)


def _task(tid):
    return {
        "task_id": tid,
        "shown_cases": [[1], [2]],
        "holdout_cases": [[3], [4]],
        "holdout_truth": [3, 4],
    }


def _load():
    fake_drv = types.ModuleType("abc_v3_run")
    fake_drv.CAP = 7
    fake_drv.WALL_PER_TASK = 1.0
    fake_drv.split_universe = lambda tasks: {"control": [_task(t) for t in _TASKS]}
    fake_drv._extract_admitted = lambda disc: (list(_KEYS), [])
    fake_drv.catalog_digest = lambda k, c: _DIGEST
    fake_drv._run_with_wall = lambda fn, w: (fn(), False)
    orig = pathlib.Path

    def redirect(arg, *rest):
        if str(arg) == "/home/hatch/workspace/ace-omega":
            return _FAKE_BASE
        return orig(arg, *rest)

    prev = sys.modules.get("abc_v3_run")
    sys.modules["abc_v3_run"] = fake_drv
    try:
        with mock.patch("pathlib.Path", side_effect=redirect), redirect_stdout(io.StringIO()):
            from tools import ctrlreg_stage1_counterfactual as mod
    finally:
        if prev is None:
            sys.modules.pop("abc_v3_run", None)
        else:
            sys.modules["abc_v3_run"] = prev
    return mod


s1 = _load()


def tearDownModule():
    s1.od._safe_score = s1._orig
    _IMPORT_TMP.cleanup()


class TestCtrlregStage1E3(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.evidence = self.tmp / "ev.json"

    def tearDown(self):
        s1._rec["active"] = False
        s1._rec["hashes"] = []
        self._tmp.cleanup()

    def test_01_import_bootstrap_builds_control_and_a_win(self):
        self.assertEqual(set(s1.control), set(_TASKS))
        self.assertEqual(s1.A_WIN, _A_WIN)
        self.assertEqual(s1.keys, _KEYS)

    def test_02_atomic_write_replaces_without_tmp_leftover(self):
        p = self.tmp / "x.json"
        s1._atomic_write(p, "1")
        s1._atomic_write(p, "2")
        self.assertEqual(p.read_text(), "2")
        self.assertFalse(p.with_name("x.json.tmp").exists())

    def test_03_recording_only_when_active(self):
        with mock.patch.object(s1, "_orig", return_value=1):
            s1._rec["active"] = False
            s1._recording("b", "code")
            self.assertEqual(s1._rec["hashes"], [])
            s1._rec["active"] = True
            s1._recording("b", "code")
            self.assertEqual(s1._rec["hashes"], [hashlib.sha256(b"code").hexdigest()])

    def _solve(self, tid, scored_codes, passes, solve_side=None):
        def fake_solve(task, adapter, keys, chains, max_score_calls=None, trace=None):
            for c in scored_codes:
                s1._recording("b", c)
            trace.append(("key", ("k", 1)))
            trace.append(("note", None))
            return "final"

        with (
            mock.patch.object(s1, "solve_task", side_effect=solve_side or fake_solve),
            mock.patch.object(s1, "_orig", return_value=2),
            mock.patch.object(s1.GRID_ADAPTER, "make_budget", return_value="b"),
            mock.patch.object(s1.GRID_ADAPTER, "passes", return_value=passes),
        ):
            return s1.solve_instr(s1.control[tid], _KEYS)

    def test_04_solve_instr_records_solved_and_a_solution_scored(self):
        tid = _TASKS[0]
        rec = self._solve(tid, ["c1", "awin-" + tid], passes=2)
        self.assertTrue(rec["solved"])
        self.assertFalse(rec["timeout"])
        self.assertTrue(rec["a_solution_scored"])
        self.assertEqual(rec["n_scored"], 2)
        self.assertEqual(rec["returned_sha256"], hashlib.sha256(b"final").hexdigest())
        self.assertEqual(rec["trace"], [["key", "('k', 1)"], ["note", None]])
        self.assertFalse(s1._rec["active"])

    def test_05_solve_instr_unsolved_and_a_solution_not_scored(self):
        rec = self._solve(_TASKS[1], ["c1"], passes=1)
        self.assertFalse(rec["solved"])
        self.assertFalse(rec["a_solution_scored"])

    def test_06_scored_multiset_hash_is_order_independent(self):
        r1 = self._solve(_TASKS[0], ["a", "b", "c"], passes=2)
        r2 = self._solve(_TASKS[0], ["c", "a", "b"], passes=2)
        self.assertEqual(r1["scored_multiset_sha256"], r2["scored_multiset_sha256"])
        r3 = self._solve(_TASKS[0], ["a", "b"], passes=2)
        self.assertNotEqual(r1["scored_multiset_sha256"], r3["scored_multiset_sha256"])

    def test_07_solve_instr_zero_scored_variants(self):
        rec = self._solve(_TASKS[0], [], passes=2)
        self.assertEqual(rec["n_scored"], 0)
        self.assertEqual(rec["score_calls"], 0)

    def test_08_solve_instr_timeout_minimal_record(self):
        with mock.patch.object(s1.drv, "_run_with_wall", return_value=(None, True)):
            rec = s1.solve_instr(s1.control[_TASKS[0]], _KEYS)
        self.assertEqual(rec, {"task_id": _TASKS[0], "solved": False, "timeout": True})

    def test_09_solve_instr_resets_active_flag_on_solver_error(self):
        def boom(*a, **k):
            raise RuntimeError("crash")

        with self.assertRaisesRegex(RuntimeError, "crash"):
            self._solve(_TASKS[0], [], passes=0, solve_side=boom)
        self.assertFalse(s1._rec["active"])

    def test_10_run_experiment_writes_checkpoint_for_both_tasks(self):
        with (
            mock.patch.object(s1, "STATE", self.state),
            mock.patch.object(s1, "solve_instr", side_effect=lambda t, k, c=(): {"task_id": t["task_id"], "solved": True}),
            redirect_stdout(io.StringIO()),
        ):
            out = s1.run_experiment("exp1", _KEYS)
        self.assertEqual(set(out["records"]), set(_TASKS))
        self.assertTrue((self.state / "exp1.json").exists())

    def test_11_run_experiment_skips_existing_checkpoint(self):
        saved = {"experiment": "exp2", "records": {}}
        (self.state / "exp2.json").write_text(json.dumps(saved), encoding="utf-8")
        with (
            mock.patch.object(s1, "STATE", self.state),
            mock.patch.object(s1, "solve_instr") as si,
            redirect_stdout(io.StringIO()),
        ):
            out = s1.run_experiment("exp2", _KEYS)
        si.assert_not_called()
        self.assertEqual(out, saved)

    def test_12_main_runs_loo_per_trace_key_and_8_perms(self):
        stage0 = self.tmp / "stage0"
        stage0.mkdir()
        (stage0 / "B_capped.json").write_text(
            json.dumps({"records": [
                {"task_id": _TASKS[0], "trace": [["key", "('k', 1)"], ["key", "('k', 2)"], ["other", None]]},
                {"task_id": "unrelated", "trace": [["key", "('k', 3)"]]},
            ]}),
            encoding="utf-8",
        )
        base = types.SimpleNamespace()
        calls = []

        def fake_run(name, arm_keys, arm_chains=()):
            calls.append((name, list(arm_keys)))
            return {"records": {"r": name}}

        fake_base = self.tmp
        (fake_base / "ctrlreg-stage0-state").mkdir(exist_ok=True)
        (fake_base / "ctrlreg-stage0-state" / "B_capped.json").write_text(
            (stage0 / "B_capped.json").read_text(), encoding="utf-8"
        )
        with (
            mock.patch.object(s1, "BASE", fake_base),
            mock.patch.object(s1, "EVIDENCE", self.evidence),
            mock.patch.object(s1, "run_experiment", side_effect=fake_run),
            redirect_stdout(io.StringIO()),
        ):
            s1.main()
        names = [c[0] for c in calls]
        self.assertEqual(names[0], "full_B")
        self.assertEqual(names[1:3], ["loo_0", "loo_1"])
        self.assertIn("loo_all_trace_keys", names)
        self.assertEqual(sum(n.startswith("perm_") for n in names), 8)
        loo_all = dict(calls)["loo_all_trace_keys"]
        self.assertEqual(loo_all, [("k", 3)])
        for n, ks in calls:
            if n.startswith("perm_"):
                self.assertEqual(sorted(ks), sorted(_KEYS))
        ev = json.loads(self.evidence.read_text(encoding="utf-8"))
        self.assertEqual(ev["tasks"], list(_TASKS))
        self.assertEqual(len(ev["permutations"]), 8)
        self.assertEqual(set(ev["loo_by_trace_key"]), {"('k', 1)", "('k', 2)"})

    def test_13_main_permutations_are_deterministic_across_runs(self):
        (self.tmp / "ctrlreg-stage0-state").mkdir(exist_ok=True)
        (self.tmp / "ctrlreg-stage0-state" / "B_capped.json").write_text(
            json.dumps({"records": []}), encoding="utf-8"
        )

        def run_once():
            seen = []
            with (
                mock.patch.object(s1, "BASE", self.tmp),
                mock.patch.object(s1, "EVIDENCE", self.evidence),
                mock.patch.object(
                    s1, "run_experiment",
                    side_effect=lambda n, k, c=(): (seen.append((n, list(k))) or {"records": {}}),
                ),
                redirect_stdout(io.StringIO()),
            ):
                s1.main()
            return [x for x in seen if x[0].startswith("perm_")]

        self.assertEqual(run_once(), run_once())


if __name__ == "__main__":
    unittest.main()
