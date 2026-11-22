from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_STORED, ZipFile

from ._contracts import ProductionError, identity
from .epub_builder import build_epub, verify_epub
from .test_tabular_engine import save


class EpubTests(unittest.TestCase):
    def test_native_container_toc_spine_and_xhtml_escaped_with_source_hash(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref = save(root, "one.txt", b"## Outline\nA < B & C.\n")
            notes = save(root, "next.txt", b"More text.\n")
            plan = {"schema": "ace.production.epub-plan.v1", "id": "fixture", "title": "Cahaya", "creator": "ACE",
                    "language": "id", "revision_date": "2025-05-01", "chapters": [
                        {"id": "first", "title": "Bab Satu", **ref}, {"id": "second", "title": "Bab Dua", **notes}]}
            raw, report = build_epub(plan, identity(plan), root)
            self.assertEqual(report["verified_chapters"], 2)
            self.assertEqual(verify_epub(raw), 2)
            with ZipFile(BytesIO(raw)) as bundle:
                self.assertEqual(bundle.infolist()[0].compress_type, ZIP_STORED)
                self.assertIn(b"A &lt; B &amp; C.", bundle.read("EPUB/first.xhtml"))
            self.assertEqual(build_epub(plan, identity(plan), root)[0], raw)
            plan["chapters"][0]["id"] = "nav"
            with self.assertRaisesRegex(ProductionError, "dicadangkan"):
                build_epub(plan, identity(plan), root)
