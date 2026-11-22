from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .conversation_memory import recall
from .test_rolling_summary import sample


class RecallTests(unittest.TestCase):
    def test_across_sessions_recall_excludes_unauthorized_and_old_or_other_speakers(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowed = sample(root, "first")[0]
            also = sample(root, "second", day="2025-05-02")[0]
            old = sample(root, "old", day="2025-01-01")[0]
            plan = {"schema": "ace.presence.recall-plan.v1", "person": "quoted", "query": "panel",
                    "as_of": "2025-05-03", "retention_days": 10, "maximum": 10,
                    "sessions": [ref | {"people": ["quoted"], "grant_ref": "fixture:grant"} for ref in (allowed, also, old)]
                    + [{"path": "absent", "sha256": "0" * 64, "people": [], "grant_ref": None}]}
            report = recall(plan, identity(plan), root)
            self.assertEqual([row["session"] for row in report["matches"]], ["second", "first"])
            self.assertTrue(all(row["excerpt"] == "Kalibrasi panel tersedia." for row in report["matches"]))
            self.assertEqual(report["exclusions"]["no_grant"], 1)
            self.assertEqual(report["exclusions"]["outside_retention"], 2)
