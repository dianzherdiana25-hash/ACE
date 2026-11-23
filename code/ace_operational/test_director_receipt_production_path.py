"""Regresi receipt director lewat JALUR PRODUKSI nyata (bukan FakeStore).

Bug yang ditambatkan: eksekutor Kelas A (director_execution) menuntut gap
yang masih OPEN dengan capability KNOWN_AND_TESTED terikat fingerprint
gap itu, tetapi jalur belajar (AutonomyOrchestrator.learn_skill_and_
resume_parent) menutup gap menjadi RESOLVED sebelum menaikkan capability
— konjungsinya tak terjangkau, jadi file receipt tidak pernah lahir.

Tes ini menjalankan rantai produksi apa adanya di atas OperationalStore
asli: parent task -> report_gap -> proposal director persis seperti
execute_director_step membuatnya -> learn_skill_and_resume_parent nyata
-> run_execution_step. Sesudah perbaikan, jalur belajar menunda penutupan
bila ada proposal WAITING yang mengutip gap itu, dan CloseGap director
yang menutupnya — dengan receipt started+completed tertulis.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from ace_operational import director_execution as dx
from ace_operational.autonomy_loop import AutonomyOrchestrator
from ace_operational.store import OperationalStore


class DirectorReceiptProductionPath(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        root = Path(stack.enter_context(TemporaryDirectory()))
        self.store = stack.enter_context(OperationalStore(root))
        self.orch = AutonomyOrchestrator(self.store)

    def _parent_and_gap(self):
        parent = self.store.create_task(
            kind="user_task",
            title_id="Rekap pengeluaran bulanan",
            user_request="Kelompokkan dan jumlahkan pengeluaran per kategori",
            normalized_goal="Agregasi pengeluaran per kategori terverifikasi",
        )
        res = self.orch.report_gap(
            source_task_id=parent["task_id"],
            error_type="missing_capability",
            missing_skill_or_tool="pengelompokan JSON/CSV",
            description_id="gap_rekap_kelompok",
        )
        gap = res["gap"]
        self.assertEqual(gap["status"], "OPEN")
        return parent, gap

    def _director_proposal(self, gap_id):
        """Proposal persis seperti execute_director_step menyimpannya."""
        proposal = {
            "title": "Tutup gap rekap kelompok",
            "rationale": "Bukti belajar terverifikasi akan tersedia untuk gap ini.",
            "category": "capability",
            "score": 5.0,
            "based_on": [gap_id],
        }
        task = self.store.create_task(
            kind="director_proposal",
            title_id=proposal["title"],
            user_request=proposal["rationale"],
            normalized_goal=proposal["title"],
            model_backend="fixture/test-model",
            priority=proposal["score"],
            checkpoint={"stage": "director_review", "cycle": 1,
                        "brain_of_origin": "fixture/test-model",
                        "proposal": proposal},
            hold_for_review=True,
        )
        self.assertEqual(task["status"], "WAITING_FOR_DEPENDENCY")
        return task

    def _gap(self, gap_id):
        return next(g for g in self.store.list_gaps() if g["gap_id"] == gap_id)

    def _capability(self, gap):
        cap_id = f"cap_{gap['fingerprint'][:10]}"
        return next(c for c in self.store.list_frontier()
                    if c["capability_id"] == cap_id)

    def test_waiting_proposal_defers_closure_and_director_receipts(self):
        _parent, gap = self._parent_and_gap()
        proposal_task = self._director_proposal(gap["gap_id"])

        self.orch.learn_skill_and_resume_parent(gap_id=gap["gap_id"])

        # Jalur belajar TIDAK menutup gap: proposal WAITING mengutipnya,
        # jadi gap kembali OPEN (bukan LEARNING_IN_PROGRESS, bukan
        # RESOLVED) sementara buktinya sudah KNOWN_AND_TESTED.
        after_learn = self._gap(gap["gap_id"])
        self.assertEqual(after_learn["status"], "OPEN")
        self.assertTrue(after_learn["linked_learning_task_id"])
        cap = self._capability(after_learn)
        self.assertEqual(cap["status"], "KNOWN_AND_TESTED")
        self.assertTrue(cap["evidence_ref"])

        # Executor membaca flag dari os.environ (bukan parameter
        # environ run_execution_step) — persis seperti engine live.
        with mock.patch.dict(os.environ, {"ACE_DIRECTOR_EXEC_A": "1"}):
            result = dx.run_execution_step(
                self.store, self.store.workspace,
                environ={"ACE_DIRECTOR_EXEC_A": "1"})
        self.assertEqual(result["executed"], 1)
        self.assertEqual(result["considered"], 1)

        receipt_path = Path(self.store.workspace) / dx.RECEIPT_NAME
        records = [json.loads(line) for line in
                   receipt_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["status"] for r in records],
                         ["started", "completed"])
        self.assertEqual(records[0]["task_id"], proposal_task["task_id"])

        # CloseGap director yang menutup gap; proposal selesai dengan
        # receipt_status tercatat di checkpoint-nya.
        self.assertEqual(self._gap(gap["gap_id"])["status"], "RESOLVED")
        done = self.store.get_task(proposal_task["task_id"])
        self.assertEqual(done["status"], "COMPLETED")
        self.assertEqual(
            done["checkpoint"]["director_execution"]["receipt_status"],
            "completed")

    def test_without_waiting_proposal_learning_closes_gap_as_before(self):
        _parent, gap = self._parent_and_gap()

        self.orch.learn_skill_and_resume_parent(gap_id=gap["gap_id"])

        after_learn = self._gap(gap["gap_id"])
        self.assertEqual(after_learn["status"], "RESOLVED")
        cap = self._capability(after_learn)
        self.assertEqual(cap["status"], "KNOWN_AND_TESTED")
        self.assertFalse(
            (Path(self.store.workspace) / dx.RECEIPT_NAME).exists())

    def test_skip_reasons_aggregate_no_verified_evidence(self):
        _parent, gap = self._parent_and_gap()
        self._director_proposal(gap["gap_id"])

        result = dx.run_execution_step(
            self.store, self.store.workspace,
            environ={"ACE_DIRECTOR_EXEC_A": "1"})
        self.assertEqual(result["executed"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["skip_reasons"], {
            "already_receipted": 0, "multi_gap": 0,
            "no_verified_evidence": 1, "anchor_failed": 0})


if __name__ == "__main__":
    unittest.main()
