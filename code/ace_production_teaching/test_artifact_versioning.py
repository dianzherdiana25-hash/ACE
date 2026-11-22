from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, canonical, identity
from .artifact_versioning import version
from .test_tabular_engine import save


class VersionTests(unittest.TestCase):
    def test_parent_transaction_and_actual_byte_delta(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            parts = [save(root, key, key.encode()) | {"name": key} for key in ("one", "two", "three")]
            plan = {"schema": "ace.production.version-plan.v1", "id": "note", "version": 1, "parent": None, "inputs": parts}
            result, receipt = version(plan, identity(plan), root)
            self.assertEqual(receipt["difference"]["added"], ["one", "three", "two"])
            raw = canonical(receipt["manifest"]) + b"\n"
            old = save(root, "parent.json", raw)
            added = save(root, "four", b"new") | {"name": "four"}
            changed = save(root, "two_new", b"changed") | {"name": "two"}
            plan.update(version=2, parent=old, inputs=[parts[0], changed, added])
            result, report = version(plan, identity(plan), root)
            self.assertEqual(report["difference"],
                             {"added": ["four"], "removed": ["three"], "changed": ["two"], "unchanged": ["one"]})
            self.assertEqual((root / "parent.json").read_bytes(), raw)
            plan["version"] = 4
            with self.assertRaisesRegex(ProductionError, "urutan parent"):
                version(plan, identity(plan), root)
