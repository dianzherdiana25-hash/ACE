"""Tamper, source-version and replay checks for the public v2 runtime demo."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.verify_runtime_demo_v2 import verify, ROOT

FIXTURE = ROOT / "evidence/runtime/v2-demo.json"
HISTORICAL = ROOT / "evidence/runtime/v1-demo.json"


class RuntimeV2ReceiptTests(unittest.TestCase):
    def test_versioned_fixture_matches_github_action_sha_and_provenance(self):
        report = verify(FIXTURE, FIXTURE)
        self.assertEqual(report["status"], "PASS_PUBLIC_ENGINEERING_REPLAY_NOT_SCIENTIFIC_GO")
        self.assertEqual(report["release_gate"], "BLOCK_RELEASE")
        self.assertEqual(report["scientific_status"], "NOT_ASSESSED")
        self.assertFalse(report["candidate_deployed"])

    def test_history_is_preserved_but_not_usable_as_new_fixture(self):
        with self.assertRaises(ValueError):
            verify(HISTORICAL, FIXTURE)

    def test_receipt_mutation_fails_even_if_syntactically_valid_json(self):
        original = json.loads(FIXTURE.read_text(encoding="utf-8"))
        original["status"]["candidate_deployed"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.json"
            path.write_text(json.dumps(original, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify(path, FIXTURE)

    def test_changed_model_identity_cannot_satisfy_versioned_replay(self):
        original = json.loads(FIXTURE.read_text(encoding="utf-8"))
        original["status"]["implementation"] = "f" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changed.json"
            path.write_text(json.dumps(original, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify(path, FIXTURE)


if __name__ == "__main__":
    unittest.main()
