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


if __name__ == "__main__":
    unittest.main()
