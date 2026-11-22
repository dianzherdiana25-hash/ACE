from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .field_chronology import chronology
from .test_comparison_analyst import save


class ChronologyTests(unittest.TestCase):
    def test_leap_month_and_overlapping_date_precision_are_retained(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref = save(root, "log.txt", b"2024-02 Versi awal.\n2024-02-15 Pemeriksaan tengah bulan.\n")
            rows = [{"id": key, "date": date, "summary": "Kejadian fixture", "document": "log", "line": index,
                    "after": [] if index == 1 else ["month"], "excerpt": excerpt} for index, (key, date, excerpt) in enumerate(
                        (("month", "2024-02", "Versi awal"), ("day", "2024-02-15", "Pemeriksaan")), 1)]
            plan = {"schema": "ace.institute.chronology-plan.v1", "field": "fixture",
                    "documents": [{"id": "log", **ref}], "events": rows}
            report = chronology(plan, identity(plan), root)
            self.assertEqual(report["events"][0]["range"], ["2024-02-01", "2024-02-29"])
            self.assertEqual(report["findings"][0]["reason"], "overlapping_intervals")
            rows[1]["date"] = "2024-02-14"
            with self.assertRaisesRegex(ResearchError, "baris"):
                chronology(plan, identity(plan), root)
