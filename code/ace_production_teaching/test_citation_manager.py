from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .citation_manager import registry
from .test_tabular_engine import save


class CitationsTests(unittest.TestCase):
    def test_same_evidence_alias_number_stable_and_unknown_mentions_cite_positions(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            link = save(root, "source.txt", b"Evidence for a document.\n")
            plan = {"schema": "ace.production.citation-plan.v1", "sources": [
                {"id": key, "title": title, "reference": "fixture:source", "evidence": link | {"line": 1}}
                for key, title in (("canon", "Source"), ("alias", "Another title"))],
                "documents": [{"id": "first", **save(root, "first.md", b"Some [@alias] and [@missing].\n")},
                              {"id": "second", **save(root, "second.md", b"`[@hidden]` [@canon]\n")}]}
            result = registry(plan, identity(plan), root)
            book = result["bibliography"][0]
            self.assertEqual((book["number"], book["canonical"], book["aliases"]), (1, "canon", ["alias"]))
            self.assertEqual([row["cited_id"] for row in book["used_in"]], ["alias", "canon"])
            self.assertEqual(result["unresolved"][0]["cited_id"], "missing")
            self.assertEqual(result["alias_conflicts"][0]["reason"], "same_line_inconsistent_title")
