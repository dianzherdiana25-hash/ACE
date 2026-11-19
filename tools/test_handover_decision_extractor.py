"""Unit & adversarial tests untuk tools/handover_decision_extractor.py (I1)."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import handover_decision_extractor as hde

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestHandoverDecisionExtractor(unittest.TestCase):
    def test_01_extracts_categories_brain_of_origin_and_skips_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            secret = base / "secret.md"
            secret.write_text("Keputusan pemilik rahasia", encoding="utf-8")

            repo = base / "repo"
            (repo / "handover").mkdir(parents=True)
            (repo / "docs").mkdir(parents=True)
            os.symlink(secret, repo / "handover" / "symlink.md")

            (repo / "handover" / "GOV.md").write_text(
                "# Aturan 1 — Wajib hidup\n"
                "Semua hasil self-dev wajib lolos ratifikasi independen sebelum dipakai.\n",
                encoding="utf-8",
            )
            (repo / "handover" / "DEC.md").write_text(
                "Keputusan pemilik 15 Nov menetapkan Slate Otak v2.\n"
                "Aksi bayar nyata diparkir menunggu verifikasi panel.\n"
                "Dokumen ini berstatus DRAF rancangan tahap berikutnya.\n",
                encoding="utf-8",
            )

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                rep = hde.extract_decisions(repo)

            self.assertEqual(rep["schema"], hde.DECISIONS_SCHEMA)
            self.assertEqual(rep["brain_of_origin"], "gravity-proposal")
            self.assertEqual(rep["summary"]["files_scanned"], 2)

            by_cat = {g["category"]: g["items"] for g in rep["groups"]}
            self.assertTrue(any(it["path"] == "handover/GOV.md" and it["line"] == 1 for it in by_cat["GOVERNANCE_RULE"]))
            self.assertTrue(any(it["path"] == "handover/DEC.md" and it["line"] == 1 for it in by_cat["OWNER_HUB_DECISION"]))
            self.assertTrue(any(it["path"] == "handover/DEC.md" and it["line"] == 2 for it in by_cat["PARKED_OR_BLOCKED"]))
            self.assertTrue(any(it["path"] == "handover/DEC.md" and it["line"] == 3 for it in by_cat["OPEN_PROPOSAL"]))

    def test_02_check_fresh_stale_and_error_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "handover").mkdir(parents=True)
            (repo / "handover" / "A.md").write_text("Keputusan hub disetujui APPROVED hari ini.\n", encoding="utf-8")
            out = repo / "docs" / "research" / "ACE_HANDOVER_DECISIONS_EXTRACTED.md"

            self.assertEqual(hde.main(["--root", str(repo), "--output", str(out)]), 0)
            self.assertEqual(hde.main(["--root", str(repo), "--check", str(out)]), 0)

            (repo / "handover" / "B.md").write_text("Butir baru diparkir oleh pemilik.\n", encoding="utf-8")
            self.assertEqual(hde.main(["--root", str(repo), "--check", str(out)]), 1)
            self.assertEqual(hde.main(["--root", "/tmp/does_not_exist_ace_hde"]), 2)

    def test_03_live_repo_generated_doc_fresh_and_all_citations_verified(self) -> None:
        target = REPO_ROOT / "docs" / "research" / "ACE_HANDOVER_DECISIONS_EXTRACTED.md"
        self.assertTrue(target.is_file(), "Dokumen ekstraksi keputusan harus ada")
        fresh, msg = hde.check_extracted_doc(REPO_ROOT, target)
        self.assertTrue(fresh, msg)

        rep = hde.extract_decisions(REPO_ROOT)
        self.assertEqual(rep["brain_of_origin"], "gravity-proposal")
        self.assertGreater(rep["summary"]["total_items_kept"], 30)
        for grp in rep["groups"]:
            for it in grp["items"]:
                src = REPO_ROOT / it["path"]
                self.assertTrue(src.is_file())
                total_lines = len(src.read_text(encoding="utf-8").splitlines())
                self.assertLessEqual(it["line"], total_lines)


if __name__ == "__main__":
    unittest.main()
