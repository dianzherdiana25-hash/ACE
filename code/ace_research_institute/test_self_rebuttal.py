from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, canonical, identity
from .deep_report_writer import make_report
from .self_rebuttal import challenge
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan
from .test_source_collector import source, source_plan


class SelfRebuttalTests(unittest.TestCase):
    def test_new_sources_can_disagree_but_old_hash_and_new_value_are_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = report_plan(root)
            prior = make_report(template, identity(template), root)
            emerging = source_plan([source(root, "other", "new", "| k | group | cahaya | lab | 70 | pct | 50 | - | - |")])
            candidate = dict(template["checks"]["claims"][0])
            plan = {"schema": "ace.institute.self-rebuttal-plan.v1",
                    "prior_report": save(root, "previous.json", canonical(prior)),
                    "counter_plan": {"schema": "ace.institute.rebuttal-plan.v1", "target": "valid",
                        "minimum_conflicting_groups": 1, "max_cites": 2, "limitation": "Konteks yang sama.",
                        "checks": {"schema": "ace.institute.claim-plan.v1", "source_plan": emerging, "claims": [candidate]}}}
            output = challenge(plan, identity(plan), root)
            self.assertEqual(output["counter_review"]["status"], "counterevidence_found")
            candidate["value"] = "35"
            with self.assertRaisesRegex(ResearchError, "nilai klaim"):
                challenge(plan, identity(plan), root)
            candidate["value"] = "31"
            emerging["sources"].append(template["checks"]["source_plan"]["sources"][0])
            with self.assertRaisesRegex(ResearchError, "hash bukti asal"):
                challenge(plan, identity(plan), root)
