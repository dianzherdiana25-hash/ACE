"""Public CLI smoke tests for ACE open-world planner (no provider calls)."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ace_operational.open_world_cli import main


class OpenWorldCliTests(unittest.TestCase):
    def run_cli(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(list(args))
        return exit_code, json.loads(output.getvalue())

    def test_read_only_demo_chain(self):
        manifest = Path(__file__).resolve().parents[2] / "examples" / "open_world_capabilities.json"
        code, result = self.run_cli(
            "--manifest", str(manifest),
            "--have", "dataset:raw", "--want", "report:verified",
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["capability_ids"],
                         ["parse-dataset", "research-analysis", "create-report"])
        self.assertEqual(result["total_cost_units"], 7)
        self.assertFalse(result["execution_performed"])

    def test_missing_capability_returns_nonzero(self):
        manifest = Path(__file__).resolve().parents[2] / "examples" / "open_world_capabilities.json"
        code, result = self.run_cli(
            "--manifest", str(manifest),
            "--have", "dataset:raw", "--want", "artifact:unknown",
        )
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "NO_PLAN")
        self.assertFalse(result["structurally_routable"])

    def test_invalid_manifest_rejected_without_action(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "manifest.json"
            file.write_text(json.dumps({"capabilities": [
                {"capability_id": "malformed", "provider": "remote",
                 "consumes": [], "produces": ["x"], "effect": "root"}
            ]}), encoding="utf-8")
            code, result = self.run_cli(
                "--manifest", str(file), "--have", "raw", "--want", "x",
            )
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "INVALID_INPUT")

    def test_unverified_direct_shortcut_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "manifest.json"
            file.write_text(json.dumps({"capabilities": [
                {"capability_id": "fake", "provider": "remote",
                 "consumes": ["raw"], "produces": ["goal"],
                 "status": "UNVERIFIED", "evidence_ref": "self-report"}
            ]}), encoding="utf-8")
            code, result = self.run_cli(
                "--manifest", str(file), "--have", "raw", "--want", "goal",
            )
        self.assertEqual(code, 2)
        self.assertEqual(result["capability_ids"], [])
        self.assertFalse(result["execution_performed"])

    def test_workspace_plan_is_durable_and_same_task_retries_are_idempotent(self):
        from ace_operational.store import OperationalStore
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "ws"
            with OperationalStore(workspace) as store:
                task = store.create_task(
                    title_id="ow-demo", user_request="Generate validated report",
                    normalized_goal="report:verified",
                )
                task_id = task["task_id"]
            manifest = Path(__file__).resolve().parents[2] / "examples" / "open_world_capabilities.json"
            cmd = (
                "--manifest", str(manifest), "--have", "dataset:raw",
                "--want", "report:verified", "--workspace", str(workspace),
                "--task-id", task_id,
            )
            first_code, first = self.run_cli(*cmd)
            second_code, second = self.run_cli(*cmd)
            self.assertEqual((first_code, second_code), (0, 0))
            self.assertEqual(first["plan_key"], second["plan_key"])
            self.assertEqual(first["record_sha256"], second["record_sha256"])
            self.assertFalse(first["execution_performed"])
            with OperationalStore(workspace) as store:
                self.assertEqual(store.get_task(task_id)["status"], "QUEUED")
                count = store._conn.execute("SELECT COUNT(*) FROM open_world_plans").fetchone()[0]
                self.assertEqual(count, 1)

    def test_stage_review_requires_authorization_and_is_not_executed(self):
        from ace_operational.store import OperationalStore
        from ace_mission.bus import MissionBus
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "ws"
            with OperationalStore(workspace) as store:
                task_id = store.create_task(
                    title_id="ow-review", user_request="Check report path",
                    normalized_goal="report:verified",
                )["task_id"]
            manifest = Path(__file__).resolve().parents[2] / "examples" / "open_world_capabilities.json"
            base = (
                "--manifest", str(manifest), "--have", "dataset:raw",
                "--want", "report:verified", "--workspace", str(workspace),
                "--task-id", task_id,
            )
            refused_code, refused = self.run_cli(*base, "--stage-review")
            self.assertEqual(refused_code, 3)
            self.assertEqual(refused["status"], "INVALID_INPUT")
            code, result = self.run_cli(
                *base, "--stage-review", "--authorize-local-queue"
            )
            self.assertEqual(code, 0)
            self.assertEqual(result["review_mission"]["status"], "PENDING_REVIEW")
            self.assertFalse(result["execution_performed"])
            second_code, second = self.run_cli(
                *base, "--stage-review", "--authorize-local-queue"
            )
            self.assertEqual(second_code, 0)
            self.assertEqual(
                result["review_mission"]["mission_id"],
                second["review_mission"]["mission_id"],
            )
            bus = MissionBus(workspace / "mission_bus.sqlite3")
            self.assertEqual(bus.status()["mission_counts"]["PENDING"], 1)
            self.assertTrue(bus.verify_hash_chain())

    def test_workspace_requires_valid_existing_task(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(__file__).resolve().parents[2] / "examples" / "open_world_capabilities.json"
            code, result = self.run_cli(
                "--manifest", str(manifest), "--have", "dataset:raw",
                "--want", "report:verified", "--workspace", directory,
                "--task-id", "missing-task",
            )
            self.assertEqual(code, 3)
            self.assertEqual(result["status"], "INVALID_INPUT")



if __name__ == "__main__":
    unittest.main()
