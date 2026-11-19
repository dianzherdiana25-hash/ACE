"""Unit & adversarial tests untuk tools/builder_onboarding_pack.py (I3)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import builder_onboarding_pack as bop

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestBuilderOnboardingPack(unittest.TestCase):
    def test_01_fixture_contracts_upstream_blobs_and_protected_zones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            secret = base / "secret.jsonl"
            secret.write_text("{}\n", encoding="utf-8")

            repo = base / "repo"
            (repo / "handover").mkdir(parents=True)
            (repo / "tools").mkdir(parents=True)
            (repo / "docs").mkdir(parents=True)
            (repo / "code" / "ace_evaluator").mkdir(parents=True)
            (repo / "code" / "ace_operational").mkdir(parents=True)

            (repo / "handover" / "GOVERNANCE_RULES_20261115.md").write_text("# Aturan\nIsi.\n", encoding="utf-8")
            (repo / "tools" / "FUZZ_STANDARD.md").write_text("# Fuzz\nSeeds: 20261117, 20261118, 20261119.\n", encoding="utf-8")
            (repo / "code" / "ace_evaluator" / "sealed.py").write_text("X = 1\n", encoding="utf-8")
            (repo / "handover" / "CORPUS_V1.jsonl").write_text('{"id":"1"}\n', encoding="utf-8")
            os.symlink(secret, repo / "handover" / "SYMLINK_CORPUS.jsonl")

            raw = (repo / "code" / "ace_evaluator" / "sealed.py").read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            (repo / "docs" / "UPSTREAM_SOURCES.json").write_text(
                json.dumps(
                    {
                        "schema": "ace.source-integration.v1",
                        "files": {"code/ace_evaluator/sealed.py": {"git_blob": blob}},
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                pack = bop.build_onboarding_pack(repo)

            self.assertEqual(pack["schema"], bop.ONBOARDING_SCHEMA)
            self.assertEqual(pack["upstream_sources"]["status"], "PASS")
            self.assertEqual(pack["protected_zones"]["evaluator_modules"], ["code/ace_evaluator/sealed.py"])
            self.assertEqual(pack["protected_zones"]["frozen_corpora"], ["handover/CORPUS_V1.jsonl"])

    def test_02_check_fresh_stale_and_error_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "handover").mkdir(parents=True)
            (repo / "handover" / "GOVERNANCE_RULES_20261115.md").write_text("# Gov\n", encoding="utf-8")
            out = repo / "docs" / "BUILDER_ONBOARDING_PACK.md"

            self.assertEqual(bop.main(["--root", str(repo), "--output", str(out)]), 0)
            self.assertEqual(bop.main(["--root", str(repo), "--check", str(out)]), 0)

            (repo / "STATUS.md").write_text("# Status berubah\n", encoding="utf-8")
            self.assertEqual(bop.main(["--root", str(repo), "--check", str(out)]), 1)
            self.assertEqual(bop.main(["--root", "/tmp/does_not_exist_ace_bop"]), 2)

    def test_03_live_repo_generated_doc_fresh_and_upstream_passes(self) -> None:
        target = REPO_ROOT / "docs" / "BUILDER_ONBOARDING_PACK.md"
        self.assertTrue(target.is_file(), "docs/BUILDER_ONBOARDING_PACK.md wajib ada")
        fresh, msg = bop.check_onboarding_doc(REPO_ROOT, target)
        self.assertTrue(fresh, msg)

        pack = bop.build_onboarding_pack(REPO_ROOT)
        self.assertEqual(pack["summary"]["upstream_status"], "PASS")
        self.assertEqual(pack["summary"]["contracts_present"], pack["summary"]["contracts_total"])


if __name__ == "__main__":
    unittest.main()
