from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .test_tabular_engine import save
from .writing_coach import review_revision


class WritingTests(unittest.TestCase):
    def test_feedback_mapped_to_changed_lines_and_required_phrase_loss(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.writing-revision-plan.v1",
                    "before": save(root, "before.md", b"Statistik tetap.\nAwal\nAkhir\n"),
                    "after": save(root, "after.md", b"Uraian baru.\nAwal\nAkhir\n"),
                    "max_words": 20, "required": [{"id": "fact", "must_remain": "Statistik tetap", "source_ref": "fixture:fact"}],
                    "feedback": [{"id": key, "line": line, "prompt": "Tinjau ulang.", "source_ref": "fixture:note"}
                                 for key, line in (("edit", 1), ("late", 3))]}
            result = review_revision(plan, identity(plan), root)
            self.assertEqual(result["changes"][0]["related_feedback"], ["edit"])
            self.assertEqual(result["blockers"], ["fact"])
            self.assertEqual(result["feedback_outside_changed_lines"], ["late"])
