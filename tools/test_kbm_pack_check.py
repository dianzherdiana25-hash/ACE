"""Uji unit untuk pemeriksa paket unggah KBM tools/kbm_pack_check.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.kbm_pack_check import JPEG_MAGIC, KbmPackCheckError, PNG_MAGIC, check_manuscript, check_package

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


class ManuscriptPackCheckTests(unittest.TestCase):
    """Uji ambang kata isi, kelengkapan urutan, dan gerbang staging yang sama."""

    def _write_manuscript(self, path, numbers=range(1, 31), *, short_chapter=None):
        sections = []
        for number in numbers:
            words = 999 if number == short_chapter else 1000
            sections.append(f"# Bab {number}: Judul yang panjang\n\n" + "kata " * words)
        path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")

    def _run_cli(self, manuscript, *options):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(manuscript), *options],
            capture_output=True,
            text=True,
        )

    def test_complete_manuscript_human_report_counts_all_chapter_bodies(self):
        with tempfile.TemporaryDirectory() as tmp:
            manuscript = Path(tmp) / "naskah.md"
            self._write_manuscript(manuscript)
            before = manuscript.read_bytes()
            result = self._run_cli(manuscript)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.splitlines()
            self.assertEqual(lines[0], "LULUS — 30/30 bab")
            self.assertEqual(lines[1:], [f"Bab {number}: 1000 kata — LULUS" for number in range(1, 31)])
            self.assertEqual(manuscript.read_bytes(), before)
            self.assertEqual(list(Path(tmp).iterdir()), [manuscript])

    def test_short_chapter_excludes_title_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            manuscript = Path(tmp) / "naskah.md"
            self._write_manuscript(manuscript, short_chapter=19)
            result = self._run_cli(manuscript, "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["valid"])
            failures = [chapter for chapter in report["chapters"] if not chapter["valid"]]
            self.assertEqual([(item["chapter_number"], item["word_count"]) for item in failures], [(19, 999)])
            self.assertIn("Bab 19: 999 kata — GAGAL", self._run_cli(manuscript).stdout)

    def test_missing_terminal_chapter_is_reported_with_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            manuscript = Path(tmp) / "naskah.md"
            self._write_manuscript(manuscript, range(1, 30))
            result = self._run_cli(manuscript, "--json")
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing_numbers"], [30])

    def test_thirty_chapters_with_duplicates_or_wrong_order_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manuscript = Path(tmp) / "naskah.md"
            self._write_manuscript(manuscript, [1, 1, *range(3, 31)])
            report = check_manuscript(manuscript)
            self.assertFalse(report["valid"])
            self.assertEqual(report["duplicate_numbers"], [1])
            self.assertEqual(report["missing_numbers"], [2])
            self._write_manuscript(manuscript, [2, 1, *range(3, 31)])
            report = check_manuscript(manuscript)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing_numbers"], [])
            self.assertEqual(
                [chapter["chapter_number"] for chapter in report["chapters"] if not chapter["valid"]],
                [2, 1],
            )

    def test_pipeline_pack_uses_manuscript_verdict_before_staging(self):
        pipeline = REPO_ROOT / "tools" / "kbm_pipeline.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manuscript = root / "naskah.md"
            cover = root / "cover.png"
            cover.write_bytes(PNG_MAGIC + b"fakepngpayload")
            for expected_exit, numbers in ((0, range(1, 31)), (1, range(1, 30))):
                with self.subTest(expected_exit=expected_exit):
                    self._write_manuscript(manuscript, numbers)
                    bundle = root / f"bundle-{expected_exit}"
                    result = subprocess.run(
                        [sys.executable, str(pipeline), str(manuscript), "--pack",
                         "--output-dir", str(root / f"split-{expected_exit}"),
                         "--cover-file", str(cover), "--bundle-dir", str(bundle)],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, expected_exit, result.stderr)
                    report = json.loads(result.stdout)
                    expected = check_manuscript(manuscript)
                    expected.pop("source")
                    self.assertEqual(report["manuscript_check"], expected)
                    self.assertEqual((bundle / "upload_manifest.json").is_file(), not expected_exit)
                    if expected_exit:
                        self.assertEqual(report["failed_stage"], "manuscript")


if __name__ == "__main__":
    unittest.main()
