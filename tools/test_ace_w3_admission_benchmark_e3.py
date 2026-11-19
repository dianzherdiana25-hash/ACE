"""Tes tepi luring untuk tools/ace_w3_admission_benchmark.py (E3 #4, TESTS ONLY)."""

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

from tools import ace_w3_admission_benchmark as w3  # noqa: E402


class _FakeProg:
    def __init__(self, predict_fn, data_val):
        self._predict = predict_fn
        self._data = data_val

    def predict(self, word):
        return self._predict(word)

    def data(self):
        return self._data


class TestAceW3AdmissionBenchmarkE3(unittest.TestCase):
    """Uji unit tepi untuk 5 simbol publik ace_w3_admission_benchmark."""

    def test_01_digest_canonicalizes_key_order_and_produces_sha256(self):
        d1 = w3.digest({"b": [1, 2], "a": {"z": True, "m": None}})
        d2 = w3.digest({"a": {"m": None, "z": True}, "b": [1, 2]})
        self.assertEqual(d1, d2)
        self.assertEqual(len(d1), 64)

    def test_02_digest_handles_primitives_and_rejects_unserializable(self):
        self.assertNotEqual(w3.digest({}), w3.digest([]))
        self.assertNotEqual(w3.digest(False), w3.digest(0))
        with self.assertRaises(TypeError):
            w3.digest({1, 2})

    def test_03_legacy_status_thresholds_zero_within_max_and_rejected(self):
        fn = lambda w: w.startswith("a")
        train = [("a", True), ("b", False), ("c", True), ("d", True)]  # 2 errors
        self.assertEqual(w3.legacy_status(fn, train[:2]), "ADMITTED")
        self.assertEqual(w3.legacy_status(fn, train, max_errors=2), "ADMITTED_WITH_ERRORS")
        self.assertEqual(w3.legacy_status(fn, train, max_errors=1), "REJECTED")

    def test_04_legacy_status_empty_train_and_negative_max_errors(self):
        self.assertEqual(w3.legacy_status(lambda w: False, []), "ADMITTED")
        self.assertEqual(w3.legacy_status(lambda w: False, [("x", True)], max_errors=-1), "REJECTED")
        self.assertEqual(w3.legacy_status(lambda w: False, [("x", False)], max_errors=-1), "ADMITTED")

    def test_05_legacy_status_propagates_predictor_exception(self):
        def broken(_w):
            raise RuntimeError("predictor crash")

        with self.assertRaisesRegex(RuntimeError, "predictor crash"):
            w3.legacy_status(broken, [("a", True)])

    def test_06_score_none_program_abstains_all_and_empty_rows(self):
        self.assertEqual(
            w3.score(None, [("a", True), ("b", False)]),
            {"correct": 0, "total": 2, "abstained": 2, "predictions": []},
        )
        self.assertEqual(
            w3.score(None, []),
            {"correct": 0, "total": 0, "abstained": 0, "predictions": []},
        )

    def test_07_score_matches_replay_and_tallies_accuracy(self):
        prog = _FakeProg(lambda w: w.startswith("a"), {"kind": "starts_a"})
        rows = [("a", True), ("ab", False), ("b", False), ("", True)]  # hits: a, b (2/4)
        with mock.patch.object(w3.c, "replay", side_effect=lambda _data, word: word.startswith("a")):
            res = w3.score(prog, rows)
        self.assertEqual(res["correct"], 2)
        self.assertEqual(res["total"], 4)
        self.assertEqual(res["abstained"], 0)
        self.assertEqual(res["predictions"], [True, True, False, False])

    def test_08_score_raises_on_serialized_replay_mismatch(self):
        prog = _FakeProg(lambda _w: True, {"kind": "const"})
        with mock.patch.object(w3.c, "replay", return_value=False):
            with self.assertRaisesRegex(ValueError, "serialized replay mismatch"):
                w3.score(prog, [("a", True)])

    def test_09_score_empty_rows_with_valid_program(self):
        prog = _FakeProg(lambda _w: False, {})
        self.assertEqual(
            w3.score(prog, []),
            {"correct": 0, "total": 0, "abstained": 0, "predictions": []},
        )

    def test_10_run_single_cell_executes_adversarial_and_gates_offline(self):
        seed0 = w3.c.SEEDS[:1]
        with (
            mock.patch.object(w3.c, "SEEDS", seed0),
            mock.patch.object(w3.c, "TASKS", ("starts",)),
        ):
            report, profile = w3.run()
        self.assertEqual(report["schema"], "ace.w3-admission.public.v1")
        self.assertEqual(len(report["cells"]), 1)
        self.assertEqual(len(report["adversarial"]), 6)  # 3 families x 2 candidates
        self.assertTrue(report["gates"]["H1_all_validation_failures_rejected"])
        self.assertTrue(report["gates"]["H2_all_positive_controls_admitted"])
        self.assertTrue(report["gates"]["H3_starts_all_seeds_admitted"])
        self.assertEqual(report["release_gate"], "BLOCK_RELEASE")
        self.assertEqual(report["external_ai_calls"], 0)
        self.assertFalse(report["candidate_deployed"])
        self.assertGreater(profile["process_peak_rss_kib"], 0)
        self.assertEqual(len(profile["tasks"]), 1)

    def test_11_run_rejects_fit_not_called_exactly_once(self):
        with (
            mock.patch.object(w3.c, "SEEDS", w3.c.SEEDS[:1]),
            mock.patch.object(w3.c, "TASKS", ("starts",)),
            mock.patch.object(w3, "fit_with_admission", return_value=(None, {"status": "ABSTAIN"})),
        ):
            with self.assertRaisesRegex(ValueError, "fit was not called exactly once"):
                w3.run()

    def test_12_run_enforces_900s_budget_timeout(self):
        with (
            mock.patch.object(w3.c, "SEEDS", w3.c.SEEDS[:1]),
            mock.patch.object(w3.c, "TASKS", ("starts",)),
            mock.patch.object(w3.time, "perf_counter", side_effect=[0.0, 900.1]),
        ):
            with self.assertRaisesRegex(TimeoutError, "900-second study budget exceeded"):
                w3.run()

    def test_13_main_writes_nested_output_and_returns_zero_when_gates_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "nested" / "report.json"
            prof_path = Path(tmp) / "nested" / "profile.json"
            fake_report = {
                "summary": {"current": {"correct": 1, "total": 1}},
                "gates": {"H1": True, "H2": True},
                "legacy_observed_false_admission_tasks": 1,
                "current_observed_false_admission_tasks": 0,
            }
            fake_profile = {"cpu_seconds": 0.01, "wall_seconds": 0.02, "tasks": [{"id": 1}]}
            buf = io.StringIO()
            with (
                mock.patch.object(w3, "run", return_value=(fake_report, fake_profile)),
                mock.patch.object(sys, "argv", ["w3", "--output", str(out_path), "--profile", str(prof_path)]),
                redirect_stdout(buf),
            ):
                rc = w3.main()
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out_path.read_text()), fake_report)
            self.assertEqual(json.loads(prof_path.read_text()), fake_profile)
            printed = json.loads(buf.getvalue())
            self.assertEqual(printed["current_false_admission"], 0)
            self.assertNotIn("tasks", printed["profile"])

    def test_14_main_returns_one_when_any_gate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "r.json"
            prof_path = Path(tmp) / "p.json"
            fake_report = {
                "summary": {},
                "gates": {"H1": True, "H2": False},
                "legacy_observed_false_admission_tasks": 0,
                "current_observed_false_admission_tasks": 0,
            }
            fake_profile = {"cpu_seconds": 0.0, "wall_seconds": 0.0, "tasks": []}
            with (
                mock.patch.object(w3, "run", return_value=(fake_report, fake_profile)),
                mock.patch.object(sys, "argv", ["w3", "--output", str(out_path), "--profile", str(prof_path)]),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(w3.main(), 1)

    def test_15_main_rejects_non_finite_nan_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "r.json"
            prof_path = Path(tmp) / "p.json"
            fake_report = {
                "summary": {"bad": float("nan")},
                "gates": {"H1": True},
                "legacy_observed_false_admission_tasks": 0,
                "current_observed_false_admission_tasks": 0,
            }
            fake_profile = {"cpu_seconds": 0.0, "wall_seconds": 0.0, "tasks": []}
            with (
                mock.patch.object(w3, "run", return_value=(fake_report, fake_profile)),
                mock.patch.object(sys, "argv", ["w3", "--output", str(out_path), "--profile", str(prof_path)]),
            ):
                with self.assertRaises(ValueError):
                    w3.main()

    def test_16_main_requires_output_and_profile_args(self):
        with (
            mock.patch.object(sys, "argv", ["w3", "--output", "/tmp/only_out.json"]),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as ctx:
                w3.main()
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
