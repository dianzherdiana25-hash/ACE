#!/usr/bin/env python3
"""Tes unit untuk `tools/candidate_census.py` (Gelombang C1).

Memastikan sensus kandidat menghitung sebaran `task_kind`, sebaran kendala,
menangkap duplikat `id` maupun duplikat instruksi, serta merangkum verdict
kesiapan beserta alasannya secara deterministik dan baca-saja.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.candidate_census import CENSUS_SCHEMA, census_file, census_lines, render_markdown


class CandidateCensusTests(unittest.TestCase):
    def _clean_rows(self) -> list[dict[str, str]]:
        return [
            {
                "id": "cand-lang-001",
                "kind": "episode",
                "task_kind": "language",
                "instruction": (
                    "Tulis ringkasan tepat 40 kata dalam tiga kalimat Bahasa Indonesia "
                    "yang wajib memuat frasa 'audit berjenjang', dilarang memakai kata 'mungkin', "
                    "dan menempatkan fakta anggaran sebelum fakta jadwal."
                ),
            },
            {
                "id": "cand-code-001",
                "kind": "episode",
                "task_kind": "code",
                "instruction": (
                    "Tulis fungsi Python `gabung_interval(intervals)` dengan kompleksitas waktu O(n log n), "
                    "tanpa rekursi, menangani input kosong dan interval bersentuhan, serta sertakan docstring Bahasa Indonesia."
                ),
            },
        ]

    def test_clean_fixture_reports_ready_with_task_kind_and_constraint_distribution(self) -> None:
        lines = [json.dumps(row, ensure_ascii=False) for row in self._clean_rows()]
        report = census_lines(lines, source_name="clean.jsonl")

        self.assertEqual(report["schema"], CENSUS_SCHEMA)
        self.assertEqual(report["valid_records"], 2)
        self.assertEqual(report["task_kind_counts"], {"code": 1, "language": 1})
        self.assertEqual(report["duplicates"]["duplicate_id_count"], 0)
        self.assertEqual(report["duplicates"]["duplicate_instruction_count"], 0)
        self.assertGreaterEqual(report["constraint_stats"]["min"], 3)
        self.assertTrue(report["readiness"]["ready"])
        self.assertEqual(report["readiness"]["verdict"], "LAYAK")

    def test_embedded_duplicate_id_is_caught_and_explained_in_verdict(self) -> None:
        rows = self._clean_rows()
        rows.append(
            {
                "id": "cand-lang-001",  # duplikat tertanam
                "kind": "episode",
                "task_kind": "language",
                "instruction": (
                    "Susun paragraf maksimal 50 kata dalam dua kalimat Bahasa Indonesia, "
                    "wajib memuat frasa 'batas aman' dan dilarang memakai angka."
                ),
            }
        )
        lines = [json.dumps(row, ensure_ascii=False) for row in rows]
        report = census_lines(lines, source_name="dup_id.jsonl")

        self.assertEqual(report["duplicates"]["duplicate_id_count"], 1)
        self.assertEqual(report["duplicates"]["duplicate_ids"][0]["id"], "cand-lang-001")
        self.assertEqual(report["duplicates"]["duplicate_ids"][0]["lines"], [1, 3])
        self.assertFalse(report["readiness"]["ready"])
        self.assertEqual(report["readiness"]["verdict"], "BELUM_LAYAK")
        joined_reasons = " ".join(report["readiness"]["reasons"]).lower()
        self.assertIn("duplikat id", joined_reasons)
        self.assertIn("cand-lang-001", joined_reasons)

    def test_embedded_duplicate_instruction_is_caught_even_with_different_id_and_whitespace(self) -> None:
        rows = self._clean_rows()
        rows.append(
            {
                "id": "cand-lang-002",
                "kind": "episode",
                "task_kind": "language",
                "instruction": "  " + rows[0]["instruction"].upper() + "  ",
            }
        )
        lines = [json.dumps(row, ensure_ascii=False) for row in rows]
        report = census_lines(lines, source_name="dup_instr.jsonl")

        self.assertEqual(report["duplicates"]["duplicate_id_count"], 0)
        self.assertEqual(report["duplicates"]["duplicate_instruction_count"], 1)
        self.assertFalse(report["readiness"]["ready"])
        self.assertEqual(report["readiness"]["verdict"], "BELUM_LAYAK")
        joined_reasons = " ".join(report["readiness"]["reasons"]).lower()
        self.assertIn("duplikat instruksi", joined_reasons)

    def test_zero_constraint_and_invalid_json_mark_not_ready(self) -> None:
        lines = [
            json.dumps(
                {
                    "id": "bare-001",
                    "kind": "episode",
                    "task_kind": "language",
                    "instruction": "Ceritakan tentang matahari pagi.",
                }
            ),
            "{broken-json",
        ]
        report = census_lines(lines, source_name="broken.jsonl")
        self.assertEqual(report["invalid_line_count"], 1)
        self.assertEqual(report["constraint_stats"]["zero_constraint_count"], 1)
        self.assertFalse(report["readiness"]["ready"])
        joined = " ".join(report["readiness"]["reasons"]).lower()
        self.assertIn("tidak sah", joined)
        self.assertIn("tanpa kendala", joined)

    def test_cli_outputs_json_and_markdown_without_modifying_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cand_file = tmp_dir / "candidates.jsonl"
            rows = self._clean_rows()
            rows.append(dict(rows[0]))  # duplikat id + instruksi
            original_text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
            cand_file.write_text(original_text, encoding="utf-8")

            json_out = tmp_dir / "out.json"
            md_out = tmp_dir / "out.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.candidate_census",
                    str(cand_file),
                    "--json-out",
                    str(json_out),
                    "--markdown-out",
                    str(md_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertEqual(cand_file.read_text(encoding="utf-8"), original_text)

            data = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(data["readiness"]["verdict"], "BELUM_LAYAK")
            self.assertEqual(data["duplicates"]["duplicate_id_count"], 1)
            md_text = md_out.read_text(encoding="utf-8")
            self.assertIn("BELUM_LAYAK", md_text)
            self.assertIn("duplikat id", md_text.lower())

            # Pastikan fungsi render_markdown deterministik terhadap laporan berkas
            rep = census_file(cand_file)
            self.assertEqual(render_markdown([rep]), md_text)


if __name__ == "__main__":
    unittest.main()
