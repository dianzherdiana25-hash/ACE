#!/usr/bin/env python3
"""Tes unit untuk `tools/organ_forensics.py` (Gelombang C2).

Memverifikasi ekstraksi kejadian jatuh/restart dari snapshot log teks secara
baca-saja, akurasi cap waktu, jarak waktu antar-jatuh, serta baris konteks
terakhir tepat sebelum kejadian jatuh.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.organ_forensics import (
    ORGAN_FORENSICS_SCHEMA,
    analyze_log_file,
    analyze_log_lines,
    render_markdown,
)


class OrganForensicsTests(unittest.TestCase):
    def _two_crash_fixture_lines(self) -> list[str]:
        return [
            "2026-11-19T08:00:00Z INFO ace-brain.service booting llama-server on port 8081",
            "2026-11-19T08:01:10Z INFO ace-brain.service slot 0 prompt eval started (ctx=4096)",
            "2026-11-19T08:01:25Z WARN ace-brain.service rss memory climbed to 7.4 GiB",
            "2026-11-19T08:01:30Z ERROR ace-brain.service Out of memory: Killed process 4120 (llama-server)",
            "2026-11-19T08:02:00Z INFO ace-brain.service healthy after manual recovery",
            "2026-11-19T08:06:10Z INFO ace-brain.service slot 1 evaluating batch #19",
            "2026-11-19T08:06:28Z WARN ace-brain.service kv cache allocation spike detected",
            "2026-11-19T08:06:30Z ERROR ace-brain.service Main process exited, code=killed, status=11/SEGV",
            "2026-11-19T08:06:35Z INFO systemd[1] ace-brain.service: Scheduled restart job, restart counter is at 2.",
        ]

    def test_extracts_two_embedded_crashes_with_timestamps_interval_and_context(self) -> None:
        report = analyze_log_lines(
            self._two_crash_fixture_lines(),
            source_name="fixture.log",
            context_lines=2,
        )

        self.assertEqual(report["schema"], ORGAN_FORENSICS_SCHEMA)
        self.assertEqual(report["crash_count"], 2)
        self.assertEqual(report["restart_count"], 1)
        self.assertEqual(report["incident_count"], 3)

        crashes = [ev for ev in report["incidents"] if ev["severity"] == "crash"]
        self.assertEqual(len(crashes), 2)

        # Kejadian jatuh pertama (OOM)
        self.assertEqual(crashes[0]["category"], "oom_kill")
        self.assertEqual(crashes[0]["timestamp_raw"], "2026-11-19T08:01:30Z")
        self.assertEqual(crashes[0]["line_number"], 4)
        self.assertEqual(crashes[0]["organ"], "ace-brain.service")
        self.assertEqual(
            [c["line_number"] for c in crashes[0]["context_before"]],
            [2, 3],
        )
        self.assertIn("7.4 GiB", crashes[0]["context_before"][1]["text"])

        # Kejadian jatuh kedua (exit failure / SEGV -> crash_signal or exit_failure)
        self.assertEqual(crashes[1]["timestamp_raw"], "2026-11-19T08:06:30Z")
        self.assertEqual(crashes[1]["line_number"], 8)
        self.assertEqual(
            [c["line_number"] for c in crashes[1]["context_before"]],
            [6, 7],
        )
        self.assertIn("kv cache allocation spike", crashes[1]["context_before"][1]["text"])

        # Jarak waktu antar dua jatuh = 5 menit tepat = 300.0 detik
        pat = report["inter_failure_pattern_crashes"]
        self.assertEqual(pat["intervals_seconds"], [300.0])
        self.assertEqual(pat["mean_seconds"], 300.0)
        self.assertEqual(pat["median_seconds"], 300.0)

    def test_syslog_and_llama_relative_timestamps_and_clean_log(self) -> None:
        syslog_lines = [
            "Nov 19 10:00:00 host brain_bridge[99]: started",
            "Nov 19 10:00:10 host brain_bridge[99]: Fatal error: socket closed",
            "Nov 19 10:00:40 host brain_bridge[99]: Fatal error: worker died",
        ]
        rep = analyze_log_lines(syslog_lines, context_lines=1, default_year=2026)
        self.assertEqual(rep["crash_count"], 2)
        self.assertEqual(rep["inter_failure_pattern_crashes"]["intervals_seconds"], [30.0])
        self.assertEqual(rep["inter_failure_pattern_crashes"]["pattern_label"], "burst_crash_loop")

        clean = analyze_log_lines(["2026-11-19T09:00:00Z INFO normal tick"], context_lines=2)
        self.assertEqual(clean["incident_count"], 0)
        self.assertEqual(clean["inter_failure_pattern_crashes"]["pattern_label"], "insufficient_events")

    def test_cli_writes_json_and_markdown_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            log_path = tmp_dir / "organ.journal.log"
            raw_content = "\n".join(self._two_crash_fixture_lines()) + "\n"
            log_path.write_text(raw_content, encoding="utf-8")

            json_out = tmp_dir / "forensics.json"
            md_out = tmp_dir / "forensics.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.organ_forensics",
                    str(log_path),
                    "--context-lines",
                    "2",
                    "--json-out",
                    str(json_out),
                    "--markdown-out",
                    str(md_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(log_path.read_text(encoding="utf-8"), raw_content)

            data = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(data["crash_count"], 2)
            md_text = md_out.read_text(encoding="utf-8")
            self.assertIn("2026-11-19T08:01:30Z", md_text)
            self.assertIn("2026-11-19T08:06:30Z", md_text)
            self.assertIn("kv cache allocation spike", md_text)
            self.assertEqual(render_markdown(analyze_log_file(log_path, context_lines=2)), md_text)


if __name__ == "__main__":
    unittest.main()
