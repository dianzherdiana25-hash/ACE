"""Uji unit untuk pipeline terpadu tools/kbm_pipeline.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.kbm_pack_check import PNG_MAGIC
from tools.kbm_pipeline import KBM_PIPELINE_SCHEMA, KbmPipelineError, run_pipeline
from tools.kbm_split import KbmSplitError

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "kbm_pipeline.py"


def _words(n: int, prefix: str = "kata") -> str:
    return " ".join(f"{prefix}{i}" for i in range(1, n + 1))


class KbmPipelineTests(unittest.TestCase):
    """Menguji alur hulu-ke-hilir kbm_split + kbm_pack_check tanpa duplikasi logika."""

    def test_valid_intact_manuscript_passes_end_to_end_cli_and_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            manuscript = tmp_dir / "naskah.md"
            pkg_dir = tmp_dir / "paket"
            pkg_dir.mkdir()
            (pkg_dir / "cover.png").write_bytes(PNG_MAGIC + b"\x00" * 32)

            manuscript.write_text(
                "\n".join(
                    [
                        "# Bab 1: Awal Perjalanan",
                        _words(120, "satu"),
                        "",
                        "# Bab 2: Persimpangan",
                        _words(130, "dua"),
                        "",
                        "# Bab 3: Penutup",
                        _words(125, "tiga"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(manuscript),
                    "--output-dir",
                    str(pkg_dir),
                    "--min-words",
                    "100",
                    "--min-bytes",
                    "400",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["schema"], KBM_PIPELINE_SCHEMA)
            self.assertTrue(report["passed"])
            self.assertTrue(report["split_clean"])
            self.assertTrue(report["pack_valid"])
            self.assertIsNone(report["failed_stage"])
            self.assertEqual(report["short_chapters"], [])
            self.assertEqual(report["split"]["chapter_count"], 3)
            self.assertEqual(report["pack_check"]["chapter_count"], 3)
            self.assertEqual(report["pack_check"]["cover"]["format"], "png")

    def test_manuscript_with_short_chapter_fails_at_check_stage_pointing_to_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            manuscript = tmp_dir / "naskah_pendek.md"
            pkg_dir = tmp_dir / "paket"
            cover_src = tmp_dir / "sampul.png"
            cover_src.write_bytes(PNG_MAGIC + b"\x00" * 24)

            manuscript.write_text(
                "\n".join(
                    [
                        "# Bab 1: Pembukaan Panjang",
                        _words(120, "awal"),
                        "",
                        "# Bab 2: Bab Terlalu Pendek",
                        "Hanya lima kata saja.",
                        "",
                        "# Bab 3: Pemulihan",
                        _words(120, "akhir"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(manuscript),
                    "--output-dir",
                    str(pkg_dir),
                    "--cover-file",
                    str(cover_src),
                    "--min-words",
                    "100",
                    "--min-bytes",
                    "500",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["passed"])
            self.assertFalse(report["pack_valid"])
            self.assertEqual(report["failed_stage"], "check")
            self.assertEqual(report["short_chapters"], ["bab_02_bab-terlalu-pendek.md"])
            self.assertEqual(
                report["pack_check"]["short_chapters"],
                ["bab_02_bab-terlalu-pendek.md"],
            )
            err_files = [e.get("file") for e in report["pack_check"]["errors"]]
            self.assertIn("bab_02_bab-terlalu-pendek.md", err_files)

    def test_missing_cover_fails_check_stage_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            manuscript = tmp_dir / "naskah.md"
            pkg_dir = tmp_dir / "paket_tanpa_cover"
            manuscript.write_text("# Bab 1: Satu\n" + _words(110) + "\n", encoding="utf-8")

            report = run_pipeline(manuscript, pkg_dir, min_words=100, min_bytes=400)
            self.assertFalse(report["passed"])
            self.assertTrue(report["split_clean"])
            self.assertFalse(report["pack_valid"])
            self.assertEqual(report["failed_stage"], "check")
            codes = [e["code"] for e in report["pack_check"]["errors"]]
            self.assertIn("missing_cover", codes)

    def test_invalid_inputs_raise_and_cli_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            with self.assertRaises(KbmSplitError):
                run_pipeline(tmp_dir / "tidak_ada.md", tmp_dir / "out")

            manuscript = tmp_dir / "ok.md"
            manuscript.write_text("# Bab 1: Satu\n" + _words(20) + "\n", encoding="utf-8")
            with self.assertRaises(KbmPipelineError):
                run_pipeline(manuscript, tmp_dir / "out", cover_source=tmp_dir / "no_cover.png")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(tmp_dir / "tidak_ada.md"), "--output-dir", str(tmp_dir / "out")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
