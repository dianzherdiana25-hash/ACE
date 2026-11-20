"""Uji semua jenis pointer inventaris di pohon fixture."""
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.successor_inventory import inventory, main


class SuccessorInventoryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        self.git("init", "-q")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                 "commit", "-q", "--allow-empty", "-m", "fixture")

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_all_evidence_types_and_hashes(self):
        self.git("branch", "test/successor-0006")
        file = self.repo / "s0006-note.md"
        file.write_bytes(b"fixture")
        self.git("add", file.name)
        data = b'{"type":"unrelated"}\n{"stage":"successor_6"}\n'
        (self.snapshot / "records.jsonl").write_bytes(data)
        output = self.root / "out"
        self.assertEqual(main(["--repo", str(self.repo), "--snapshot", str(self.snapshot),
                               "--output-dir", str(output)]), 0)
        result = json.loads((output / "inventory.json").read_text())
        self.assertEqual(result["counts"], {"branches": 1, "files": 1, "records": 1})
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(b"fixture").hexdigest())
        self.assertEqual(result["records"][0]["entry"], 2)
        self.assertEqual(result["records"][0]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertIn("records.jsonl", (output / "inventory.md").read_text())

    def test_empty_inventory(self):
        self.assertEqual(inventory(self.repo, self.snapshot)["counts"],
                         {"branches": 0, "files": 0, "records": 0})


if __name__ == "__main__":
    unittest.main()
