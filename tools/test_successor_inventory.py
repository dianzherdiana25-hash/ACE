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

    def test_circular_and_outside_root_symlinks_terminate_and_report_both_findings(self):
        outside_dir = self.root / "outside_secret"
        outside_dir.mkdir()
        outside_file = outside_dir / "s0006-leak.jsonl"
        outside_file.write_text('{"leak": "successor-0006"}\n', encoding="utf-8")

        # Symlink melingkar di dalam root (direktori ke induk + siklus dua symlink file)
        sub = self.snapshot / "nested"
        sub.mkdir()
        (sub / "loop_parent").symlink_to(self.snapshot)
        (self.snapshot / "cyc_a").symlink_to("cyc_b")
        (self.snapshot / "cyc_b").symlink_to("cyc_a")

        # Symlink keluar root (baik direktori maupun file di repo dan snapshot)
        (self.snapshot / "escape_dir").symlink_to(outside_dir)
        (self.repo / "escape_s0006.jsonl").symlink_to(outside_file)
        (self.repo / "repo_cyc").symlink_to(".")

        output = self.root / "out_symlinks"
        code = main([
            "--repo", str(self.repo),
            "--snapshot", str(self.snapshot),
            "--output-dir", str(output),
        ])
        self.assertEqual(code, 0)
        result = json.loads((output / "inventory.json").read_text(encoding="utf-8"))

        # Tidak mengikuti tautan keluar root: records dan files tetap kosong
        self.assertEqual(result["counts"], {"branches": 0, "files": 0, "records": 0})
        self.assertEqual(result["files"], [])
        self.assertEqual(result["records"], [])

        findings = {(item["tree"], item["path"]): item["kind"] for item in result["symlink_findings"]}
        self.assertEqual(findings[("snapshot", "nested/loop_parent")], "symlink_cycle")
        self.assertEqual(findings[("snapshot", "cyc_a")], "symlink_cycle")
        self.assertEqual(findings[("snapshot", "cyc_b")], "symlink_cycle")
        self.assertEqual(findings[("snapshot", "escape_dir")], "symlink_outside_root")
        self.assertEqual(findings[("repo", "escape_s0006.jsonl")], "symlink_outside_root")
        self.assertEqual(findings[("repo", "repo_cyc")], "symlink_cycle")

        md = (output / "inventory.md").read_text(encoding="utf-8")
        self.assertIn("Temuan symlink", md)
        self.assertIn("symlink_cycle", md)
        self.assertIn("symlink_outside_root", md)


if __name__ == "__main__":
    unittest.main()
