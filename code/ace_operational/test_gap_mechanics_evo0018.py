"""Tes mekanisme gap EVO 0018 M2: hitung kegagalan berbeda,
buka-ulang sesudah resolve, dan resolve-on-pass di engine."""
import tempfile
import unittest
from pathlib import Path

from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.store import OperationalStore


def _record(store: OperationalStore, *, task: str = "t1", repro: str = "/tmp/x.py"):
    return store.record_gap(
        source_task_id=task,
        error_type="LANGUAGE_VERIFICATION_FAILED",
        missing_skill_or_tool="skill_uji",
        description_id="Verifikasi gagal pada Uji: boom",
        reproduction_ref=repro,
        resolution_strategy="self_repair",
    )[0]


class GapCountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = OperationalStore(workspace=Path(self._tmp.name))

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_reobservation_same_repro_does_not_inflate(self) -> None:
        _record(self.store)
        _record(self.store, task="t2")
        gap = _record(self.store, task="t3")
        self.assertEqual(gap["occurrence_count"], 1)

    def test_distinct_repro_counts(self) -> None:
        _record(self.store)
        gap = _record(self.store, repro="/tmp/y.py")
        self.assertEqual(gap["occurrence_count"], 2)

    def test_resolved_gap_reopens_at_one(self) -> None:
        gap = _record(self.store)
        self.store.update_gap(gap["gap_id"], status="RESOLVED")
        again = _record(self.store, repro="/tmp/z.py")
        self.assertEqual(again["status"], "OPEN")
        self.assertEqual(again["occurrence_count"], 1)


class ResolveOnPassTests(unittest.TestCase):
    def test_curriculum_pass_resolves_matching_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            engine = ContinuousAutonomousEngine(workspace=ws, tick_interval_seconds=0.2)
            gap = engine.store.record_gap(
                source_task_id="t0",
                error_type="LANGUAGE_VERIFICATION_FAILED",
                missing_skill_or_tool="skill_uji",
                description_id="Verifikasi gagal pada Uji: boom",
                reproduction_ref=str(ws / "uji.py"),
                resolution_strategy="self_repair",
            )[0]
            item = {
                "skill_name": "skill_uji",
                "title": "Uji",
                "goal": "goal uji",
                "target_file": "uji.py",
                "code": "print('UJI_OK')\n",
                "verification_str": "UJI_OK",
                "domain": "bahasa",
                "preconditions": [],
                "procedure_steps": ["jalankan"],
                "boundary_limitations": [],
                "capability_id": "cap_uji",
                "capability_name": "Kemampuan Uji",
            }
            result = engine._run_verified_curriculum_item(
                item, learning_kind="language", category="language",
                verified_by="test", task_prefix="Uji")
            self.assertTrue(result["passed"])
            closed = engine.store.get_gap(gap["gap_id"]) \
                if hasattr(engine.store, "get_gap") else None
            if closed is None:
                closed = [g for g in engine.store.list_gaps()
                          if g["gap_id"] == gap["gap_id"]][0]
            self.assertEqual(closed["status"], "RESOLVED")
            self.assertTrue(closed["linked_learning_task_id"])
            engine.store.close()


if __name__ == "__main__":
    unittest.main()
