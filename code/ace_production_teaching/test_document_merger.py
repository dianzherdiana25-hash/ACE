from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, identity
from .artifact_qa import safe_xml
from .document_builder import make_document
from .document_merger import W, merge_documents
from .test_document_builder import document
from .test_tabular_engine import save


class MergerTests(unittest.TestCase):
    def test_complete_word_table_and_toc_hyperlinks_resolve_to_real_bookmarks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.production.merge-plan.v1", "title": "Gabungan", "sources": []}
            for name in ("first", "second"):
                spec = document()
                spec["title"] = name + " {{period}}"
                source = make_document(spec, identity(spec))[0]["document.docx"]
                plan["sources"].append({"id": name, "label": name.title(), **save(root, name + ".docx", source)})
            output, report = merge_documents(plan, identity(plan), root)
            body = safe_xml(unpack(output)["word/document.xml"])
            self.assertEqual(len(body.findall(f".//{W}tbl")), 2)
            anchors = {link.get(W + "anchor") for link in body.findall(f".//{W}hyperlink")}
            bookmarks = {node.get(W + "name") for node in body.findall(f".//{W}bookmarkStart")}
            self.assertEqual(anchors, bookmarks)
            self.assertEqual(anchors, {row["bookmark"] for row in report["sources"]})
            plan["sources"][1]["id"] = "first"
            with self.assertRaisesRegex(ProductionError, "ber-ID sama"):
                merge_documents(plan, identity(plan), root)
