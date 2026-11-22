from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .test_literature_reviewer import hypotheses
from .topic_knowledge_base import query_topics


class TopicTests(unittest.TestCase):
    def test_synonyms_and_exact_context_ranking_keep_inconsistent_values_visible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.institute.topic-query.v1", "source_plan": hypotheses(root), "limit": 2,
                    "query": "Berapa sinar di lab?", "aliases": [
                        {"field": "outcome", "value": "cahaya", "phrases": ["sinar"], "source_ref": "fixture:glossary"}]}
            report = query_topics(plan, identity(plan), root)
            first, second = report["results"]
            self.assertEqual(first["dimensions"]["context"], "lab")
            self.assertEqual(first["distinct_values"], ["0.31", "0.46"])
            self.assertEqual(second["dimensions"]["context"], "field")
            self.assertEqual(first["alias_provenance"], [{"dimension": "outcome", "source_ref": "fixture:glossary"}])
            plan["query"] = "Apa itu suara?"
            self.assertEqual(query_topics(plan, identity(plan), root)["status"], "unknown")
