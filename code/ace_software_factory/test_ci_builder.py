"""Verifier workflow serta perintah suite pada repository produk fixture."""
from hashlib import sha256
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import ci_builder as model
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.repo_scaffolder import materialize


class CITests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())) / "checkout"
        self.source = b"import unittest\nclass Smoke(unittest.TestCase):\n    def test_negative(self):\n        self.assertLess(-1, 0)\n"
        self.name = "tests/unit/test_sample.py"
        materialize(self.root, {self.name: self.source})
        self.plan = {"schema": "ace.factory-ci-plan.v1", "id": "product_ci", "runner": "ubuntu-24.04",
                     "checkout_commit": "11bd71901bbe5b1630ceea73d27597364c9af683",
                     "checkout_ref": "fixture/reviewed-action-pin", "branches": ["stable/v1", "main"],
                     "suites": [{"id": "unit", "tests": "tests/unit", "timeout_minutes": 2,
                                 "files": [{"path": self.name, "sha256": sha256(self.source).hexdigest()}]}]}

    def test_uses_pinned_action_and_local_discovery_command(self):
        files, report = model.build(self.root, self.plan, identity(self.plan))
        workflow = files[report["workflow"]].decode()
        self.assertIn('branches: ["main", "stable/v1"]', workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn(f"actions/checkout@{self.plan['checkout_commit']}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        run = next(row.split("run: ", 1)[1] for row in workflow.splitlines() if "run: " in row)
        result = subprocess.run([sys.executable, *shlex.split(run)[1:]], cwd=self.root, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Ran 1 test", result.stderr)
        self.assertEqual(report["workflow_sha256"], sha256(workflow.encode()).hexdigest())

    def test_refuses_wildcard_branches_and_unpinned_actions(self):
        self.plan["branches"] = ["feature/*"]
        with self.assertRaisesRegex(ContractError, "Branch"):
            model.build(self.root, self.plan, identity(self.plan))
        self.plan["branches"] = ["feature/one"]
        self.plan["checkout_commit"] = "main"
        with self.assertRaisesRegex(ContractError, "pin"):
            model.build(self.root, self.plan, identity(self.plan))

    def test_test_bytes_are_bound_without_creating_workflow_in_source(self):
        (self.root / self.name).write_bytes(b"pass\n")
        with self.assertRaisesRegex(ContractError, "SHA-256"):
            model.build(self.root, self.plan, identity(self.plan))
        self.assertFalse((self.root / ".github").exists())
