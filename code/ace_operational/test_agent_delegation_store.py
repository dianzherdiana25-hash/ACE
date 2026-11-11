"""Public fixtures for durable multiagent task handoffs; no actual AI calls."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ace_operational.agent_fabric import WorkerResult, validate_work_plan
from ace_operational.agent_delegation_store import DurableAgentSupervisor
from ace_operational.store import OperationalStore


class MockWorker:
    def __init__(self):
        self.calls = []
        self.failure = False
        self.exception = False

    def run(self, order, root):
        self.calls.append(order.order_id)
        if self.exception:
            raise RuntimeError("worker may have changed worktree")
        return WorkerResult(order.worker, not self.failure, "fixture",
                            "a" * 64, "b" * 64, int(self.failure), {})


class DurableDelegationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "state"
        self.wt = Path(self.tmp.name) / "worker"
        self.wt.mkdir()
        (self.wt / ".git").write_text(
            "gitdir: " + str(Path(self.tmp.name) / "git" / "worktrees" / "worker")
        )
        self.store = OperationalStore(self.ws)
        self.worker = MockWorker()
        self.supervisor = DurableAgentSupervisor(
            self.store, self.worker, verifier=lambda o, root, result: result.success
        )
        self.plan = validate_work_plan("Fix unseen bug", {"orders": [
            {"id": "inspect", "worker": "codex", "mode": "read-only",
             "instruction": "Locate the relevant defect", "depends_on": []},
            {"id": "repair", "worker": "antigravity", "mode": "workspace-write",
             "instruction": "Apply patch and regression", "depends_on": ["inspect"]},
        ]}, planner="ollama:mock")
        self.task = self.supervisor.submit(self.plan)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def advance(self, **opts):
        return self.supervisor.advance(self.task["task_id"], str(self.wt), **opts)

    def test_default_denial_does_not_use_quota(self):
        self.assertEqual(self.advance()["status"], "NOT_AUTHORIZED")
        self.assertEqual(self.worker.calls, [])
        self.assertEqual(self.store.get_task(self.task["task_id"])["status"], "QUEUED")

    def test_one_step_per_call_write_denial_and_local_receipts(self):
        first = self.advance(authorized=True)
        self.assertEqual(first["status"], "ACTIVE")
        self.assertEqual(first["checkpoint"]["step_index"], 1)
        self.assertEqual(self.advance(authorized=True)["status"], "WRITE_NOT_AUTHORIZED")
        self.assertEqual(self.worker.calls, ["inspect"])
        second = self.advance(authorized=True, allow_write=True)
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(second["checkpoint"]["step_index"], 2)
        self.assertEqual(self.worker.calls, ["inspect", "repair"])
        self.assertEqual(len(self.store.list_receipts(self.task["task_id"])), 2)
        self.assertFalse(second["verification_summary"]["independent_sandbox_verification"])
        self.assertEqual(second["verification_summary"]["release_gate"], "BLOCK_RELEASE")
        self.advance(authorized=True, allow_write=True)
        self.assertEqual(self.worker.calls, ["inspect", "repair"])

    def test_restart_resumes_only_pending_step(self):
        self.advance(authorized=True)
        self.store.close()
        self.store = OperationalStore(self.ws)
        self.worker = MockWorker()
        self.supervisor = DurableAgentSupervisor(
            self.store, self.worker, verifier=lambda o, root, result: result.success
        )
        result = self.advance(authorized=True, allow_write=True)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(self.worker.calls, ["repair"])

    def test_crash_with_inflight_never_silently_reruns(self):
        self.store.update_task(self.task["task_id"], status="ACTIVE",
                               checkpoint={"inflight": {
                                   "order_id": "inspect", "step_index": 0
                               }})
        self.store.close()
        self.store = OperationalStore(self.ws)
        self.supervisor = DurableAgentSupervisor(
            self.store, self.worker, verifier=lambda o, root, result: True
        )
        self.store.recover_interrupted_tasks()
        self.assertEqual(
            self.advance(authorized=True)["status"], "RECONCILIATION_REQUIRED"
        )
        self.assertEqual(self.worker.calls, [])

    def test_provider_failure_requires_manual_reconciliation(self):
        self.worker.failure = True
        self.assertEqual(
            self.advance(authorized=True)["status"], "FAILED_WITH_RECOVERY_STATE"
        )
        self.assertEqual(
            self.advance(authorized=True)["status"], "RECONCILIATION_REQUIRED"
        )
        self.assertEqual(self.worker.calls, ["inspect"])
        receipts = self.store.list_receipts(self.task["task_id"])
        self.assertEqual(len(receipts), 1)
        self.assertFalse(receipts[0]["passed"])

    def test_worker_exception_cannot_claim_success(self):
        self.worker.exception = True
        self.assertEqual(
            self.advance(authorized=True)["status"], "FAILED_WITH_RECOVERY_STATE"
        )
        self.assertEqual(self.worker.calls, ["inspect"])

    def test_verifier_veto_is_final_until_reconciled(self):
        self.supervisor.verifier = lambda o, r, x: False
        self.assertEqual(
            self.advance(authorized=True)["status"], "FAILED_WITH_RECOVERY_STATE"
        )
        self.assertEqual(self.worker.calls, ["inspect"])

    def test_no_verifier_no_calls(self):
        self.supervisor.verifier = None
        self.assertEqual(self.advance(authorized=True)["status"], "NO_HOST_VERIFIER")
        self.assertEqual(self.worker.calls, [])

    def test_corrupt_plan_checkpoint_rejected(self):
        self.store.update_task(self.task["task_id"],
                               checkpoint={"plan_digest": "sha256:forged"})
        with self.assertRaises(ValueError):
            self.advance(authorized=True)
        self.assertEqual(self.worker.calls, [])

    def test_missing_local_scientific_attestation_is_explicit(self):
        cp = self.store.get_task(self.task["task_id"])["checkpoint"]
        self.assertEqual(cp["scientific_status"], "NOT_ASSESSED")
        self.assertEqual(cp["release_gate"], "BLOCK_RELEASE")
        self.assertEqual(cp["plan_digest"], self.plan.plan_digest)


if __name__ == "__main__":
    unittest.main()
