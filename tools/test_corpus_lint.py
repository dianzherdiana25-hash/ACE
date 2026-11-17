"""Uji unit untuk perkakas linter corpus JSONL tools/corpus_lint.py."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.corpus_lint import InvalidInputError, lint_file, lint_lines, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def _row(
    item_id: str = "w4-code-001",
    *,
    kind: str = "episode",
    task_kind: str = "code",
    instruction: str = (
        "Buat fungsi Python hitung_rata(angka: list[int]) -> float dengan kasus tepi kosong. "
        "Sertakan docstring Bahasa Indonesia."
    ),
) -> str:
    return json.dumps(
        {
            "id": item_id,
            "kind": kind,
            "task_kind": task_kind,
            "instruction": instruction,
        },
        ensure_ascii=False,
    )


class CorpusLintTests(unittest.TestCase):
    """Kumpulan pengujian validasi schema, prefix, docstring, dan mode --frozen."""

    def test_01_valid_code_and_language_corpus_passes(self) -> None:
        lines = [
            _row("w4-code-001", task_kind="code"),
            _row(
                "w4-code-002",
                task_kind="code",
                instruction="Buat fungsi saring(data) untuk daftar kosong. Sertakan docstring Bahasa Indonesia.",
            ),
        ]
        report = lint_lines(lines, prefixes=["w4-code-"])
        self.assertTrue(report["valid"])
        self.assertEqual(report["total_lines"], 2)
        self.assertEqual(report["violation_count"], 0)

    def test_02_invalid_json_line_reported(self) -> None:
        report = lint_lines(['{"id": "w4-code-001"'], prefixes=["w4-code-"])
        self.assertFalse(report["valid"])
        self.assertEqual(report["violations"][0]["code"], "invalid_json")
        self.assertEqual(report["violations"][0]["line"], 1)

    def test_03_non_dict_json_rejected(self) -> None:
        report = lint_lines(['["bukan", "objek"]'])
        self.assertFalse(report["valid"])
        self.assertEqual(report["violations"][0]["code"], "not_json_object")

    def test_04_schema_missing_and_extra_fields_rejected(self) -> None:
        missing_row = json.dumps({"id": "w4-lang-001", "kind": "episode", "task_kind": "language"})
        extra_row = json.dumps(
            {
                "id": "w4-lang-002",
                "kind": "episode",
                "task_kind": "language",
                "instruction": "Tulis ringkasan singkat.",
                "score": 90,
            }
        )
        report = lint_lines([missing_row, extra_row])
        self.assertFalse(report["valid"])
        codes = [v["code"] for v in report["violations"]]
        self.assertIn("invalid_schema", codes)
        self.assertEqual(codes.count("invalid_schema"), 2)

    def test_05_wrong_kind_rejected(self) -> None:
        report = lint_lines([_row("w4-lang-001", kind="task", task_kind="language")])
        self.assertFalse(report["valid"])
        self.assertEqual(report["violations"][0]["code"], "invalid_kind")

    def test_06_wrong_task_kind_rejected(self) -> None:
        report = lint_lines([_row("w4-code-001", task_kind="math")])
        self.assertFalse(report["valid"])
        self.assertEqual(report["violations"][0]["code"], "invalid_task_kind")

    def test_07_duplicate_id_rejected(self) -> None:
        lines = [_row("w4-code-001"), _row("w4-code-001")]
        report = lint_lines(lines)
        self.assertFalse(report["valid"])
        self.assertEqual(report["violations"][0]["code"], "duplicate_id")

    def test_08_prefix_mismatch_and_non_sequential_id_rejected(self) -> None:
        lines = [
            _row("w4-code-001"),
            _row("w4-code-003"),
            _row("w4-lang-001", task_kind="language", instruction="Tulis pesan resmi."),
        ]
        report = lint_lines(lines, prefixes=["w4-code-"])
        self.assertFalse(report["valid"])
        codes = [v["code"] for v in report["violations"]]
        self.assertEqual(codes, ["non_sequential_id", "invalid_id_prefix"])

    def test_09_multiple_prefixes_sequential_per_prefix_passes(self) -> None:
        lines = [
            _row("tr-code-001", task_kind="code"),
            _row("tr-code-002", task_kind="code"),
            _row("tr-lang-001", task_kind="language", instruction="Tulis pengumuman resmi 3 kalimat."),
            _row("tr-lang-002", task_kind="language", instruction="Tulis ringkasan singkat 40 kata."),
        ]
        report = lint_lines(lines, prefixes=["tr-code-", "tr-lang-"])
        self.assertTrue(report["valid"])

    def test_10_code_missing_docstring_phrase_rejected(self) -> None:
        lines = [_row("w4-code-001", task_kind="code", instruction="Buat fungsi Python tambah(a, b).")]
        report = lint_lines(lines, prefixes=["w4-code-"])
        self.assertFalse(report["valid"])
        self.assertEqual(report["violations"][0]["code"], "missing_code_docstring_phrase")

    def test_11_language_without_docstring_phrase_allowed(self) -> None:
        lines = [
            _row(
                "w4-lang-001",
                task_kind="language",
                instruction="Tulis catatan rilis tepat 40 kata tanpa kata terlarang.",
            )
        ]
        report = lint_lines(lines, prefixes=["w4-lang-"])
        self.assertTrue(report["valid"])

    def test_12_frozen_60_char_prefix_overlap_rejected_and_distinct_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            frozen_a = tmp_dir / "frozen_a.jsonl"
            frozen_b = tmp_dir / "frozen_b.jsonl"
            cand_bad = tmp_dir / "cand_bad.jsonl"
            cand_ok = tmp_dir / "cand_ok.jsonl"

            shared_60 = "Tulis fungsi Python unik_stabil(data) yang mempertahankan urutan awal"
            frozen_a.write_text(
                _row("w1-code-001", instruction=f"{shared_60} elemen. Sertakan docstring Bahasa Indonesia.")
                + "\n",
                encoding="utf-8",
            )
            frozen_b.write_text(
                _row(
                    "w1-lang-001",
                    task_kind="language",
                    instruction="Tulis pengumuman singkat penutupan layanan gedung utama akhir pekan ini.",
                )
                + "\n",
                encoding="utf-8",
            )
            cand_bad.write_text(
                _row(
                    "w4-code-001",
                    instruction=f"{shared_60} versi baru. Sertakan docstring Bahasa Indonesia.",
                )
                + "\n",
                encoding="utf-8",
            )
            cand_ok.write_text(
                _row(
                    "w4-code-001",
                    instruction="Buat fungsi Python cari_puncak(nums) dengan kasus tepi. Sertakan docstring Bahasa Indonesia.",
                )
                + "\n",
                encoding="utf-8",
            )

            bad_report = lint_file(cand_bad, prefixes=["w4-code-"], frozen_paths=[frozen_a, frozen_b])
            self.assertFalse(bad_report["valid"])
            self.assertEqual(bad_report["violations"][0]["code"], "frozen_prefix_overlap")

            ok_report = lint_file(cand_ok, prefixes=["w4-code-"], frozen_paths=[frozen_a, frozen_b])
            self.assertTrue(ok_report["valid"])

    def test_13_empty_corpus_reported_as_violation_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_path = Path(tmp) / "empty.jsonl"
            empty_path.write_text("", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main([str(empty_path)])
            self.assertEqual(rc, 1)
            report = json.loads(buf.getvalue())
            self.assertEqual(report["violations"][0]["code"], "empty_corpus")

    def test_14_cli_exit_codes_0_1_2(self) -> None:
        script = REPO_ROOT / "tools" / "corpus_lint.py"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            ok_path = tmp_dir / "ok.jsonl"
            bad_path = tmp_dir / "bad.jsonl"
            frozen_path = tmp_dir / "frozen.jsonl"

            ok_path.write_text(_row("w4-code-001") + "\n", encoding="utf-8")
            bad_path.write_text(_row("w4-code-002") + "\n", encoding="utf-8")
            frozen_path.write_text(
                _row(
                    "w1-lang-001",
                    task_kind="language",
                    instruction="Tulis ringkasan berita perubahan jadwal kereta komuter wilayah selatan.",
                )
                + "\n",
                encoding="utf-8",
            )

            p0 = subprocess.run(
                [sys.executable, str(script), str(ok_path), "--prefix", "w4-code-", "--frozen", str(frozen_path)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p0.returncode, 0)
            self.assertTrue(json.loads(p0.stdout)["valid"])

            p1 = subprocess.run(
                [sys.executable, str(script), str(bad_path), "--prefix", "w4-code-"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p1.returncode, 1)
            self.assertFalse(json.loads(p1.stdout)["valid"])

            p2 = subprocess.run(
                [sys.executable, str(script), str(tmp_dir / "tidak_ada.jsonl")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p2.returncode, 2)
            self.assertIn("Error:", p2.stderr)

    def test_15_invalid_frozen_file_raises_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp) / "cand.jsonl"
            cand.write_text(_row("w4-code-001") + "\n", encoding="utf-8")
            with self.assertRaises(InvalidInputError):
                lint_file(cand, frozen_paths=[Path(tmp) / "missing_frozen.jsonl"])

    def test_16_negative_control_official_evo0005_shape_passes(self) -> None:
        # Struktur kontrol negatif setara berkas resmi EVO_0005_CORPUS_V1.jsonl (16 baris, 4 prefix).
        sample = [
            _row("tr-code-001", task_kind="code", instruction="Tulis fungsi Python `hitung_umur(a, b)`. Sertakan docstring Bahasa Indonesia."),
            _row("tr-code-002", task_kind="code", instruction="Tulis fungsi Python `mode_terbanyak(x)`. Sertakan docstring Bahasa Indonesia."),
            _row("tr-lang-001", task_kind="language", instruction="Tulis satu paragraf Bahasa Indonesia (3-4 kalimat) yang menjelaskan manfaat bank sampah."),
            _row("ho-code-001", task_kind="code", instruction="Tulis fungsi Python `pecah_uang(jumlah)`. Sertakan docstring Bahasa Indonesia."),
            _row("ho-lang-001", task_kind="language", instruction="Tulis satu paragraf Bahasa Indonesia (3-4 kalimat) yang menjelaskan mengapa posyandu penting."),
        ]
        report = lint_lines(sample, prefixes=["tr-code-", "tr-lang-", "ho-code-", "ho-lang-"])
        self.assertTrue(report["valid"])
        self.assertEqual(report["violation_count"], 0)

    def test_17_regression_non_string_unhashable_fields_from_fuzz(self) -> None:
        cases = [
            (
                {"id": {"nested": 1}, "kind": "episode", "task_kind": "code", "instruction": "Buat fungsi. Sertakan docstring Bahasa Indonesia."},
                ["invalid_id"],
            ),
            (
                {"id": ["w4-code-001"], "kind": "episode", "task_kind": "code", "instruction": "Buat fungsi. Sertakan docstring Bahasa Indonesia."},
                ["invalid_id"],
            ),
            (
                {"id": "w4-code-001", "kind": "episode", "task_kind": ["code"], "instruction": "Buat fungsi. Sertakan docstring Bahasa Indonesia."},
                ["invalid_task_kind"],
            ),
            (
                {"id": "w4-code-002", "kind": "episode", "task_kind": {"v": "language"}, "instruction": "Tulis satu paragraf."},
                ["invalid_task_kind"],
            ),
            (
                {"id": "w4-lang-001", "kind": {"k": "episode"}, "task_kind": "language", "instruction": ["list"]},
                ["invalid_kind", "invalid_instruction"],
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for idx, (payload, expected_codes) in enumerate(cases, start=1):
                path = Path(tmp) / f"fuzz_case_{idx}.jsonl"
                path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
                report = lint_file(path, prefixes=["w4-code-", "w4-lang-"])
                self.assertFalse(report["valid"])
                actual_codes = [v["code"] for v in report["violations"]]
                for code in expected_codes:
                    self.assertIn(code, actual_codes)


if __name__ == "__main__":
    unittest.main()
