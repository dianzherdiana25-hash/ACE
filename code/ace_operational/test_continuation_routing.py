"""Continuation-cycle routing determination (owner direction, 2026-11-24).

A task that carries a work order is delegated to an external agent: the
agent is ACE's brain and its worker. The autonomous continuation cycle
must NOT execute such a task itself — substituting a template project
mints receipts that certify work the task never asked for. This was
proven live on task_1795516343713_597f18e1, whose VERIFIED verdict
rested on expense-tracker template receipts while the real bugfix was
done by the agent through the work order.

These tests prove, on scratch stores only:
- a delegated task (has a work order) is routed, stays QUEUED, and
  gains no receipts from the continuation cycle,
- an undelegated task still executes through the coding loop as before.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.autonomy_loop import AutonomyOrchestrator
from ace_operational.store import OperationalStore


class ContinuationRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = OperationalStore(Path(self._tmp.name))
        self.orchestrator = AutonomyOrchestrator(self.store)

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def _task(self, title: str) -> dict:
        return self.store.create_task(
            title_id=title,
            user_request=title,
            normalized_goal=title,
        )

    def test_delegated_task_is_routed_not_executed(self) -> None:
        task = self._task("Perbaiki bug nyata di repo")
        order, _created = self.store.create_work_order(
            parent_task_id=task["task_id"],
            idempotency_key="routing-test-1",
            objective="Agen eksternal mengerjakan tugas ini",
            base_snapshot_hash="",
        )
        result = self.orchestrator.run_autonomous_continuation_cycle()
        self.assertEqual(result["executed"], [])
        routed_ids = [row["task_id"] for row in result["routed_to_agent"]]
        self.assertEqual(routed_ids, [task["task_id"]])
        self.assertEqual(result["routed_to_agent"][0]["work_order_ids"],
                         [order["work_order_id"]])
        after = self.store.get_task(task["task_id"])
        self.assertEqual(after["status"], "QUEUED")
        self.assertEqual(self.store.list_receipts(task["task_id"]), [])

    def test_undelegated_task_still_executes(self) -> None:
        task = self._task("Latihan internal engine")
        result = self.orchestrator.run_autonomous_continuation_cycle()
        self.assertEqual(result["routed_to_agent"], [])
        self.assertEqual(len(result["executed"]), 1)
        self.assertEqual(result["executed"][0]["task_id"], task["task_id"])
        self.assertEqual(result["executed"][0]["final_status"], "COMPLETED")
        self.assertTrue(self.store.list_receipts(task["task_id"]))


if __name__ == "__main__":
    unittest.main()
