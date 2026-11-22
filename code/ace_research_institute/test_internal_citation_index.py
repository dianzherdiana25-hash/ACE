from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .internal_citation_index import build_index, canonical_citation
from .test_comparison_analyst import save


class CitationIndexTests(unittest.TestCase):
    def test_doi_across_spelling_and_fragments_uses_one_key(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = save(root, "first.md", b"DOI: 10.1234/Case.\nhttps://public.example/a#note\n")
            second = save(root, "second.md", b"(https://doi.org/10.1234/case)\nhttps://PUBLIC.example:443/a#part\n")
            plan = {"schema": "ace.institute.citation-index-plan.v1",
                    "documents": [{"id": "first", **first}, {"id": "second", **second}]}
            result = build_index(plan, identity(plan), root)
            self.assertEqual([row["canonical"] for row in result["citations"]], ["doi:10.1234/case", "https://public.example/a"])
            self.assertEqual([row["distinct_documents"] for row in result["citations"]], [2, 2])
            self.assertEqual(result["citations"][1]["occurrences"][0]["line"], 2)
            self.assertIsNone(canonical_citation("https://value@public.example/a"))
