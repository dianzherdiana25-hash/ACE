"""Public development tests for existing OW-1A trusted pure local executor.

No isolated sandbox or independent scientific validation is claimed. Real
Python callbacks execute only when registered by the trusted test host.
"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ace_operational.open_world_execution import LocalAdapter, OpenWorldLocalExecutor
from ace_operational.open_world_planner import Capability, CapabilityRegistry
from ace_operational.store import OperationalStore


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "ws"
        self.store = OperationalStore(self.workspace)
        self.calls = []

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def build(self, *, verified=True, bad_provider=False, bad_verifier=False):
        registry = CapabilityRegistry()
        registry.register(Capability(
            "step1", frozenset({"raw"}), frozenset({"mid"}),
            "trusted:one", "fixture:step1", "VERIFIED", "none", 1,
        ))
        registry.register(Capability(
            "step2", frozenset({"mid"}), frozenset({"done"}),
            "trusted:two", "fixture:step2", "VERIFIED", "none", 1,
        ))
        if verified:
            for c in registry.list_all():
                self.store.set_frontier_capability(
                    capability_id=c.capability_id, name_id=c.capability_id,
                    category="test", status="KNOWN_AND_TESTED",
                    evidence_ref=c.evidence_ref,
                )

        def run1(inputs):
            self.calls.append("step1")
            return {"mid": inputs["raw"] + 1}

        def run2(inputs):
            self.calls.append("step2")
            return {"done": inputs["mid"] * 2}

        adapters = {
            "step1": LocalAdapter(
                "wrong:provider" if bad_provider else "trusted:one",
                run1, lambda i, o: o["mid"] == i["raw"] + 1,
            ),
            "step2": LocalAdapter(
                "trusted:two", run2,
                (lambda i, o: False) if bad_verifier else
                (lambda i, o: o["done"] == i["mid"] * 2),
            ),
        }
        return OpenWorldLocalExecutor(self.store, registry, adapters)

    def test_two_step_real_local_execution_produces_receipts(self):
        worker = self.build()
        task = worker.submit(
            request="Transform raw to done", available_values={"raw": 5},
            goal_types={"done"},
        )
        completed = worker.run(task["task_id"])
        self.assertEqual(completed["status"], "COMPLETED")
        self.assertEqual(completed["checkpoint"]["available_values"]["done"], 12)
        self.assertEqual(self.calls, ["step1", "step2"])
        self.assertEqual(len(self.store.list_receipts(task["task_id"])), 2)
        self.assertTrue(completed["verification_summary"]["local_verification"])
        self.assertFalse(completed["verification_summary"]["independent_sandbox_verification"])
        # Already completed tasks are not executed twice.
        self.assertEqual(worker.run(task["task_id"])["status"], "COMPLETED")
        self.assertEqual(self.calls, ["step1", "step2"])

    def test_not_frontier_verified_never_calls_adapter(self):
        worker = self.build(verified=False)
        task = worker.submit(
            request="Work", available_values={"raw": 5}, goal_types={"done"},
        )
        stopped = worker.run(task["task_id"])
        self.assertEqual(stopped["status"], "WAITING_FOR_DEPENDENCY")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.list_receipts(task["task_id"]), [])

    def test_provider_mismatch_fails_preflight_before_running(self):
        worker = self.build(bad_provider=True)
        task = worker.submit(
            request="Work", available_values={"raw": 5}, goal_types={"done"},
        )
        stopped = worker.run(task["task_id"])
        self.assertEqual(stopped["status"], "WAITING_FOR_DEPENDENCY")
        self.assertEqual(self.calls, [])

    def test_verifier_rejection_does_not_mark_task_complete(self):
        worker = self.build(bad_verifier=True)
        task = worker.submit(
            request="Work", available_values={"raw": 5}, goal_types={"done"},
        )
        failed = worker.run(task["task_id"])
        self.assertEqual(failed["status"], "FAILED_WITH_RECOVERY_STATE")
        self.assertEqual(failed["checkpoint"]["failed_step"], 1)
        self.assertEqual(failed["checkpoint"]["available_values"]["mid"], 6)
        self.assertEqual(self.calls, ["step1", "step2"])
        self.assertEqual(len(self.store.list_receipts(task["task_id"])), 1)

    def test_restart_does_not_duplicate_completed_effect(self):
        worker = self.build()
        task = worker.submit(
            request="Work", available_values={"raw": 8}, goal_types={"done"},
        )
        worker.run(task["task_id"])
        self.store.close()
        self.store = OperationalStore(self.workspace)
        reboot = self.build()
        task_after = reboot.run(task["task_id"])
        self.assertEqual(task_after["status"], "COMPLETED")
        self.assertEqual(task_after["checkpoint"]["available_values"]["done"], 18)
        self.assertEqual(self.calls, ["step1", "step2"])

    def test_manifest_drift_is_fail_closed(self):
        worker = self.build()
        task = worker.submit(
            request="Work", available_values={"raw": 5}, goal_types={"done"},
        )
        changed = CapabilityRegistry()
        changed.register(Capability(
            "step1", frozenset({"raw"}), frozenset({"mid"}),
            "trusted:one", "fixture:step1", "VERIFIED", "none", 2,
        ))
        changed.register(Capability(
            "step2", frozenset({"mid"}), frozenset({"done"}),
            "trusted:two", "fixture:step2", "VERIFIED", "none", 1,
        ))
        worker.registry = changed
        with self.assertRaises(ValueError):
            worker.run(task["task_id"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.store.get_task(task["task_id"])["status"], "QUEUED")


if __name__ == "__main__":
    unittest.main()
