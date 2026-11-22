from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .journal_club import schedule_club
from .test_comparison_analyst import save


class JournalTests(unittest.TestCase):
    def test_weekly_roles_rotate_and_unfilled_week_remains_visible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            link = save(root, "paper", b"Text")
            days = ["2025-01-01", "2025-01-08"]
            plan = {"schema": "ace.institute.journal-club-plan.v1", "starting": days[0],
                    "members": [{"id": name, "available": days, "roles": ["reviewer", "challenger"]} for name in ("a", "b")],
                    "readings": [{"id": name, "title": name, **link, "prompts": ["Uji asumsi?"]} for name in ("x", "y", "z")]}
            schedule = schedule_club(plan, identity(plan), root)
            self.assertEqual([row["roles"] for row in schedule["sessions"]],
                             [{"reviewer": "a", "challenger": "b"}, {"reviewer": "b", "challenger": "a"}, None])
            self.assertEqual(schedule["sessions"][2]["status"], "unfilled")
