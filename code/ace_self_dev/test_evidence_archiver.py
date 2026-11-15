"""Tests for EvidenceArchiver manifest handling.

Absorption audit (PR #231, item #7): a corrupt evidence
manifest used to be silently reset by a bare except-pass.
It is now preserved as a .corrupt.json sibling for
inspection before the index is rebuilt.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ace_self_dev.evidence_archiver import EvidenceArchiver


class EvidenceArchiverManifestTests(unittest.TestCase):
    def test_corrupt_manifest_is_preserved_then_rebuilt(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            archiver = EvidenceArchiver(root)
            archiver.checkpoints_dir.mkdir(parents=True, exist_ok=True)
            archiver.evidence_dir.mkdir(parents=True, exist_ok=True)
            archiver.manifest_path.write_text("{ not json", encoding="utf-8")

            manifest = archiver.build_or_update_manifest()

            corrupt = archiver.manifest_path.with_suffix(".corrupt.json")
            self.assertTrue(corrupt.exists())
            self.assertEqual(corrupt.read_text(encoding="utf-8"), "{ not json")
            self.assertEqual(manifest["total_artifacts"], 0)
            # The rebuilt manifest is valid JSON on disk.
            on_disk = json.loads(
                archiver.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["schema_version"], "1.0")

    def test_valid_manifest_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            archiver = EvidenceArchiver(root)
            archiver.checkpoints_dir.mkdir(parents=True, exist_ok=True)
            good = {"schema_version": "1.0", "total_artifacts": 0,
                    "artifacts": {}}
            archiver.manifest_path.write_text(json.dumps(good),
                                              encoding="utf-8")
            archiver.build_or_update_manifest()
            self.assertFalse(
                archiver.manifest_path.with_suffix(".corrupt.json").exists())


if __name__ == "__main__":
    unittest.main()
