"""Integration tests for read-only ACE Open-World persistence and review queue.

All fixtures are public. They do not certify scientific evidence or provider
execution; only durability, idempotency and boundaries are under test.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ace_mission.bus import MissionBus
from ace_operational.open_world_planner import Capability, CapabilityRegistry
from ace_operational.open_world_task_bridge import OpenWorldTaskBridge
from ace_operational.open_world_review_bus import queue_structural_review
from ace_operational.store import OperationalStore


def registry(*, provider="provider:one", effect="read", verified=True):
    caps = CapabilityRegistry()
    caps.register(Capability(
        capability_id="convert_data", consumes=frozenset({"raw:dataset"}),
        produces=frozenset({"dataset:clean"}), provider=provider,
        status="VERIFIED" if verified else "UNVERIFIED",
        evidence_ref="public-fixture:validation" if verified else "",
        effect=effect, cost_units=3,
    ))
    caps.register(Capability(
        capability_id="analyze", consumes=frozenset({"dataset:clean"}),
        produces=frozenset({"report:validated"}), provider="worker:two",
        status="VERIFIED", evidence_ref="public-fixture:analysis",
        effect="none", cost_units=2,
    ))
    return caps


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        self.store = OperationalStore(self.workspace)
        self.task = self.store.create_task(
            title_id="open-world",
            user_request="Analyze unfamiliar dataset",
            normalized_goal="Produce report:validated from raw:dataset",
        )
        self.bridge = OpenWorldTaskBridge(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def plan(self, reg=None, **options):
        return self.bridge.plan_and_record(
            self.task["task_id"], reg or registry(),
            available_types={"raw:dataset"}, goal_types={"report:validated"},
            **options,
        )

    def test_persists_exact_snapshot_without_completing_task(self):
        out = self.plan()
        self.assertEqual(out["result"]["status"], "READY")
        self.assertEqual(out["result"]["capability_ids"], ["convert_data", "analyze"])
        self.assertEqual(out["result"]["total_cost_units"], 5)
        self.assertFalse(out["result"]["execution_performed"])
        self.assertEqual(out["result"]["scientific_status"], "NOT_ASSESSED")
        self.assertEqual(self.store.get_task(self.task["task_id"])["status"], "QUEUED")
        self.assertEqual(len(self.bridge.list_plan_keys(self.task["task_id"])), 1)

    def test_identical_retry_is_idempotent(self):
        first = self.plan()
        second = self.plan()
        self.assertEqual(first, second)
        self.assertEqual(len(self.bridge.list_plan_keys(self.task["task_id"])), 1)

    def test_snapshot_version_change_creates_new_journal_record(self):
        first = self.plan()
        second = self.plan(registry(provider="provider:replacement"))
        self.assertNotEqual(first["plan_key"], second["plan_key"])
        self.assertEqual(len(self.bridge.list_plan_keys(self.task["task_id"])), 2)

    def test_restart_recovers_same_digest_and_snapshot(self):
        original = self.plan()
        self.store.close()
        self.store = OperationalStore(self.workspace)
        self.bridge = OpenWorldTaskBridge(self.store)
        restored = self.bridge.get_plan(original["plan_key"])
        self.assertEqual(restored, original)
        self.assertEqual(self.plan()["plan_key"], original["plan_key"])

    def test_journal_tampering_fails_closed(self):
        out = self.plan()
        with self.store._lock:
            self.store._conn.execute(
                "UPDATE open_world_plans SET result_json = ? WHERE plan_key = ?",
                (json.dumps({"status": "READY", "execution_performed": True}), out["plan_key"]),
            )
            self.store._conn.commit()
        with self.assertRaises(ValueError):
            self.bridge.get_plan(out["plan_key"])
        with self.assertRaises(ValueError):
            self.plan()

    def test_unknown_task_is_rejected_without_new_row(self):
        with self.assertRaises(KeyError):
            self.bridge.plan_and_record(
                "no-such-task", registry(),
                available_types={"raw:dataset"}, goal_types={"report:validated"},
            )
        with self.store._lock:
            count = self.store._conn.execute("SELECT COUNT(*) FROM open_world_plans").fetchone()[0]
        self.assertEqual(count, 0)

    def test_no_plan_saved_honestly_and_cannot_be_staged(self):
        out = self.plan(registry(verified=False))
        self.assertEqual(out["result"]["status"], "NO_PLAN")
        self.assertEqual(out["result"]["capability_ids"], [])
        bus = MissionBus(self.workspace / "mission_bus.sqlite3")
        with self.assertRaises(ValueError):
            self.bridge.stage_review_mission(out["plan_key"], bus, authorize_local_queue=True)
        self.assertEqual(bus.status()["mission_counts"], {})

    def test_permission_required_before_local_review_queue(self):
        out = self.plan()
        bus = MissionBus(self.workspace / "mission_bus.sqlite3")
        with self.assertRaises(PermissionError):
            self.bridge.stage_review_mission(out["plan_key"], bus)
        self.assertEqual(bus.status()["mission_counts"], {})

    def test_external_action_cannot_be_enqueued_as_review(self):
        out = self.plan(registry(effect="external"), allowed_effects=("none", "external"))
        self.assertEqual(out["result"]["status"], "READY")
        bus = MissionBus(self.workspace / "mission_bus.sqlite3")
        with self.assertRaises(PermissionError):
            self.bridge.stage_review_mission(out["plan_key"], bus, authorize_local_queue=True)
        self.assertEqual(bus.status()["mission_counts"], {})

    def test_review_mission_idempotent_after_retry_and_restart(self):
        out = self.plan()
        bus = MissionBus(self.workspace / "mission_bus.sqlite3")
        first = self.bridge.stage_review_mission(out["plan_key"], bus, authorize_local_queue=True)
        second = self.bridge.stage_review_mission(out["plan_key"], bus, authorize_local_queue=True)
        self.assertEqual(first["mission_id"], second["mission_id"])
        self.assertFalse(first["execution_performed"])
        self.assertTrue(bus.verify_hash_chain())
        self.assertEqual(bus.status()["mission_counts"]["PENDING"], 1)

        claimed = bus.next_mission("reviewer:test")
        self.assertEqual(claimed["id"], first["mission_id"])
        self.assertIn("do NOT execute", claimed["goal"])

        self.store.close()
        self.store = OperationalStore(self.workspace)
        self.bridge = OpenWorldTaskBridge(self.store)
        bus_after_restart = MissionBus(self.workspace / "mission_bus.sqlite3")
        third = self.bridge.stage_review_mission(
            out["plan_key"], bus_after_restart, authorize_local_queue=True
        )
        self.assertEqual(first["mission_id"], third["mission_id"])
        self.assertEqual(bus_after_restart.status()["mission_counts"]["CLAIMED"], 1)
        self.assertTrue(bus_after_restart.verify_hash_chain())

    def test_review_id_collision_with_changed_snapshot_rejected(self):
        bus = MissionBus(self.workspace / "mission_bus.sqlite3")
        plan_key = "ow_" + ("a" * 64)
        first = queue_structural_review(
            bus, plan_key=plan_key, record_sha256="b" * 64
        )
        self.assertTrue(first.startswith("mission_"))
        with self.assertRaises(ValueError):
            queue_structural_review(
                bus, plan_key=plan_key, record_sha256="c" * 64
            )
        self.assertTrue(bus.verify_hash_chain())
        self.assertEqual(bus.status()["mission_counts"]["PENDING"], 1)


if __name__ == "__main__":
    unittest.main()
