"""E3 thick edge tests for tools/regression_anchor.py (tests only, 0/10 -> 10/10 symbols)."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CODE_DIR = _REPO_ROOT / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from tools import regression_anchor as ra


def _sample_tasks() -> list[dict]:
    """Synthetic minimal universe tasks mirroring grid_generalization split shape."""
    tasks = []
    idx = 0
    for cls in ra.CLASSES:
        for j in range(5):
            idx += 1
            tasks.append(
                {
                    "task_id": f"{cls}_{j}",
                    "subset": "new_only",
                    "defects": [cls],
                    "holdout_cases": [([1],)],
                    "holdout_truth": [1],
                }
            )
    for j in range(8):
        idx += 1
        tasks.append(
            {
                "task_id": f"mixed_{j}",
                "subset": "new_only",
                "defects": [ra.CLASSES[0], ra.CLASSES[1]],
                "holdout_cases": [([1],)],
                "holdout_truth": [1],
            }
        )
    tasks.append(
        {
            "task_id": "old_ignored",
            "subset": "baseline_only",
            "defects": [ra.CLASSES[0]],
            "holdout_cases": [([1],)],
            "holdout_truth": [1],
        }
    )
    return tasks


class RegressionAnchorEdgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.ev = self.base / "evidence"
        self.ev.mkdir()
        self.v4 = self.ev / "operator_discovery_v4.json"
        self.v4.write_text(
            json.dumps(
                {
                    "by_class": {
                        "bounds_off_by_one": {
                            "admitted_operators": ["('swap', 1)"],
                            "admitted_chains": ["(('swap', 1), ('add', 2))"],
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        for attr, val in (("BASE", self.base), ("EVIDENCE", self.ev), ("V4_EVIDENCE", self.v4)):
            p = mock.patch.object(ra, attr, val)
            p.start()
            self.addCleanup(p.stop)

    def test_01_bucket_of_single_and_mixed_defects(self) -> None:
        self.assertEqual(ra.bucket_of({"defects": ["wall_char_x"]}), "wall_char_x")
        self.assertEqual(ra.bucket_of({"defects": ["a", "b"]}), "mixed")
        self.assertEqual(ra.bucket_of({"defects": []}), "mixed")

    def test_02_battery_id_of_is_sha256_and_order_sensitive(self) -> None:
        t1 = [{"task_id": "a"}, {"task_id": "b"}]
        t2 = [{"task_id": "b"}, {"task_id": "a"}]
        h1 = ra.battery_id_of(t1)
        self.assertEqual(len(h1), 64)
        self.assertEqual(h1, ra.battery_id_of(t1))
        self.assertNotEqual(h1, ra.battery_id_of(t2))

    def test_03_build_battery_full_zero_subsample_and_oversized_cap(self) -> None:
        universe = {"tasks": _sample_tasks()}
        with mock.patch.object(ra, "build_universe", return_value=universe):
            full = ra.build_battery(None)
            zero = ra.build_battery(0)
            five = ra.build_battery(5)
            over = ra.build_battery(999)

        # 4 classes * (5 - 3 pool) = 8 singles + (8 - 6 pool) = 2 mixed = 10 eval tasks
        self.assertEqual(len(full), 10)
        self.assertEqual(zero, [])
        self.assertEqual(len(over), len(full))
        # Stratified round-robin size=5 takes 1 from each bucket first.
        self.assertEqual(len(five), 5)
        self.assertEqual({ra.bucket_of(t) for t in five}, set(ra.BUCKETS))

    def test_04_load_catalog_empty_and_equivalent_discovery_vs_materialized_shapes(self) -> None:
        ek, ec, ed, edesc = ra.load_catalog("empty")
        self.assertEqual((ek, ec, edesc), ((), (), "empty catalog"))
        self.assertEqual(len(ed), 64)

        mat_path = self.base / "mat_catalog.json"
        mat_path.write_text(
            json.dumps(
                {
                    "classes": {
                        "bounds_off_by_one": {
                            "operators": ["('swap', 1)"],
                            "chains": ["(('swap', 1), ('add', 2))"],
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        k1, c1, d1, desc1 = ra.load_catalog("v4")
        k2, c2, d2, _ = ra.load_catalog(str(mat_path))
        self.assertEqual((k1, c1, d1), (k2, c2, d2))
        self.assertEqual(desc1, "v4 (operator_discovery_v4.json)")

    def test_05_load_catalog_rejects_bad_shape_and_non_tuple_literals(self) -> None:
        bad_shape = self.base / "bad_shape.json"
        bad_shape.write_text(json.dumps({"other": 1}), encoding="utf-8")
        with self.assertRaises(ValueError):
            ra.load_catalog(str(bad_shape))

        bad_op = self.base / "bad_op.json"
        bad_op.write_text(json.dumps({"classes": {"c": {"operators": ["[1, 2]"]}}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            ra.load_catalog(str(bad_op))

        bad_chain = self.base / "bad_chain.json"
        bad_chain.write_text(json.dumps({"classes": {"c": {"chains": ["'not_tuple'"]}}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            ra.load_catalog(str(bad_chain))

        with self.assertRaises(FileNotFoundError):
            ra.load_catalog(str(self.base / "missing.json"))

    def test_06_run_pass_counts_solved_and_handles_timeout_gracefully(self) -> None:
        battery = [
            {"task_id": "t_ok", "defects": ["wall_char_x"], "holdout_cases": [(1,), (2,)], "holdout_truth": [1, 2]},
            {"task_id": "t_to", "defects": ["bounds_off_by_one"], "holdout_cases": [(1,)], "holdout_truth": [1]},
        ]

        def fake_passes(code: str, cases: list, truth: list) -> int:
            if code == "timeout_code":
                raise ra._ScoreTimeout()
            return len(cases)

        def fake_solve(task: dict, *_args) -> str:
            return "timeout_code" if task["task_id"] == "t_to" else "ok_code"

        with mock.patch.object(ra, "solve_task", side_effect=fake_solve), \
                mock.patch.object(ra.GRID_ADAPTER, "passes", side_effect=fake_passes):
            res = ra.run_pass(battery, (), ())

        self.assertEqual(res["tasks"], 2)
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["per_class"]["wall_char_x"]["solved_ids"], ["t_ok"])
        self.assertEqual(res["per_class"]["bounds_off_by_one"]["solved"], 0)

    def test_07_compare_detects_no_regression_regression_and_improvement(self) -> None:
        battery = [{"task_id": "t1"}]
        base = {"per_class": {b: {"tasks": 1, "solved": 1 if b == "wall_char_x" else 0} for b in ra.BUCKETS}, "total": 1, "tasks": 1}
        cand_same = json.loads(json.dumps(base))
        res_same = ra.compare(battery, "v4", "v4", base, cand_same, {}, {}, True, 0.25)
        self.assertEqual(res_same["verdict"], "NO_REGRESSION")
        self.assertEqual(res_same["regressions"], [])

        cand_reg = json.loads(json.dumps(base))
        cand_reg["per_class"]["wall_char_x"]["solved"] = 0
        cand_reg["per_class"]["mixed"]["solved"] = 1
        res_reg = ra.compare(battery, "v4", "empty", base, cand_reg, {}, {}, False, 1.0)
        self.assertEqual(res_reg["verdict"], "REGRESSION_FOUND")
        self.assertEqual(res_reg["regressions"], ["wall_char_x"])
        self.assertEqual(res_reg["improvements"], ["mixed"])

    def test_08_run_anchor_dedupes_identical_catalogs_and_writes_atomic_json(self) -> None:
        battery = [
            {"task_id": "t1", "defects": ["bounds_off_by_one"], "holdout_cases": [(1,)], "holdout_truth": [1]}
        ]
        with mock.patch.object(ra, "run_pass", return_value={
            "per_class": {b: {"tasks": 1 if b == "bounds_off_by_one" else 0, "solved": 1 if b == "bounds_off_by_one" else 0, "solved_ids": ["t1"] if b == "bounds_off_by_one" else []} for b in ra.BUCKETS},
            "total": 1, "tasks": 1,
        }) as rp:
            out_dedup, dest = ra.run_anchor(battery, "v4", "v4", "dedup_lbl", dedupe=True)
            self.assertTrue(out_dedup["deduped"])
            self.assertEqual(rp.call_count, 1)
            self.assertTrue(dest.is_file())

            out_nodedup, _ = ra.run_anchor(battery, "v4", "v4", "nodedup_lbl", dedupe=False)
            self.assertFalse(out_nodedup["deduped"])
            self.assertEqual(rp.call_count, 3)

    def test_09_run_anchor_respects_inoculate_registry_via_temp_harness(self) -> None:
        (self.base / "abc_v3_run.py").write_text(
            "def split_universe(tasks):\n"
            "    return {'control': tasks}\n"
            "def _run_with_wall(fn, wall):\n"
            "    return fn(), False\n",
            encoding="utf-8",
        )
        reg_dir = self.base / "reg"
        reg_dir.mkdir()
        reg_json = reg_dir / "distractor_registry.json"
        reg_json.write_text(json.dumps({"items": ["x"]}), encoding="utf-8")
        (reg_dir / "distractor_inoculation.py").write_text(
            "import json\nfrom pathlib import Path\n"
            "def load_registry(p):\n"
            "    return json.loads(Path(p).read_text(encoding='utf-8'))\n"
            "def run_battery(*, catalog_keys, solve, registry):\n"
            "    return {'overall': 'PASS' if solve('bounds_off_by_one_0', catalog_keys) else 'FAIL'}\n",
            encoding="utf-8",
        )
        battery = [{"task_id": "bounds_off_by_one_0", "defects": ["bounds_off_by_one"], "holdout_cases": [(1,)], "holdout_truth": [1]}]
        fake_universe = {"tasks": _sample_tasks()}
        with mock.patch.dict(sys.modules), \
                mock.patch("ace_operational.grid_generalization.build_universe", return_value=fake_universe), \
                mock.patch.object(ra, "solve_task", return_value="ok"), \
                mock.patch.object(ra.GRID_ADAPTER, "passes", return_value=1):
            direct = ra.run_inoculation([("swap", 1)], reg_json)
            self.assertEqual(direct["overall"], "PASS")
            res, _ = ra.run_anchor(battery, "v4", "v4", "inoc", inoculate_registry=str(reg_json))
        self.assertEqual(res["inoculation"]["overall"], "PASS")

    def test_10_self_test_passes_with_mocked_solver_and_fails_on_all_zero(self) -> None:
        battery = [{"task_id": "t1", "defects": ["wall_char_x"], "holdout_cases": [(1,)], "holdout_truth": [1]}]
        with mock.patch.object(ra, "build_battery", return_value=battery), \
                mock.patch.object(ra, "solve_task", side_effect=lambda t, g, keys, chains: "win" if keys else "lose"), \
                mock.patch.object(ra.GRID_ADAPTER, "passes", side_effect=lambda code, cases, truth: len(cases) if code == "win" else 0), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ra.self_test(1), 0)

        with mock.patch.object(ra, "build_battery", return_value=battery), \
                mock.patch.object(ra, "solve_task", return_value="lose"), \
                mock.patch.object(ra.GRID_ADAPTER, "passes", return_value=0), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ra.self_test(1), 1)

    def test_11_main_rejects_oversized_smoke_battery_and_missing_registry(self) -> None:
        with mock.patch.object(sys, "argv", ["regression_anchor.py", "--battery-size", "25"]), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                ra.main()
            self.assertEqual(cm.exception.code, 2)

        with mock.patch.object(ra, "build_battery", return_value=[]), \
                mock.patch.object(sys, "argv", ["regression_anchor.py", "--inoculate"]), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm2:
                ra.main()
            self.assertEqual(cm2.exception.code, 2)

    def test_12_main_cli_executes_anchor_and_prints_summary(self) -> None:
        battery = [{"task_id": "t1", "defects": ["wall_char_x"], "holdout_cases": [(1,)], "holdout_truth": [1]}]
        out_buf = io.StringIO()
        with mock.patch.object(ra, "build_battery", return_value=battery), \
                mock.patch.object(ra, "solve_task", return_value="win"), \
                mock.patch.object(ra.GRID_ADAPTER, "passes", return_value=1), \
                mock.patch.object(sys, "argv", ["regression_anchor.py", "--baseline", "v4", "--candidate", "v4", "--label", "cli_ok"]), \
                contextlib.redirect_stdout(out_buf):
            rc = ra.main()
        self.assertEqual(rc, 0)
        self.assertIn("verdict=NO_REGRESSION", out_buf.getvalue())
        self.assertTrue((self.ev / "regression_anchor_cli_ok.json").is_file())

    def test_13_main_self_test_flag_dispatches_self_test(self) -> None:
        with mock.patch.object(ra, "self_test", return_value=0) as st, \
                mock.patch.object(sys, "argv", ["regression_anchor.py", "--self-test", "--battery-size", "3"]):
            rc = ra.main()
        self.assertEqual(rc, 0)
        st.assert_called_once_with(3)

    def test_14_load_catalog_rejects_corrupt_json(self) -> None:
        bad = self.base / "corrupt.json"
        bad.write_text("{corrupt", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            ra.load_catalog(str(bad))

    def test_15_run_pass_handles_empty_battery(self) -> None:
        res = ra.run_pass([], (), ())
        self.assertEqual(res["tasks"], 0)
        self.assertEqual(res["total"], 0)

    # Dugaan bug minor E3 (EVIDENCE tidak dibuat otomatis sebelum _atomic_write):
    # `run_anchor()` memanggil `_atomic_write(dest, ...)` tanpa `dest.parent.mkdir(parents=True, exist_ok=True)`.
    @unittest.expectedFailure
    def test_16_bug_run_anchor_fails_if_evidence_dir_missing(self) -> None:
        missing_ev = self.base / "nonexistent_ev"
        with mock.patch.object(ra, "EVIDENCE", missing_ev):
            ra.run_anchor([], "empty", "empty", "new_dir")


if __name__ == "__main__":
    unittest.main()
