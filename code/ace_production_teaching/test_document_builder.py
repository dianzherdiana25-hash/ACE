from hashlib import sha256
from importlib.util import find_spec
from io import BytesIO
from xml.etree import ElementTree as ET
import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, identity
from ._docx import NS
from .document_builder import make_document


def document():
    return {"schema": "ace.production.document-plan.v1", "title": "Ringkasan {{period}}", "formats": ["docx", "pdf"],
            "bindings": [{"id": "period", "value": "Mei & Juni", "source_ref": "fixture:dates"}],
            "blocks": [{"kind": "heading", "level": 1, "body": "Hasil"},
                       {"kind": "paragraph", "body": "Nilai aman (terukur) \\"},
                       {"kind": "table", "columns": ["Rentang", "Nilai"], "rows": [["{{period}}", "10"]]},
                       {"kind": "break"}, {"kind": "paragraph", "body": "Lampiran"}]}


class DocumentTests(unittest.TestCase):
    def test_well_formed_docx_and_pdf_with_verified_blocks_and_lineage(self):
        plan = document()
        raw, receipt = make_document(plan, identity(plan))
        self.assertEqual(receipt["binding_sources"], {"period": "fixture:dates"})
        self.assertEqual(receipt["pdf_pages"], 2)
        self.assertEqual(receipt["output"]["document.pdf"]["sha256"], sha256(raw["document.pdf"]).hexdigest())
        doc = ET.fromstring(unpack(raw["document.docx"])["word/document.xml"])
        self.assertEqual(doc.find(f".//{{{NS}}}t").text, "Ringkasan Mei & Juni")
        self.assertIsNotNone(doc.find(f".//{{{NS}}}tblHeader"))
        self.assertEqual(raw, make_document(plan, identity(plan))[0])
        plan["bindings"].clear()
        with self.assertRaisesRegex(ProductionError, "Placeholder period"):
            make_document(plan, identity(plan))

    @unittest.skipUnless(find_spec("docx") and find_spec("pypdf"), "Pembaca artefak lokal diperlukan")
    def test_independent_word_and_pdf_readers_extract_the_same_document(self):
        from docx import Document
        from pypdf import PdfReader

        plan = document()
        raw, _ = make_document(plan, identity(plan))
        docx = Document(BytesIO(raw["document.docx"]))
        pdf = PdfReader(BytesIO(raw["document.pdf"]))
        self.assertEqual(docx.paragraphs[1].style.name.casefold(), "heading 1")
        self.assertEqual(docx.tables[0].cell(1, 1).text, "10")
        self.assertIn("Mei & Juni", pdf.pages[0].extract_text())
        self.assertIn("Lampiran", pdf.pages[1].extract_text())
