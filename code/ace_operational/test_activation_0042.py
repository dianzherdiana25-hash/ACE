"""Tes integrasi paket EVO 0042 (AG111–AG119: Kurikulum & Praktik).

Berjalan aman di baseline (`main`) dengan menguji `step_practice` serta integritas
`curriculum_wave2`, dan membuka suite penuh end-to-end 9 langkah EVO 0042
saat seluruh branch AG111–AG119 digabungkan.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ace_operational import curriculum_wave2, leap_wiring
from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.store import OperationalStore

_EVO0042_STEPS = (
    "step_mastery_board",
    "step_practice",
    "step_occurrence_outlier_scan",
    "step_practice_task_lint",
    "step_curriculum_ab_report",
    "step_curriculum_wave2",
    "step_director_actions_wave2",
)
_ALL_WIRED = all(hasattr(leap_wiring, name) for name in _EVO0042_STEPS)


class Activation0042BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0042-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.store.record_gap(
            source_task_id="evo0042-gap-1",
            error_type="DYNAMIC_TECH_PRACTICE_FAILED",
            missing_skill_or_tool="dedup_csv",
            description_id="latihan deduplikasi baris csv",
            reproduction_ref="probe:evo0042",
        )

    def test_baseline_practice_schedule_and_wave2_catalog(self) -> None:
        self.assertEqual(len(curriculum_wave2.LANGUAGE_WAVE2), 6)
        self.assertEqual(len(curriculum_wave2.TECHNICAL_WAVE2), 6)
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 10
        out = leap_wiring.step_practice(eng)
        self.assertEqual(out["status"], "ok")
        self.assertTrue((self.ws / "practice_schedule.json").is_file())


class Activation0042OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0042-overlay-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.store.record_gap(
            source_task_id="evo0042-ov-gap",
            error_type="DYNAMIC_TECH_PRACTICE_FAILED",
            missing_skill_or_tool="dedup_csv",
            description_id="latihan deduplikasi baris csv",
            reproduction_ref="probe:evo0042:ov",
        )
        gid = self.store.list_gaps(status="OPEN")[0]["gap_id"]
        self.store._conn.execute(
            "UPDATE gaps SET occurrence_count = 200 WHERE gap_id = ?", (gid,)
        )
        self.store._conn.commit()
        self.gid = gid
        self.prac = self.store.create_task(
            kind="learning_practice",
            title_id="Praktik Wave2 Dedup",
            user_request="uji praktik wave2",
            normalized_goal="uji praktik wave2",
            model_backend="leap_wiring/failure_taskgen",
            priority=5,
            checkpoint={"gap_id": gid, "evidence_refs": [gid]},
            hold_for_review=False,
        )
        valid_lint = {
            "id": "lint-dedup-ok",
            "family": "dedup_csv",
            "prompt": "Tulis `dedup_csv(rows)` menjaga urutan awal baris CSV.",
            "reference_solution": "def dedup_csv(rows):\n    return list(dict.fromkeys(rows))\n",
            "evaluator_code": (
                "def evaluate(solution, test_cases=None):\n"
                "    ns = {}\n"
                "    exec(solution, ns, ns)\n"
                "    fn = ns.get('dedup_csv')\n"
                "    if not callable(fn):\n"
                "        return {'passed': False}\n"
                "    for args, expected in test_cases:\n"
                "        if fn(*args) != expected:\n"
                "            return {'passed': False}\n"
                "    return {'passed': True, 'score': 1.0}\n"
            ),
            "test_cases": [([["a,1", "b,2", "a,1"]], ["a,1", "b,2"])],
        }
        (self.ws / "practice_tasks.jsonl").write_text(
            json.dumps(valid_lint) + "\n", encoding="utf-8"
        )

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh branch AG111–AG119 EVO 0042 digabungkan")
    def test_full_evo0042_pipeline_at_cycle_200(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 199
        with patch.dict(
            os.environ,
            {"ACE_LEAPS": "1", "ACE_DIRECTOR_EXEC_A2": "0", "ACE_WAVE2_PRACTICE": "0"},
            clear=False,
        ):
            summary = eng.execute_cycle()

        self.assertEqual(summary["cycle"], 200)
        leaps = summary.get("leaps", {})
        for key in (
            "mastery_board",
            "practice",
            "occurrence_outlier_scan",
            "practice_task_lint",
            "curriculum_ab_report",
            "curriculum_wave2",
        ):
            self.assertIn(key, leaps, f"Step {key} hilang di summary['leaps']")
            self.assertEqual(leaps[key]["status"], "ok", f"Step {key}: {leaps[key]}")

        self.assertEqual(leaps["director_actions_wave2"]["status"], "gated_off")
        self.assertGreaterEqual(leaps["occurrence_outlier_scan"]["outlier_count"], 1)
        self.assertIn("gap_patterns", leaps["practice"])
        self.assertIn("gap_root_causes", leaps["practice"])
        self.assertIn("failure_agenda", leaps["practice"])

        for art in (
            "mastery_board.json",
            "mastery_board.md",
            "gap_patterns.json",
            "gap_root_causes.json",
            "gap_outliers.jsonl",
            "failure_agenda.jsonl",
            "practice_lint.jsonl",
            "curriculum_ab.json",
            "curriculum_wave2_state.json",
        ):
            self.assertTrue((self.ws / art).is_file(), f"Artefak {art} tidak terbuat")

        # Uji aktivasi eksekutor Kelas A Wave-2 + undo dengan tugas praktik baru
        self.store.create_task(
            kind="learning_practice",
            title_id="Praktik Wave2 Siap Eksekusi",
            user_request="uji eksekutor wave2",
            normalized_goal="uji eksekutor wave2",
            model_backend="leap_wiring/failure_taskgen",
            priority=5,
            checkpoint={"gap_id": self.gid, "evidence_refs": [self.gid]},
            hold_for_review=False,
        )
        with patch.dict(os.environ, {"ACE_DIRECTOR_EXEC_A2": "1"}, clear=False):
            exec_res = leap_wiring.step_director_actions_wave2(eng)
        self.assertEqual(exec_res["status"], "ok")
        self.assertTrue((self.ws / "director_exec_a2_receipts.jsonl").is_file())
        last_rcpt = json.loads(
            (self.ws / "director_exec_a2_receipts.jsonl").read_text(encoding="utf-8").strip().splitlines()[-1]
        )
        undo_res = leap_wiring.undo_director_wave2_receipt(eng, last_rcpt)
        self.assertEqual(undo_res["status"], "ok")


if __name__ == "__main__":
    unittest.main()
