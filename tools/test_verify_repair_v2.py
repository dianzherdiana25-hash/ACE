"""Tamper and historical-custody regression tests for public repair v2 replay."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from tools.verify_repair_v2 import (
    ROOT, RepairV2ReceiptError, verify, verify_manifest,
    V2_GZIP_SHA256, git_blob, V1_BLOB,
)


class RepairV2ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "evidence/repair/v2-provenance.json").read_text())

    def test_manifest_pins_scientific_negative_and_two_replays(self):
        verify_manifest(self.manifest)
        self.assertEqual(self.manifest["v2_candidate"]["gzip_sha256"], V2_GZIP_SHA256)
        self.assertFalse(self.manifest["v2_candidate"]["hypotheses"]["H1_nominal_accuracy_and_coverage"])
        self.assertFalse(self.manifest["v2_candidate"]["scientific_capability_validated"])
        self.assertFalse(self.manifest["candidate_deployed"])

    def test_old_historical_repair_evidence_is_immutable(self):
        old = (ROOT / "evidence/repair/ace_repair_v1.json.gz").read_bytes()
        self.assertEqual(git_blob(old), V1_BLOB)
        with self.assertRaises(RepairV2ReceiptError):
            verify(ROOT / "evidence/repair/ace_repair_v1.json.gz")

    def test_tampered_manifest_hash_or_metrics_is_rejected(self):
        for edit in (
            ("v2_candidate", "gzip_sha256", "0"*64),
            ("v2_candidate", "gzip_bytes", 62732),
            ("v2_candidate", "nominal_verified", {"R_ace": 13}),
            ("v2_candidate", "hypotheses", {
                **self.manifest["v2_candidate"]["hypotheses"],
                "H1_nominal_accuracy_and_coverage": True,
            }),
        ):
            changed = copy.deepcopy(self.manifest)
            container, key, value = edit
            changed[container][key] = value
            with self.subTest(edit=key), self.assertRaises(RepairV2ReceiptError):
                verify_manifest(changed)

    def test_false_release_or_scientific_success_is_rejected(self):
        for field, value in (("scientific_status", "GO"),
                             ("release_gate", "ALLOW_RELEASE"),
                             ("candidate_deployed", True),
                             ("open_world_safe", True),
                             ("oaie_established", True)):
            changed = copy.deepcopy(self.manifest)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(RepairV2ReceiptError):
                verify_manifest(changed)


if __name__ == "__main__":
    unittest.main()
