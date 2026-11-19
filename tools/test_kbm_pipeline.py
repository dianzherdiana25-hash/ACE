"""Uji unit untuk pipeline terpadu tools/kbm_pipeline.py."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.kbm_pack_check import PNG_MAGIC
from tools.kbm_pipeline import (
    KBM_PIPELINE_SCHEMA,
    KBM_UPLOAD_MANIFEST_SCHEMA,
    KbmPipelineError,
    run_pipeline,
)
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

            with self.assertRaises(KbmPipelineError):
                run_pipeline(manuscript, tmp_dir / "out", bundle_dir=tmp_dir / "out")

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(tmp_dir / "tidak_ada.md"), "--output-dir", str(tmp_dir / "out")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("Error:", proc.stderr)

    def test_bundle_dir_stages_upload_manifest_and_blocks_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            manuscript = tmp_dir / "naskah.md"
            pkg_dir = tmp_dir / "paket"
            bundle_dir = tmp_dir / "unggah"
            cover_src = tmp_dir / "sampul.png"
            cover_bytes = PNG_MAGIC + b"\x00" * 40
            cover_src.write_bytes(cover_bytes)

            manuscript.write_text(
                "\n".join(
                    [
                        "# Bab 1: Kabut Pelabuhan",
                        _words(110, "pelabuhan"),
                        "",
                        "# Bab 2: Mercusuar Senja",
                        _words(115, "mercusuar"),
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
                    "--bundle-dir",
                    str(bundle_dir),
                    "--min-words",
                    "100",
                    "--min-bytes",
                    "300",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["bundle"]["staged"])
            manifest_path = bundle_dir / "upload_manifest.json"
            self.assertTrue(manifest_path.is_file())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], KBM_UPLOAD_MANIFEST_SCHEMA)
            self.assertEqual(manifest["chapter_count"], 2)
            self.assertEqual(manifest["total_words"], 225)
            self.assertEqual(
                manifest["cover"]["sha256"],
                hashlib.sha256(cover_bytes).hexdigest(),
            )
            self.assertTrue((bundle_dir / manifest["cover"]["file"]).is_file())
            self.assertEqual(manifest["chapters"][0]["order"], 1)
            self.assertEqual(manifest["chapters"][0]["bundle_file"], "ch_001_kabut-pelabuhan.md")
            ch1_bytes = (bundle_dir / manifest["chapters"][0]["bundle_file"]).read_bytes()
            self.assertEqual(manifest["chapters"][0]["sha256"], hashlib.sha256(ch1_bytes).hexdigest())

            # Jika paket gagal validasi (tanpa sampul), bundle tidak di-stage.
            bad_bundle = tmp_dir / "gagal_unggah"
            fail_report = run_pipeline(
                manuscript,
                tmp_dir / "paket_tanpa_cover",
                min_words=100,
                min_bytes=300,
                bundle_dir=bad_bundle,
            )
            self.assertFalse(fail_report["passed"])
            self.assertFalse(fail_report["bundle"]["staged"])
            self.assertFalse((bad_bundle / "upload_manifest.json").exists())


class TestKbmSuiteV2Wiring(unittest.TestCase):
    """Uji keterhubungan tools/kbm_suite_v2.py ke orkestrator tools/kbm_pipeline.py."""

    @staticmethod
    def _valid_png_bytes() -> bytes:
        import struct
        import zlib
        from tools.cover_check import DEFAULT_RULES

        width = int(DEFAULT_RULES.get("min_width") or 600)
        height = int(DEFAULT_RULES.get("min_height") or 800)
        min_bytes = int(DEFAULT_RULES.get("min_bytes") or 1024)

        def chunk(ctype: bytes, payload: bytes) -> bytes:
            body = ctype + payload
            return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        text_chunk = chunk(b"tEXt", b"Comment\x00" + (b"x" * max(64, min_bytes)))
        idat = chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        iend = chunk(b"IEND", b"")
        return b"\x89PNG\r\n\x1a\n" + ihdr + text_chunk + idat + iend

    def test_qa_v2_passes_distinct_chapters_and_blocks_duplicates(self) -> None:
        from tools import wiring_audit

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cover = root / "sampul.png"
            cover.write_bytes(self._valid_png_bytes())

            ok_ms = root / "naskah_unik.md"
            ok_ms.write_text(
                "# Bab 1: Arah Baru\n" + _words(110, "alfa") + "\n\n"
                "# Bab 2: Langkah Lanjut\n" + _words(115, "beta") + "\n",
                encoding="utf-8",
            )
            proc_ok = subprocess.run(
                [
                    sys.executable, str(SCRIPT), str(ok_ms),
                    "--output-dir", str(root / "out_ok"),
                    "--cover-file", str(cover),
                    "--min-words", "100",
                    "--max-words", "200",
                    "--min-bytes", "100",
                    "--qa-v2",
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(proc_ok.returncode, 0, proc_ok.stderr)
            rep_ok = json.loads(proc_ok.stdout)
            self.assertTrue(rep_ok["passed"])
            self.assertTrue(rep_ok["qa_v2"]["qa_passed"])
            self.assertEqual(rep_ok["qa_v2"]["duplicate_chapter_groups"], [])

            overlong_ms = root / "naskah_panjang.md"
            overlong_ms.write_text(
                "# Bab 1: Pendek\n" + _words(110, "cukup") + "\n\n"
                "# Bab 2: Kepanjangan\n" + _words(165, "panjang") + "\n",
                encoding="utf-8",
            )
            rep_long = run_pipeline(
                overlong_ms, root / "out_long",
                cover_source=cover,
                min_words=100, min_bytes=100, qa_v2=True, max_words=140,
            )
            self.assertFalse(rep_long["passed"])
            self.assertTrue(rep_long["pack_valid"])
            self.assertEqual(rep_long["failed_stage"], "qa_v2")
            self.assertEqual(len(rep_long["qa_v2"]["pacing_violations"]), 1)

        audit = wiring_audit.audit_wiring(REPO_ROOT)
        by_path = {m["path"]: m for m in audit["modules"]}
        self.assertEqual(by_path["tools/kbm_suite_v2.py"]["status"], "WIRED")
        self.assertIn("tools/kbm_pipeline.py", by_path["tools/kbm_suite_v2.py"]["non_test_callers"])


if __name__ == "__main__":
    unittest.main()
