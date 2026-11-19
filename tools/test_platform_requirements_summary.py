"""Unit & adversarial tests untuk tools/platform_requirements_summary.py (H4)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import platform_requirements_summary as prs

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPlatformRequirementsSummary(unittest.TestCase):
    def test_01_extracts_exact_file_line_citations_and_skips_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            secret = base / "secret.md"
            secret.write_text("Fastwork password leak\n", encoding="utf-8")

            repo = base / "repo"
            (repo / "docs" / "research").mkdir(parents=True)
            (repo / "handover").mkdir(parents=True)
            os.symlink(secret, repo / "docs" / "leak.md")

            (repo / "docs" / "research" / "NOTES.md").write_text(
                "# Judul\n"
                "- Kontrak KBM bersifat eksklusif dan minimum payout Rp15.000 sesudah 8 bab.\n"
                "- Biaya penarikan Fastwork tercatat kontradiktif (Rp3.000 flat vs gratis).\n"
                "- Verifikasi misi Facebook tetap terblokir menunggu panel pemilik.\n",
                encoding="utf-8",
            )
            (repo / "handover" / "PRIVACY.md").write_text(
                "- QRIS receipt & rekening penuh tidak boleh dicantumkan (pakai placeholder).\n",
                encoding="utf-8",
            )

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                rep = prs.extract_platform_requirements(repo)

            self.assertEqual(rep["schema"], prs.PLATFORM_SUMMARY_SCHEMA)
            self.assertEqual(rep["brain_of_origin"], "gravity-proposal")
            self.assertEqual(rep["summary"]["markdown_files_scanned"], 2)

            by_id = {p["platform_id"]: p for p in rep["platforms"]}
            self.assertEqual(by_id["kbm_app"]["citations"][0]["path"], "docs/research/NOTES.md")
            self.assertEqual(by_id["kbm_app"]["citations"][0]["line"], 2)
            self.assertIn("exclusivity_ip", by_id["kbm_app"]["citations"][0]["tags"])
            self.assertEqual(by_id["fastwork"]["citations"][0]["line"], 3)
            self.assertEqual(by_id["facebook"]["citations"][0]["line"], 4)
            self.assertEqual(by_id["gopay_qris_seabank"]["citations"][0]["path"], "handover/PRIVACY.md")

    def test_02_check_fresh_stale_and_error_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "docs" / "research").mkdir(parents=True)
            (repo / "docs" / "research" / "SRC.md").write_text(
                "- KBM payout minimal Rp15.000.\n",
                encoding="utf-8",
            )
            out = repo / "docs" / "research" / "ACE_PLATFORM_REQUIREMENTS_SUMMARY.md"
            self.assertEqual(prs.main(["--root", str(repo), "--output", str(out)]), 0)
            self.assertEqual(prs.main(["--root", str(repo), "--check", str(out)]), 0)

            (repo / "docs" / "research" / "SRC.md").write_text(
                "- KBM payout minimal Rp15.000.\n- Fastwork fee unverified.\n",
                encoding="utf-8",
            )
            self.assertEqual(prs.main(["--root", str(repo), "--check", str(out)]), 1)
            self.assertEqual(prs.main(["--root", "/tmp/does_not_exist_ace_prs"]), 2)

    def test_03_live_repo_generated_doc_fresh_and_all_citations_exist_on_disk(self) -> None:
        target = REPO_ROOT / "docs" / "research" / "ACE_PLATFORM_REQUIREMENTS_SUMMARY.md"
        self.assertTrue(target.is_file(), "Dokumen ringkasan platform harus dibuat")
        fresh, msg = prs.check_summary_doc(REPO_ROOT, target)
        self.assertTrue(fresh, msg)

        rep = prs.extract_platform_requirements(REPO_ROOT)
        self.assertGreater(rep["summary"]["total_citations_kept"], 20)
        for p in rep["platforms"]:
            for cit in p["citations"]:
                src_file = REPO_ROOT / cit["path"]
                self.assertTrue(src_file.is_file())
                lines = src_file.read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(cit["line"], len(lines))


if __name__ == "__main__":
    unittest.main()
