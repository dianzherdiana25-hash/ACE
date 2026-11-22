from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .artifact_qa import audit
from .document_builder import make_document
from .sheet_builder import make_workbook
from .test_document_builder import document
from .test_sheet_builder import workbook
from .test_tabular_engine import save


class ArtifactQATests(unittest.TestCase):
    def test_gate_reports_missing_structure_tamper_and_active_svg(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = document()
            xls = workbook()
            artifacts, _ = make_document(notes, identity(notes))
            workbook_bytes, _ = make_workbook(xls, identity(xls))
            work = [
                save(root, "notes.docx", artifacts["document.docx"]) | {"format": "docx", "minimum": {"tables": 1}},
                save(root, "work.xlsx", workbook_bytes) | {"format": "xlsx", "minimum": {"formulas": 5}},
                save(root, "chart.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>') |
                {"format": "svg", "minimum": {"accessible_title": 1}},
            ]
            if find_spec("pypdf"):
                work.append(save(root, "notes.pdf", artifacts["document.pdf"]) | {"format": "pdf", "minimum": {"pages": 2}})
            plan = {"schema": "ace.production.artifact-qa-plan.v1", "artifacts": work}
            result = audit(plan, identity(plan), root)
            self.assertEqual([row["status"] for row in result["formats"][:3]], ["pass", "hold", "hold"])
            self.assertEqual(result["formats"][1]["metrics"]["formulas"], 4)
            self.assertTrue(result["formats"][2]["metrics"]["active_features"])
            if len(work) == 4:
                self.assertEqual(result["formats"][3]["status"], "pass")
            (root / "notes.docx").write_bytes(artifacts["document.docx"] + b"x")
            self.assertIn("anchor", audit(plan, identity(plan), root)["formats"][0]["error"])
