from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, identity
from .contract_builder import draft_contract
from .test_tabular_engine import save


class ContractTests(unittest.TestCase):
    def test_clause_custody_and_required_topics_are_visible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = save(root, "clause.txt", b"Pekerjaan mencakup {{scope}}.\n")
            plan = {"schema": "ace.production.contract-plan.v1", "title": "Perjanjian fixture",
                    "required_topics": ["scope"], "formats": ["docx"],
                    "bindings": [{"id": "scope", "value": "materi contoh", "source_ref": "fixture:scope"}],
                    "clauses": [{"id": "chapter", "topic": "scope", "heading": "Lingkup",
                                 "approval_ref": "fixture:approved", **raw}]}
            files, receipt = draft_contract(plan, identity(plan), root)
            self.assertEqual(receipt["state"], "draft_unsigned")
            self.assertEqual(receipt["clauses"][0]["clause_sha256"], raw["sha256"])
            self.assertIn(b"materi contoh", unpack(files["document.docx"])["word/document.xml"])
            plan["required_topics"].append("duration")
            with self.assertRaisesRegex(ProductionError, "Topik wajib"):
                draft_contract(plan, identity(plan), root)
