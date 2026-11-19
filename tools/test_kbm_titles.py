"""Periksa laporan kedua format dan kompatibilitas katalog jadwal."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tools.kbm_schedule import build_schedule
from tools.kbm_titles import KbmTitlesError, TITLE_REPORT_SCHEMA, build_report, main


class KbmTitlesTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / "state.json"
        self.catalog = [
            {
                "id": "seri_fajar",
                "title": "Cahaya | Fajar <Timur>",
                "status": "naskah",
                "completed_chapters": 2,
                "total_chapters": 5,
                "total_words": 2400,
            },
            {
                "id": "seri_teluk",
                "title": "Teluk Senja",
                "status": "cek",
                "completed_chapters_list": [1, 3, 4],
                "total_chapters": 4,
                "total_words": 4150,
            },
        ]
        self.write_catalog(self.catalog)

    def write_catalog(self, titles: list[dict]) -> None:
        self.state.write_text(
            json.dumps({"serials": titles, "default_start_date": "2026-11-01"}),
            encoding="utf-8",
        )

    def cli(self, report_format: str):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main([str(self.state), "--format", report_format])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_two_title_reports_share_totals_and_preserve_source(self) -> None:
        before = self.state.read_bytes()
        status, output, error = self.cli("json")
        self.assertEqual((status, error), (0, ""))
        report = json.loads(output)
        self.assertEqual(report["schema"], TITLE_REPORT_SCHEMA)
        self.assertEqual(report["summary"], {
            "total_serials": 2,
            "completed_chapters": 5,
            "total_chapters": 9,
            "total_words": 6550,
            "by_status": {"riset": 0, "naskah": 1, "cek": 1, "paket": 0, "terbit": 0},
        })
        self.assertEqual(
            [(item["id"], item["status"], item["completed_chapters"]) for item in report["serials"]],
            [("seri_fajar", "naskah", 2), ("seri_teluk", "cek", 3)],
        )
        status, output, error = self.cli("markdown")
        self.assertEqual((status, error), (0, ""))
        self.assertIn("2 judul · 5/9 bab selesai · 6550 kata", output)
        self.assertIn("Cahaya &#124; Fajar &lt;Timur&gt; | naskah | 2/5 | 2400 |", output)
        self.assertIn("| Teluk Senja | cek | 3/4 | 4150 |", output)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(list(self.state.parent.iterdir()), [self.state])

    def test_catalog_remains_usable_by_existing_schedule(self) -> None:
        schedule = build_schedule(self.state, as_of_date="2026-11-10")
        report = build_report(self.state)
        self.assertEqual(
            [entry["completed_count"] for entry in schedule["serials"]],
            [entry["completed_chapters"] for entry in report["serials"]],
        )

    def test_invalid_syntax_utf8_and_duplicate_keys_report_failure(self) -> None:
        for payload in (b"{", b"\xff", b'{"serials": [], "serials": []}'):
            with self.subTest(payload=payload):
                self.state.write_bytes(payload)
                status, output, error = self.cli("json")
                self.assertEqual((status, output), (2, ""))
                self.assertIn("Berkas state KBM tidak sah", error)
                self.assertEqual(self.state.read_bytes(), payload)

    def test_semantically_invalid_rows_are_reported(self) -> None:
        for fields, message in (
            ({"status": "scheduled"}, "Status yang sah"),
            ({"total_words": -1}, "total_words"),
            ({"total_chapters": 0}, "total_chapters"),
            ({"completed_chapters": True}, "completed_chapters"),
            ({"completed_chapters": None}, "bab selesai wajib ada"),
            ({"completed_chapters_list": [1, 1]}, "Nomor bab selesai duplikat"),
            ({"completed_chapters_list": [1]}, "tidak cocok dengan daftar"),
            ({"completed_chapters_list": [1, 6]}, "rentang 1..5"),
            ({"title": "Baris\nbaru"}, "teks satu baris"),
        ):
            with self.subTest(fields=fields):
                self.write_catalog([{**self.catalog[0], **fields}])
                with self.assertRaisesRegex(KbmTitlesError, message):
                    build_report(self.state)

    def test_duplicate_serial_id_is_rejected(self) -> None:
        self.write_catalog([self.catalog[0], {**self.catalog[1], "id": " seri_fajar "}])
        with self.assertRaisesRegex(KbmTitlesError, "ID serial duplikat"):
            build_report(self.state)

    def test_empty_list_is_valid_before_titles_are_registered(self) -> None:
        self.state.write_text("[]", encoding="utf-8")
        report = build_report(self.state)
        self.assertEqual(report["serials"], [])
        self.assertEqual(report["summary"]["total_words"], 0)


if __name__ == "__main__":
    unittest.main()
