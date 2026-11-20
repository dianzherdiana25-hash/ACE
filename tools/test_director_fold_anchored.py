"""Pastikan rencana lipat hanya menawarkan kelas A bila based_on tertambat."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.test_director_fold import row


class DirectorFoldAnchoredTests(unittest.TestCase):
    def run_fold(self, rows, *flags):
        root = Path(self.enterContext(TemporaryDirectory()))
        path = root / "proposals.jsonl"
        path.write_text("".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8")
        store = root / "store.json"
        store.write_text(json.dumps({"verified_refs": ["clean"]}), encoding="utf-8")
        args = [str(store) if arg == "fixture-store" else arg for arg in flags]
        return subprocess.run([sys.executable, str(Path(__file__).with_name("director_fold.py")),
                               str(path), *args], capture_output=True, check=False)

    def test_anchoring_only_downgrades_dangling_class_a(self):
        boundaries = {"evidence_refs": ["receipt"], "touches_money": False,
                      "touches_publication": False, "touches_external": False, "reversible": True}
        rows = [{**row(task_id, refs, 1), **boundaries} for task_id, refs in (
            ("clean", ["clean"]), ("dangling", ["dangling"]), ("multi", ["clean", "dangling"]),
        )]
        run = self.run_fold(rows, "--require-anchored", "--store", "fixture-store")
        self.assertEqual(run.returncode, 0, run.stderr)
        groups = {group["representative"]: group for group in json.loads(run.stdout)["groups"]}
        self.assertEqual(groups["clean"]["initial_class"], "A")
        self.assertEqual(groups["dangling"]["initial_class"], "B")
        self.assertEqual(groups["dangling"]["class_reasons"], ["unanchored"])
        self.assertEqual((groups["multi"]["kind"], groups["multi"]["initial_class"]), ("multi_gap", "B"))

    def test_default_preserves_i4_fixture_cli_bytes(self):
        run = self.run_fold([row("old", ["g"], 1), {**row("new", ["g"], 2), "touches_external": True}])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(hashlib.sha256(run.stdout).hexdigest(),
                         "8f42e6accf0d57c1c008ea6094d0b514851a92afad82369f47c012337c33c6c6")

    def test_anchoring_without_store_refuses_to_emit_plan(self):
        run = self.run_fold([row("old", ["g"], 1)], "--require-anchored")
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, b"")
