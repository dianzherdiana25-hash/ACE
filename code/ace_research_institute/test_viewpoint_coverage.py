from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .test_deep_report_writer import report_plan
from .test_literature_reviewer import hypotheses
from .viewpoint_coverage import assess_cover


class ViewpointTests(unittest.TestCase):
    def test_report_coverage_uses_same_context_and_names_unlabeled_sources(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            checks = report_plan(root)["checks"]
            checks["source_plan"] = hypotheses(root)
            plan = {"schema": "ace.institute.viewpoint-plan.v1", "checks": checks, "target": "valid",
                    "perspectives": [{"id": key, "minimum_groups": 1, "description": key} for key in ("method", "field")],
                    "stance_labels": [{"source_id": "left", "perspective": "method", "annotation_ref": "fixture:annotation"},
                                      {"source_id": "wrong", "perspective": "field", "annotation_ref": "fixture:field"}]}
            result = assess_cover(plan, identity(plan), root)
            self.assertEqual(result["covered"], 1)
            self.assertEqual(result["unlabeled_sources"], ["right"])
            self.assertEqual(result["perspectives"][0]["missing_groups"], 1)
