"""Jaga nama repo dan fixpoint renderer saat lokasi checkout berbeda."""
import hashlib
import json
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
    def seed(self, root, derived=b""):
        root.mkdir()
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin",
                        "https://example.invalid/research/canonical-fixture.git"],
                       check=True, capture_output=True)
        (root / "docs").mkdir()
        (root / "tools").mkdir()
        (root / "README.md").write_text("# Program fixture\n\n**Gate**: aturan periksa bukti.\n")
        (root / "tools" / "local_task.py").write_text('"""Pemeriksaan fixture."""\n')
        if derived is not None:
            for _, rel in GENERATORS:
                (root / rel).write_bytes(derived)

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

    def snapshot(self, root):
        return {rel: (root / rel).read_bytes() for _, rel in GENERATORS if (root / rel).is_file()}

    def converge(self, root):
        previous = self.snapshot(root)
        changed = set()
        for round_number in range(1, 9):
            current = self.render(root)
            if current == previous:
                return current, round_number, sorted(changed)
            changed.update(rel for rel, data in current.items() if previous.get(rel) != data)
            previous = current
        self.fail("Generator belum mencapai fixpoint setelah 8 ronde")

    def test_bootstrap_and_stale_checkouts_converge_to_current_bytes(self):
        temp = Path(self.enterContext(TemporaryDirectory()))
        current, bootstrap, stale = (temp / name for name in ("current", "bootstrap", "stale"))
        self.seed(current)
        self.seed(bootstrap, derived=None)
        self.seed(stale, derived=b"# Stale fixture\n")
        self.assertEqual(self.snapshot(bootstrap), {})
        self.assertEqual(set(self.snapshot(stale).values()), {b"# Stale fixture\n"})

        self.converge(current)
        expected, current_rounds, _ = self.converge(current)
        bootstrapped, bootstrap_rounds, bootstrap_changes = self.converge(bootstrap)
        refreshed, refresh_rounds, _ = self.converge(stale)
        report = {
            "bootstrap_rounds": bootstrap_rounds,
            "refresh_rounds": refresh_rounds,
            "current_rounds": current_rounds,
            "bootstrap_changed_files": bootstrap_changes,
            "cross_checkout_differences": {
                name: sorted(rel for rel, data in expected.items() if actual.get(rel) != data)
                for name, actual in (("bootstrap", bootstrapped), ("stale", refreshed))
            },
        }
        print(json.dumps(report, sort_keys=True))
        self.assertEqual(current_rounds, 1)
        self.assertGreater(bootstrap_rounds, 1)
        self.assertGreater(refresh_rounds, 1)
        self.assertEqual(bootstrap_changes, sorted(expected))
        self.assertEqual(report["cross_checkout_differences"], {"bootstrap": [], "stale": []})
        self.assertEqual(bootstrapped, expected)
        self.assertEqual(refreshed, expected)
