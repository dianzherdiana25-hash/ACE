"""Jaga nama repo dan fixpoint renderer saat lokasi checkout berbeda."""
import hashlib
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools import program_glossary, repo_cartography, repo_index


GENERATORS = (
    (repo_index, "docs/REPO_INDEX.md"),
    (repo_cartography, repo_cartography.DEFAULT_OUTPUT_REL),
    (program_glossary, program_glossary.DEFAULT_OUTPUT_REL),
)


class TwoCheckoutTests(unittest.TestCase):
    def seed(self, root):
        root.mkdir()
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin",
                        "https://example.invalid/research/canonical-fixture.git"],
                       check=True, capture_output=True)
        (root / "docs").mkdir()
        (root / "tools").mkdir()
        (root / "README.md").write_text("# Program fixture\n\n**Gate**: aturan periksa bukti.\n")
        (root / "tools" / "local_task.py").write_text('"""Pemeriksaan fixture."""\n')
        # Seperti checkout ACE, daftar berkas turunan sudah ada sebelum regenerasi.
        for _, rel in GENERATORS:
            (root / rel).write_bytes(b"")

    def render(self, root):
        for generator, rel in GENERATORS:
            self.assertEqual(generator.main(["--root", str(root), "--output", str(root / rel)]), 0)
        return {rel: (root / rel).read_bytes() for _, rel in GENERATORS}

    def test_two_checkout_outputs_and_second_round_are_identical(self):
        temp = Path(self.enterContext(TemporaryDirectory()))
        versions = []
        for name in ("checkout-one-unique", "checkout-two-unique"):
            root = temp / name
            self.seed(root)
            first = self.render(root)
            hashes = {rel: hashlib.sha256(data).hexdigest() for rel, data in first.items()}
            second = self.render(root)
            self.assertEqual({rel: hashlib.sha256(data).hexdigest() for rel, data in second.items()}, hashes)
            for data in second.values():
                self.assertIn(b"canonical-fixture", data)
                self.assertNotIn(name.encode(), data)
                self.assertNotIn(str(root).encode(), data)
            versions.append(second)
        self.assertEqual(*versions)
