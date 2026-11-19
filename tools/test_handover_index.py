"""Unit & adversarial tests untuk tools/handover_index.py (G2)."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import handover_index as hi

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestHandoverIndex(unittest.TestCase):
    def test_01_empty_repo_and_symlink_skip_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            secret = base / "secret.txt"
            secret.write_text("TOP SECRET", encoding="utf-8")

            repo = base / "repo"
            (repo / "handover").mkdir(parents=True)
            (repo / "docs").mkdir(parents=True)
            os.symlink(secret, repo / "handover" / "leak.txt")
            (repo / "handover" / "CORPUS_A.jsonl").write_text('{"id":"1"}\n{"id":"2"}\n', encoding="utf-8")
            (repo / "docs" / "GUIDE.md").write_text("# Panduan Sistem\nIsi.\n", encoding="utf-8")

            idx = hi.build_handover_index(repo)
            self.assertEqual(idx["schema"], hi.HANDOVER_INDEX_SCHEMA)
            self.assertEqual(idx["summary"]["total_files"], 2)
            self.assertEqual(idx["summary"]["handover_files"], 1)
            self.assertEqual(idx["summary"]["docs_files"], 1)
            self.assertEqual(idx["summary"]["skipped_symlinks"], 1)
            paths = [e["path"] for e in idx["entries"]]
            self.assertNotIn("handover/leak.txt", paths)

    def test_02_generate_and_check_fresh_vs_stale_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "handover").mkdir(parents=True)
            (repo / "docs").mkdir(parents=True)
            (repo / "handover" / "RANCANGAN_EVO_9999.md").write_text("# Rancangan EVO 9999\nDetail.\n", encoding="utf-8")
            (repo / "docs" / "VERDICT.md").write_text("# Verdict Gate\nPASS.\n", encoding="utf-8")

            out_doc = repo / "docs" / "HANDOVER_INDEX.md"
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                rc_gen = hi.main(["--root", str(repo), "--output", str(out_doc)])
            self.assertEqual(rc_gen, 0)
            self.assertTrue(out_doc.is_file())

            # --check harus exit 0 & tetap idempoten jika digenerate ulang
            rc_fresh = hi.main(["--root", str(repo), "--check", str(out_doc)])
            self.assertEqual(rc_fresh, 0)
            before = out_doc.read_bytes()
            hi.main(["--root", str(repo), "--output", str(out_doc)])
            self.assertEqual(before, out_doc.read_bytes())

            # Tambah berkas baru -> --check wajib exit 1 (STALE)
            (repo / "handover" / "NEW_NOTE.md").write_text("# Catatan Baru\n", encoding="utf-8")
            rc_stale = hi.main(["--root", str(repo), "--check", str(out_doc)])
            self.assertEqual(rc_stale, 1)

            # Target hilang -> exit 1; root tidak valid -> exit 2
            self.assertEqual(hi.main(["--root", str(repo), "--check", str(repo / "docs" / "NO.md")]), 1)
            self.assertEqual(hi.main(["--root", "/tmp/does_not_exist_ace_hi"]), 2)

    def test_03_live_repo_generated_doc_matches_check(self) -> None:
        target = REPO_ROOT / "docs" / "HANDOVER_INDEX.md"
        self.assertTrue(target.is_file(), "docs/HANDOVER_INDEX.md harus dibuat dan mutakhir")
        fresh, msg = hi.check_handover_index(REPO_ROOT, target)
        self.assertTrue(fresh, msg)
        idx = hi.build_handover_index(REPO_ROOT)
        self.assertGreater(idx["summary"]["handover_files"], 10)
        self.assertGreater(idx["summary"]["docs_files"], 10)


if __name__ == "__main__":
    unittest.main()
