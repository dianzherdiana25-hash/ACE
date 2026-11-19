"""EVO 0009 engine write-back seam: the autonomous engine's own
verified curriculum passes reach cognitive memory.

Diagnosis (2026-11-19): the write path was wired at ratification
points and at the skills expander's receipt issuance (milestone
5), but ContinuousAutonomousEngine._run_verified_curriculum_item
never wrote — the live store held only the two operator seed
records while the engine accumulated verified receipts. These
tests prove the seam on scratch stores only:

- a passed curriculum item writes exactly one skill_verified
  record (procedural, 0.90, evidence-anchored on its receipt),
- a failed item writes nothing,
- a second distinct pass writes a second record,
- the hash chain audits clean after the writes.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.store import OperationalStore


def _item(skill_name: str, *, passes: bool) -> dict:
    code = (
        'print("SEAM_VERIFIED_OK")\n' if passes
        else 'print("nothing the verifier wants")\n'
    )
    return {
        "skill_name": skill_name,
        "domain": "seam_test",
        "title": f"Seam Test {skill_name}",
        "goal": "Prove the engine write-back seam",
        "target_file": f"projects/learning_lab/seam/{skill_name}.py",
        "verification_str": "SEAM_VERIFIED_OK",
        "preconditions": ["none"],
        "procedure_steps": ["run the module", "check stdout"],
        "boundary_limitations": ["test item only"],
        "capability_id": f"cap_{skill_name}",
        "capability_name": f"Seam {skill_name}",
        "code": code,
    }


def _records(root) -> list[dict]:
    return list(CognitiveMemory(root)._records.values())


def _by_class(root, cls: str) -> list[dict]:
    return [r for r in _records(root)
            if r["content"].get("class") == cls]


class EngineWritebackSeamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ace-seam-")
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.engine = ContinuousAutonomousEngine(
            store=self.store, workspace=self.ws)
        self.memory_root = self.ws / "cognitive_memory"

    def _run(self, item: dict) -> dict:
        return self.engine._run_verified_curriculum_item(
            item,
            learning_kind="technical",
            category="engineering",
            verified_by="engine_seam_test",
            task_prefix="SEAM",
        )

    def test_passed_item_writes_one_skill_verified_record(self) -> None:
        result = self._run(_item("seam_pass_one", passes=True))
        self.assertTrue(result["passed"])
        self.assertIsNotNone(result["writeback_id"])

        # The engine seeds the store with the two operator seed
        # records on construction; the seam adds exactly one more.
        self.assertEqual(len(_records(self.memory_root)), 3)
        records = _by_class(self.memory_root, "skill_verified")
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["id"], result["writeback_id"])
        self.assertEqual(record["kind"], "procedural")
        self.assertEqual(record["confidence"], 0.90)
        self.assertEqual(record["source"]["kind"], "evidence")
        self.assertTrue(record["source"]["ref"])
        self.assertEqual(record["content"]["class"], "skill_verified")
        self.assertEqual(record["content"]["skill_name"], "seam_pass_one")
        self.assertEqual(record["content"]["receipt_id"], result["receipt"])

        audit = CognitiveMemory(self.memory_root).audit()
        self.assertTrue(audit["chain_ok"])
        self.assertEqual(audit["anchored_evidence"], 1)

    def test_failed_item_writes_nothing(self) -> None:
        result = self._run(_item("seam_fail_one", passes=False))
        self.assertFalse(result["passed"])
        self.assertEqual(_by_class(self.memory_root, "skill_verified"), [])

    def test_second_distinct_pass_writes_second_record(self) -> None:
        first = self._run(_item("seam_pass_a", passes=True))
        second = self._run(_item("seam_pass_b", passes=True))
        self.assertNotEqual(first["writeback_id"], second["writeback_id"])
        records = _by_class(self.memory_root, "skill_verified")
        self.assertEqual(len(records), 2)
        self.assertTrue(
            CognitiveMemory(self.memory_root).audit()["chain_ok"])


if __name__ == "__main__":
    unittest.main()
