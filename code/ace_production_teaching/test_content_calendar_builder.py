from hashlib import sha256
import unittest

from ._contracts import ProductionError, identity
from .content_calendar_builder import create_calendar


class CalendarTests(unittest.TestCase):
    def test_ics_folds_symbols_without_losing_bytes_and_enforces_dependency(self):
        plan = {"schema": "ace.production.calendar-plan.v1", "id": "fixture", "as_of": "2025-05-01T08:00:00Z",
                "channels": ["class"], "entries": [
                   {"id": "first", "title": "Bukti, draf", "channel": "class", "start": "2025-05-02T09:00:00Z",
                    "end": "2025-05-02T10:00:00Z", "requires": [], "source_ref": "fixture:start"},
                   {"id": "second", "title": "é" * 66, "channel": "class", "start": "2025-05-02T10:00:00Z",
                    "end": "2025-05-02T11:00:00Z", "requires": ["first"], "source_ref": "fixture:later"}]}
        raw, record = create_calendar(plan, identity(plan))
        self.assertEqual(record["ical_sha256"], sha256(raw).hexdigest())
        self.assertIn(b"SUMMARY:Bukti\\, draf\r\n", raw)
        self.assertIn("SUMMARY:" + "é" * 66, raw.decode().replace("\r\n ", ""))
        self.assertTrue(all(len(line) <= 75 for line in raw.split(b"\r\n")))
        plan["entries"][1]["start"] = "2025-05-02T09:50:00Z"
        with self.assertRaisesRegex(ProductionError, "tumpang tindih"):
            create_calendar(plan, identity(plan))
