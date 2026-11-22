from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .research_intake import intake
from .test_comparison_analyst import save


def request_plan(root):
    pointer = save(root, "brief.txt", b"Prior observation.")
    fast = {"id": "fast", "question": "Pakailah data?", "outcome": "Ringkasan", "purpose": "Telaah bukti",
            "submitted": "2025-05-09", "requested_due": "2025-05-12", "effort_hours": 3, "impact": 50,
            "approved_scope": True, "evidence": [{**pointer, "label": "Bukti fixture"}]}
    held = fast | {"id": "hold", "outcome": None, "approved_scope": False, "evidence": []}
    return {"schema": "ace.institute.intake-plan.v1", "as_of": "2025-05-10", "requests": [fast, held]}


class IntakeTests(unittest.TestCase):
    def test_missing_outcome_consent_and_evidence_surface_as_explicit_holds(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = request_plan(root)
            result = intake(plan, identity(plan), root)
            self.assertEqual(result["eligible"][0]["days_until_due"], 2)
            self.assertEqual(result["held"][0]["needs"], ["scope_unapproved", "outcome_missing", "no_evidence_input"])
