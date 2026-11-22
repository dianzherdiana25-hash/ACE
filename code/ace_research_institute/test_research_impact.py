from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .research_impact import impact
from .test_comparison_analyst import save


class ImpactTests(unittest.TestCase):
    def test_reference_and_pre_post_units_trace_observational_change(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = save(root, "study.md", b"Complete measurement.\n")
            decision = save(root, "decision.md", b"See study_a.\n")
            measure = save(root, "outcome.md", b"Baseline 400 ms.\nLater 0.25 s.\n")
            plan = {"schema": "ace.institute.impact-plan.v1", "studies": [
                        {"id": "study_a", "date": "2025-01-02", "source": source | {"line": 1, "marker": "measurement"}}],
                    "decisions": [{"id": "release", "date": "2025-02-03", "study": "study_a", "metric": "duration",
                        "decision_ref": decision | {"line": 1, "marker": "See study_a."},
                        "before": {"date": "2025-02-01", "value": "400", "unit": "ms",
                                   "evidence": measure | {"line": 1, "marker": "400 ms"}},
                        "after": {"date": "2025-02-04", "value": "0.25", "unit": "s",
                                  "evidence": measure | {"line": 2, "marker": "0.25 s"}}}]}
            report = impact(plan, identity(plan), root)
            self.assertEqual(report["paired_outcome_count"], 1)
            self.assertEqual(report["decisions"][0]["observational_delta"], "-0.15")
            plan["decisions"][0]["before"]["value"] = "40"
            with self.assertRaisesRegex(ResearchError, "tidak memuat nilai"):
                impact(plan, identity(plan), root)
