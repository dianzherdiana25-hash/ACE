"""Tes sintetik untuk laporan verifikasi pendapatan."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.revenue_report import render_report


def fixture():
    return {
        "schema": "ace.revenue-verification.v1",
        "max_lag_days": 14,
        "events": [
            {
                "id": "event-02", "rail": "kbm_seabank", "status": "COCOK PENUH",
                "issues": [], "verified_rupiah": 15000,
            },
            {
                "id": "event-01", "rail": "kbm_seabank", "status": "HILANG",
                "issues": ["statement_missing"], "verified_rupiah": None,
            },
            {
                "id": "event-03", "rail": "fastwork_bank", "status": "COCOK PENUH",
                "issues": [], "verified_rupiah": 17000,
            },
            {
                "id": "event-04", "rail": "gopay_qris", "status": "SEBAGIAN",
                "issues": ["statement_amount"], "verified_rupiah": None,
            },
            {
                "id": "event-05", "rail": "facebook", "status": "REL TAK TERDAFTAR",
                "issues": ["rail_unknown"], "verified_rupiah": None,
            },
            {
                "id": "event-06", "rail": "gopay_qris", "status": "TIDAK COCOK",
                "issues": ["evidence_inconsistent"], "verified_rupiah": None,
            },
        ],
    }


class RevenueReportTests(unittest.TestCase):
    def test_report_includes_all_findings_and_only_full_amounts(self):
        report = render_report(fixture())

        self.assertIn("Jendela penarikan ke mutasi — 14 hari", report)
        self.assertIn("Total terverifikasi — Rp32.000", report)
        self.assertIn("COCOK PENUH — 2", report)
        for status in ("HILANG", "SEBAGIAN", "REL TAK TERDAFTAR", "TIDAK COCOK"):
            self.assertIn(f"{status} — 1", report)
        self.assertIn("- fastwork&#95;bank — Rp17.000", report)
        self.assertIn("- kbm&#95;seabank — Rp15.000", report)
        self.assertNotIn("- gopay&#95;qris — Rp", report)
        self.assertIn("| event-01 | HILANG | — | statement&#95;missing |", report)
        self.assertIn("| event-04 | SEBAGIAN | — | statement&#95;amount |", report)
        self.assertIn("| event-05 | REL TAK TERDAFTAR | — | rail&#95;unknown |", report)
        self.assertIn("| event-06 | TIDAK COCOK | — | evidence&#95;inconsistent |", report)

    def test_sort_order_is_stable_across_input_permutations(self):
        result = fixture()
        first = render_report(result)
        result["events"].reverse()

        self.assertEqual(render_report(result), first)
        positions = [first.index(event_id) for event_id in (
            "event-05", "event-03", "event-04", "event-06", "event-01", "event-02",
        )]
        self.assertEqual(positions, sorted(positions))

    def test_no_verified_events_display_absence(self):
        result = fixture()
        result["events"] = [event for event in result["events"] if event["verified_rupiah"] is None]
        report = render_report(result)

        self.assertIn("Total terverifikasi — —", report)
        self.assertIn("COCOK PENUH — 0", report)
        self.assertNotIn("Rp0", report)

    def test_escape_table_cells_and_omit_extra_fields(self):
        result = fixture()
        event = result["events"][0]
        event["id"] = "<contoh|uji>"
        event["private_metadata"] = "SINTETIK-TEKS-PRIVAT"
        report = render_report(result)

        self.assertIn("&lt;contoh&#124;uji&gt;", report)
        self.assertNotIn("SINTETIK-TEKS-PRIVAT", report)

    def test_invalid_result_envelope_rejected(self):
        for field, value in (("schema", "wrong"), ("max_lag_days", True),
                             ("max_lag_days", -1), ("events", {})):
            with self.subTest(field=field, value=value):
                result = fixture()
                result[field] = value
                with self.assertRaises(ValueError):
                    render_report(result)

    def test_invalid_event_rejected(self):
        result = fixture()
        for index, field, value in (
            (0, "verified_rupiah", True),
            (0, "verified_rupiah", 15000.0),
            (0, "verified_rupiah", 0),
            (0, "verified_rupiah", None),
            (0, "rail", "facebook"),
            (0, "id", "event-01"),
            (0, "status", "VERIFIED"),
            (0, "issues", "bad-input"),
            (0, "issues", ["newline\nissue"]),
            (0, "issues", ["amount_mismatch"]),
            (1, "issues", []),
            (1, "verified_rupiah", 15000),
            (4, "rail", "kbm_seabank"),
        ):
            with self.subTest(index=index, field=field, value=value):
                broken = deepcopy(result)
                broken["events"][index][field] = value
                with self.assertRaises(ValueError):
                    render_report(broken)

    def test_standalone_cli_reads_fixture_and_writes_only_stdout(self):
        script = Path(__file__).with_name("revenue_report.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "verification.json"
            source = json.dumps(fixture()).encode("utf-8")
            path.write_bytes(source)

            proc = subprocess.run([sys.executable, str(script), str(path)],
                                  cwd=root, capture_output=True, text=True, check=True)

            self.assertEqual(proc.stdout, render_report(fixture()))
            self.assertEqual(list(root.iterdir()), [path])
            self.assertEqual(path.read_bytes(), source)

    def test_cli_does_not_emit_partial_report_for_malformed_or_ambiguous_json(self):
        script = Path(__file__).with_name("revenue_report.py")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "verification.json"
            original = json.dumps(fixture())
            for contents in ('{"schema":', '{"max_lag_days": -1, ' + original[1:]):
                with self.subTest(contents=contents):
                    path.write_text(contents, encoding="utf-8")
                    proc = subprocess.run([sys.executable, str(script), str(path)],
                                          capture_output=True, text=True)

                    self.assertEqual(proc.returncode, 2)
                    self.assertEqual(proc.stdout, "")
                    self.assertIn("Error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
