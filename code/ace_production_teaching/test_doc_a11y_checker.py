from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .doc_a11y_checker import inspect_accessibility
from .document_builder import make_document
from .test_document_builder import document
from .test_tabular_engine import save


class AccessibilityTests(unittest.TestCase):
    def test_semantic_heading_alt_labels_and_native_table_headers(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = {"schema": "ace.production.doc-a11y-plan.v1", "kind": "markdown",
                      "file": save(root, "test.md", b"# Main\n### Skip\n![](local.png)\n[click here](#main)\n")}
            result = inspect_accessibility(report, identity(report), root)
            self.assertEqual({row["rule"] for row in result["findings"]},
                             {"heading_level_skipped", "missing_image_alt", "ambiguous_link_label"})
            doc = document()
            data = make_document(doc, identity(doc))[0]["document.docx"]
            report.update(kind="docx", file=save(root, "valid.docx", data))
            good = inspect_accessibility(report, identity(report), root)
            self.assertEqual(good["status"], "no_listed_findings")
            self.assertEqual(good["headings"][0]["title"], "Hasil")
