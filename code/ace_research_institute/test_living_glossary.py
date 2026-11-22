from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .living_glossary import glossary
from .test_comparison_analyst import save


class GlossaryTests(unittest.TestCase):
    def test_same_date_definitions_retained_and_alias_collision_visible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = []
            for key, date, note in (("old", "2025-01-01", "**ratio** — Definisi dasar."),
                                    ("later", "2025-02-01", "**ratio** — Definisi baru.\n**rate** — Kecepatan."),
                                    ("conflict", "2025-02-01", "**ratio** — Definisi berbeda.")):
                rows.append({"id": key, "date": date, **save(root, f"{key}.md", note.encode())})
            plan = {"schema": "ace.institute.glossary-plan.v1", "topic": "measurement", "as_of": "2025-02-02",
                    "documents": rows, "aliases": [{"alias": "rasio", "term": term, "source_ref": f"fixture:{term}"}
                                                   for term in ("rate", "ratio")]}
            terms = glossary(plan, identity(plan), root)
            self.assertEqual(terms["aliases"][0]["status"], "ambiguous")
            self.assertIsNone(terms["entries"][1]["current_value"])
            self.assertEqual(len(terms["entries"][1]["definitions"]), 3)
