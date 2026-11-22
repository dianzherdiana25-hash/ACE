import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, identity
from .invoice_builder import build_invoice


class InvoiceTests(unittest.TestCase):
    def test_rounds_lines_tax_and_total_cross_check_and_creates_no_transaction(self):
        plan = {"schema": "ace.production.invoice-plan.v1", "id": "mock", "issued": "2025-05-01",
                "due": "2025-05-08", "currency": "USD", "minor_digits": 2, "issuer_label": "Issuer fixture",
                "recipient_label": "Recipient fixture", "formats": ["docx"],
                "items": [{"id": "line_a", "description": "Bahan fixture", "quantity": "3", "price": "2.335",
                           "tax_bp": 1000, "source_ref": "fixture:line_a"},
                          {"id": "line_b", "description": "Bahan kedua", "quantity": "1", "price": "5.11",
                           "tax_bp": 0, "source_ref": "fixture:line_b"}]}
        raw, report = build_invoice(plan, identity(plan))
        self.assertEqual(report["totals"], {"net": "12.12", "tax": "0.70", "total": "12.82"})
        self.assertEqual(report["state"], "document_only_draft")
        self.assertIn(b"Total USD 12.82", unpack(raw["document.docx"])["word/document.xml"])
        plan["items"][0]["price"] = "-1"
        with self.assertRaises(ProductionError):
            build_invoice(plan, identity(plan))
