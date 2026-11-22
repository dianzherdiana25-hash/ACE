from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, canonical, identity
from ._docx import NS
from .report_composer import compose_report
from .test_tabular_engine import save


class ReportTests(unittest.TestCase):
    def test_same_arithmetic_result_fills_doc_title_body_and_cells(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            measured = {"schema": "ace.production.measurement-series.v1", "items": [
                {"id": "left", "value": "2.4", "unit": "lux", "source_ref": "fixture:left"},
                {"id": "right", "value": "3.1", "unit": "lux", "source_ref": "fixture:right"}]}
            plan = {"schema": "ace.production.report-plan.v1", "source": save(root, "measured.json", canonical(measured)),
                    "metrics": [{"id": "total", "unit": "lux", "operation": "sum", "members": ["left", "right"]}],
                    "document": {"title": "Total {{total}}", "formats": ["docx"], "blocks": [
                        {"kind": "paragraph", "body": "Hasil {{total}}"},
                        {"kind": "table", "columns": ["Ukuran"], "rows": [["{{total}}"]]}]}}
            outputs, receipt = compose_report(plan, identity(plan), root)
            doc = ET.fromstring(unpack(outputs["document.docx"])["word/document.xml"])
            text = [item.text for item in doc.findall(f".//{{{NS}}}t")]
            self.assertEqual(sum("5.5 lux" in item for item in text), 3)
            self.assertEqual([item["record"] for item in receipt["metrics"]["total"]["evidence"]], [1, 2])
            plan["document"]["blocks"][0]["body"] += " dan 7."
            with self.assertRaisesRegex(ProductionError, "binding metrik"):
                compose_report(plan, identity(plan), root)
