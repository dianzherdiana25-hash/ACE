"""Uji peta klaim sekaligus batas root bukti."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.successor_inventory import main


class ClaimsMapTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.repo, self.snapshot = root / "repo", root / "snapshot"
        self.repo.mkdir()
        self.snapshot.mkdir()
        self.out, self.claims = root / "out", root / "claims.json"
        self.git("init", "-q")
        self.evidence = self.repo / "s0006-evidence.md"
        self.evidence.write_text("fixture\n")
        self.git("add", self.evidence.name)
        self.args = ["--repo", str(self.repo), "--snapshot", str(self.snapshot),
                     "--output-dir", str(self.out), "--claims", str(self.claims)]

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_map_missing_and_untested_with_inventory_pointer(self):
        claims = [
            {"id": "missing", "evidence": "absent.md", "status": "teruji"},
            {"id": "untested", "evidence": self.evidence.name, "status": "belum"},
            {"id": "tested", "evidence": self.evidence.name, "status": "teruji"},
        ]
        self.claims.write_text(json.dumps(claims))
        self.assertEqual(main(self.args), 0)
        report = json.loads((self.out / "inventory.json").read_bytes())["claims"]
        self.assertEqual(report["missing_evidence"], [{**claims[0], "in_successor_inventory": False}])
        self.assertEqual(report["untested_with_evidence"], [{**claims[1], "in_successor_inventory": True}])
        self.assertIn("Klaim dengan bukti hilang (1)", (self.out / "inventory.md").read_text())

    def test_outside_root_and_symlink_escape_refused_without_output(self):
        outside = self.repo.parent / "outside.md"
        outside.write_text("fixture\n")
        (self.repo / "escape.md").symlink_to(outside)
        for path in ("../outside.md", str(outside), "escape.md"):
            with self.subTest(path=path), redirect_stderr(StringIO()) as errors:
                self.claims.write_text(json.dumps([{"id": "outside", "evidence": path, "status": "belum"}]))
                with self.assertRaises(SystemExit) as failed:
                    main(self.args)
                self.assertEqual(failed.exception.code, 2)
                self.assertIn("di luar", errors.getvalue())
                self.assertFalse(self.out.exists())
