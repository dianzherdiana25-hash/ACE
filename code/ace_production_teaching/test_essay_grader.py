from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .essay_grader import grade_essay
from .test_grader import grade
from .test_tabular_engine import save


class EssayTests(unittest.TestCase):
    def test_content_structure_and_citation_earn_separate_credit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"## intro\nSuhu tetap.\n## argument\nVolume. Massa pada gas. [@paper]\n"
            plan = {"schema": "ace.teaching.essay-plan.v1", "essay": save(root, "essay.md", raw), "id": "fixture",
                    "rubric": grade()["criteria"], "section_order": ["intro", "argument"],
                    "sources": ["paper"], "passing_bp": 9000}
            result = grade_essay(plan, identity(plan), root)
            self.assertEqual(result["score_bp"], 10000)
            self.assertEqual(result["citations"]["used"], {"paper": [4]})
            plan["sources"] = []
            self.assertEqual(grade_essay(plan, identity(plan), root)["score_bp"], 8800)
