from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .replication_assessor import assess
from .test_literature_reviewer import hypotheses


class ReplicationTests(unittest.TestCase):
    def test_numerical_tolerance_cannot_override_protocol_deviation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            protocol = {"unit": "pct", "maximum_delta": "20", "minimum_sample": 20, "direction": "same_sign",
                        "checks": [{"id": "blind", "status": "matched", "source_ref": "fixture:compare"}],
                        "source_ref": "fixture:protocol"}
            plan = {"schema": "ace.institute.replication-assessment.v1", "sources": hypotheses(root),
                    "prior": {"source_id": "left", "id": "left"}, "replication": {"source_id": "right", "id": "right"},
                    "protocol": protocol}
            result = assess(plan, identity(plan), root)
            self.assertEqual((result["effect_delta"], result["status"]), ("0.15", "matches_predefined_effect_rule"))
            protocol["checks"][0]["status"] = "unknown"
            result = assess(plan, identity(plan), root)
            self.assertEqual((result["status"], result["held"]), ("blocked", ["blind"]))
