from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .failed_research_archive import index_failed
from .test_comparison_analyst import save


class NegativeArchiveTests(unittest.TestCase):
    def test_failure_and_reason_must_link_to_actual_lines(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = save(root, "failed.md", b"Hasil null.\nSensor drift.\n")
            plan = {"schema": "ace.institute.failed-archive-plan.v1", "entries": [{
                "id": "trial", "question": "Apakah hasil tersedia?", "closed_at": "2025-05-01", "failure_class": "null",
                "report": report | {"line": 1, "excerpt": "Hasil null."},
                "protocol": save(root, "protocol.md", b"Procedure"),
                "notes": [{"line": 2, "reason": "drift", "excerpt": "Sensor drift."}]}]}
            indexed = index_failed(plan, identity(plan), root)
            self.assertEqual(indexed["count_by_class"]["null"], 1)
            self.assertEqual(indexed["entries"][0]["causes"][0]["line"], 2)
            plan["entries"][0]["notes"][0]["line"] = 1
            with self.assertRaisesRegex(ResearchError, "petikan"):
                index_failed(plan, identity(plan), root)
