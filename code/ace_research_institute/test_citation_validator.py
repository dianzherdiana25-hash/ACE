from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .citation_validator import validate_citations
from .test_comparison_analyst import save


class CitationValidatorTests(unittest.TestCase):
    def test_redirect_and_exact_excerpt_stay_offline_and_stale_is_separate(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = "2025-03-01"
            body = save(root, "body.txt", b"Line one\nProven claim.\n")
            snapshots = {"schema": "ace.institute.http-snapshot.v1", "entries": [
                {"url": "https://example.test/start", "captured": current, "status": 301, "redirect": "https://example.test/end", "document": None},
                {"url": "https://example.test/end", "captured": current, "status": 200, "redirect": None, "document": body},
                {"url": "https://example.test/old", "captured": "2025-02-01", "status": 200, "redirect": None, "document": body}]}
            plan = {"schema": "ace.institute.citation-validation-plan.v1", "as_of": current, "max_age_days": 10,
                    "snapshot": save(root, "archive.json", canonical(snapshots)), "citations": [
                        {"id": "match", "locator": "https://example.test/start", "line": 2, "excerpt": "Proven"},
                        {"id": "other", "locator": "https://example.test/end", "line": 1, "excerpt": "Proven"},
                        {"id": "stale", "locator": "https://example.test/old", "line": 2, "excerpt": "Proven"}]}
            result = validate_citations(plan, identity(plan), root)
            self.assertEqual([row["status"] for row in result["citations"]],
                             ["matched_in_snapshot", "excerpt_mismatch", "stale_snapshot"])
            self.assertEqual(len(result["citations"][0]["chain"]), 2)
            self.assertEqual(result["citations"][0]["evidence"]["sha256"], body["sha256"])
