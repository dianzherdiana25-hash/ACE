from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .claim_checker import check_claims
from .test_literature_reviewer import DIMS, hypotheses
from .test_source_collector import source


class ClaimCheckTests(unittest.TestCase):
    def test_contradiction_support_interval_and_different_context_are_traced(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            refs = hypotheses(root)
            refs["sources"].append(source(root, "overlap", "cohort_d",
                                           "| shifty | group | cahaya | lab | 34 | pct | 20 | 29 | 37 |"))
            row = {"id": "a", "text": "Cahaya 31 persen.", "source_ref": "fixture:claim", "dimensions": DIMS,
                   "value": "31", "unit": "pct", "tolerance": "1", "minimum_groups": 2, "minimum_sample": 20}
            plan = {"schema": "ace.institute.claim-plan.v1", "source_plan": refs,
                    "claims": [row, row | {"id": "missing", "dimensions": DIMS | {"context": "unknown"}}]}
            report = check_claims(plan, identity(plan), root)
            found, unknown = report["claims"]
            self.assertEqual(found["status"], "mixed_evidence")
            self.assertEqual(found["support_groups"], ["cohort_a"])
            self.assertEqual(found["contradict_groups"], ["cohort_b"])
            self.assertEqual(found["excluded"][0]["source_id"], "wrong")
            self.assertEqual({r["source_id"]: r["classification"] for r in found["measurements"]}["overlap"], "interval_overlaps")
            self.assertEqual(unknown["status"], "insufficient_evidence")
