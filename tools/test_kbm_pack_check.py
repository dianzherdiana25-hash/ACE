"""Uji unit untuk pemeriksa paket unggah KBM tools/kbm_pack_check.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.kbm_pack_check import JPEG_MAGIC, KbmPackCheckError, PNG_MAGIC, check_package

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "kbm_pack_check.py"


def _make_package(
    pkg_dir: Path,
    *,
    cover_name: str | None = "cover.png",
    cover_bytes: bytes = PNG_MAGIC + b"fakepngpayload",
    chapters: dict[str, bytes] | None = None,
) -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    if cover_name is not None:
        (pkg_dir / cover_name).write_bytes(cover_bytes)
    items = (
        chapters
        if chapters is not None
        else {
            "bab_01_awal.md": b"A" * 120,
            "bab_02_tengah.md": b"B" * 120,
            "bab_03_akhir.md": b"C" * 120,
        }
    )
    for name, content in items.items():
        (pkg_dir / name).write_bytes(content)


class KbmPackCheckTests(unittest.TestCase):
    """Menguji paket utuh (PNG & JPEG), sampul hilang/palsu, celah nomor, dan bab pendek."""

    def test_valid_package_png_and_jpeg_passes_exit_0(self) -> None:
        for cname, magic in (("cover.png", PNG_MAGIC), ("cover.jpg", JPEG_MAGIC)):
            with tempfile.TemporaryDirectory() as tmp, self.subTest(cover=cname):
                pkg = Path(tmp) / "pkg"
                _make_package(pkg, cover_name=cname, cover_bytes=magic + b"\x00" * 16)
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT), str(pkg), "--min-bytes", "100"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                report = json.loads(proc.stdout)
                self.assertTrue(report["valid"])
                self.assertEqual(report["chapter_count"], 3)
                self.assertTrue(report["cover"]["valid"])
                self.assertEqual(report["missing_numbers"], [])

    def test_missing_and_invalid_cover_fail_with_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg_missing = Path(tmp) / "missing_cover"
            _make_package(pkg_missing, cover_name=None)
            p1 = subprocess.run(
                [sys.executable, str(SCRIPT), str(pkg_missing), "--min-bytes", "100"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p1.returncode, 1)
            r1 = json.loads(p1.stdout)
            self.assertFalse(r1["valid"])
            self.assertEqual(r1["errors"][0]["code"], "missing_cover")

            pkg_fake = Path(tmp) / "fake_cover"
            _make_package(pkg_fake, cover_name="cover.jpg", cover_bytes=b"NOT_A_JPEG_IMAGE")
            p2 = subprocess.run(
                [sys.executable, str(SCRIPT), str(pkg_fake), "--min-bytes", "100"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p2.returncode, 1)
            r2 = json.loads(p2.stdout)
            self.assertFalse(r2["valid"])
            self.assertEqual(r2["errors"][0]["code"], "invalid_cover_header")

    def test_chapter_numbering_gap_and_duplicate_fail_with_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg_gap = Path(tmp) / "gap"
            _make_package(
                pkg_gap,
                chapters={
                    "bab_01.md": b"A" * 120,
                    "bab_03.md": b"C" * 120,
                },
            )
            p_gap = subprocess.run(
                [sys.executable, str(SCRIPT), str(pkg_gap), "--min-bytes", "100"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_gap.returncode, 1)
            r_gap = json.loads(p_gap.stdout)
            self.assertEqual(r_gap["missing_numbers"], [2])
            self.assertIn("chapter_numbering_gap", [e["code"] for e in r_gap["errors"]])

            pkg_dup = Path(tmp) / "dup"
            _make_package(
                pkg_dup,
                chapters={
                    "bab_01_a.md": b"A" * 120,
                    "bab_01_b.md": b"B" * 120,
                },
            )
            r_dup = check_package(pkg_dup, min_bytes=100)
            self.assertFalse(r_dup["valid"])
            self.assertEqual(r_dup["duplicate_numbers"], [1])

    def test_short_chapter_below_min_bytes_fails_with_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "short"
            _make_package(
                pkg,
                chapters={
                    "bab_01.md": b"A" * 150,
                    "bab_02.md": b"pendek",
                },
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(pkg), "--min-bytes", "100"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["valid"])
            self.assertEqual(report["short_chapters"], ["bab_02.md"])
            self.assertIn("chapter_too_short", [e["code"] for e in report["errors"]])

    def test_missing_package_dir_exits_2(self) -> None:
        with self.assertRaises(KbmPackCheckError):
            check_package(Path("/tmp/tidak_ada_kbm_pack"))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "/tmp/tidak_ada_kbm_pack"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
