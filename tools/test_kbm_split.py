"""Uji unit untuk pemecah manuskrip KBM tools/kbm_split.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.kbm_split import KbmSplitError, split_manuscript

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "kbm_split.py"


class KbmSplitTests(unittest.TestCase):
    """Menguji pemecahan 3-bab dengan 1 bab di bawah ambang kata."""

    def test_splits_three_chapters_and_flags_one_below_threshold(self) -> None:
        bab1_body = " ".join(["kata"] * 25)
        bab2_body = " ".join(["kalimat"] * 8)  # Di bawah ambang 20
        bab3_body = " ".join(["cerita"] * 30)
        manuscript_text = (
            "Kata pengantar sebelum bab satu.\n\n"
            f"# Bab 1: Awal Perjalanan\n\n{bab1_body}\n\n"
            f"## Bab 2 - Persimpangan\n\n{bab2_body}\n\n"
            f"# Chapter 3: Akhir Musim\n\n{bab3_body}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "manuskrip.md"
            out_dir = tmp_path / "chapters"
            src.write_text(manuscript_text, encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(src),
                    "--output-dir",
                    str(out_dir),
                    "--min-words",
                    "20",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["chapter_count"], 3)
            self.assertEqual(report["below_threshold_count"], 1)
            self.assertEqual(report["min_words"], 20)

            chapters = report["chapters"]
            self.assertEqual([c["word_count"] for c in chapters], [25, 8, 30])
            self.assertEqual([c["below_threshold"] for c in chapters], [False, True, False])
            self.assertEqual(report["below_threshold_files"], [chapters[1]["output_file"]])

            # Pastikan 3 berkas benar-benar tertulis dan berisi teks masing-masing bab
            written_files = sorted(p.name for p in out_dir.iterdir())
            self.assertEqual(len(written_files), 3)
            for ch in chapters:
                content = (out_dir / ch["output_file"]).read_text(encoding="utf-8")
                self.assertIn(ch["title"], content)

            # Mode --strict keluar dengan kode 1 bila ada bab pendek
            proc_strict = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(src),
                    "--output-dir",
                    str(out_dir),
                    "--min-words",
                    "20",
                    "--strict",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_strict.returncode, 1)

    def test_no_chapters_or_missing_file_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            no_chap = Path(tmp) / "flat.md"
            no_chap.write_text("# Pendahuluan saja\nTanpa penanda bab.\n", encoding="utf-8")
            with self.assertRaises(KbmSplitError):
                split_manuscript(no_chap, Path(tmp) / "out")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "/tmp/tidak_ada_manuskrip.md", "--output-dir", tmp],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)

    def test_plain_chapter_markers_without_markdown_hashes(self) -> None:
        manuscript = (
            "Bab 1\n\n"
            + ("kata " * 12)
            + "\n\nBAB 2: Hujan Sore\n\n"
            + ("cerita " * 15)
            + "\n\nChapter 3 - Penutup\n\n"
            + ("akhir " * 10)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "plain.md"
            out_dir = Path(tmp) / "out"
            src.write_text(manuscript, encoding="utf-8")

            report = split_manuscript(src, out_dir, min_words=5)
            self.assertEqual(report["chapter_count"], 3)
            self.assertEqual(
                [c["title"] for c in report["chapters"]],
                ["Bab 1", "Hujan Sore", "Penutup"],
            )
            self.assertEqual([c["word_count"] for c in report["chapters"]], [12, 15, 10])


if __name__ == "__main__":
    unittest.main()
