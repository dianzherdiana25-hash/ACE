from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .grader import assess
from .misconception_tracker import track
from .test_grader import grade
from .test_tabular_engine import save


class TrackingTests(unittest.TestCase):
    def test_repeat_same_item_not_enough_and_older_receipt_ignored(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.misconception-plan.v1", "as_of": "2025-05-10",
                    "window_days": 20, "minimum_unique_tasks": 2, "map": [
                       {"criterion": "volume", "id": "volume_confusion", "topic": "state", "source_ref": "fixture:taxonomy"}], "grades": []}
            for index, (task, stamp) in enumerate((("same", "2025-05-01"), ("same", "2025-05-02"),
                                                   ("prior", "2025-01-01"), ("other", "2025-05-02"))):
                input = grade(task)
                input["response"]["source_ref"] = f"fixture:{index}"
                proof = assess(input, identity(input))
                plan["grades"].append({"date": stamp, **save(root, f"grade{index}.json", canonical(proof))})
            out = track(plan, identity(plan), root)
            self.assertEqual(out["patterns"][0]["state"], "recurring")
            self.assertEqual(out["patterns"][0]["distinct_tasks"], ["other", "same"])
            self.assertEqual(len(out["old_receipts"]), 1)
            plan["grades"].pop()
            self.assertEqual(track(plan, identity(plan), root)["patterns"][0]["state"], "insufficient_repetition")
