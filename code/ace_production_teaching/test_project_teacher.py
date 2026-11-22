from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .document_builder import make_document
from .project_teacher import project
from .test_document_builder import document
from .test_tabular_engine import save
from .test_topic_map import topics


class ProjectsTests(unittest.TestCase):
    def test_verified_artifact_unlocks_direct_successor_and_preserves_later_gap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = document()
            raw = make_document(template, identity(template))[0]["document.docx"]
            plan = {"schema": "ace.teaching.project-plan.v1", "graph": topics(), "minutes": 10,
                    "deliverables": [{"id": key, "format": "docx", "minimum": {"tables": 1},
                        "goal": "Kirim tabel", "source_ref": "fixture:goal"} for key in ("target", "base", "other")],
                    "submissions": [{"id": "base", **save(root, "report.docx", raw)}]}
            result = project(plan, identity(plan), root)
            self.assertEqual([row["status"] for row in result["milestones"]],
                             ["verified", "next_activity", "blocked_by_unverified_predecessor"])
            self.assertEqual(result["milestones"][2]["needs"], ["other"])
