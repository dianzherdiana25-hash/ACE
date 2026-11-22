from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .spaced_repetition import review_schedule
from .test_tabular_engine import save


class SpacingTests(unittest.TestCase):
    def test_intervals_follow_evidence_and_lapse_resets(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = [{"id": f"review_{n}", "card": "base", "date": f"2025-04-{n:02d}", "quality": rating,
                     "source_ref": f"fixture:{n}"} for n, rating in ((2, 5), (4, 4), (9, 1))]
            plan = {"schema": "ace.teaching.repetition-plan.v1", "as_of": "2025-04-10",
                    "cards": [{"id": key, "introduced": "2025-04-01", "source_ref": f"fixture:{key}"} for key in ("base", "other")],
                    "receipts": save(root, "practice.jsonl", b"\n".join(map(canonical, data))),
                    "initial_days": 1, "max_days": 15}
            out = review_schedule(plan, identity(plan), root)
            cards = {row["card"]: row for row in out["cards"]}
            self.assertEqual([x["interval_days"] for x in cards["base"]["trail"]], [1, 6, 1])
            self.assertEqual(cards["base"]["lapses"], 1)
            self.assertTrue(cards["base"]["is_due"])
            self.assertEqual(cards["other"]["due"], "2025-04-01")
