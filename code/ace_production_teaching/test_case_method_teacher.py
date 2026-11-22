from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, identity
from .case_method_teacher import select_case
from .test_learner_model import profile
from .test_tabular_engine import save


class CasesTests(unittest.TestCase):
    def test_case_binds_scenario_line_and_permission_and_protects_answer(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = {"id": "field", "topic": "base", "level": 1, "case": save(root, "case.txt", b"Sensor A bergerak.\n"),
                    "permit_ref": "fixture:permission", "answer_forms": ["hotfix"],
                    "decisions": [{"id": "first", "line": 1, "question": "Apa yang perlu diperiksa dahulu?"}]}
            plan = {"schema": "ace.teaching.case-plan.v1", "profile": profile(root), "topic": "base", "maximum_level": 3,
                    "cases": [case, case | {"id": "private", "permit_ref": None}]}
            result = select_case(plan, identity(plan), root)
            self.assertEqual(result["case"]["decisions"][0]["scenario"], "Sensor A bergerak.")
            self.assertEqual(result["held"], [{"case": "private", "reason": "permission_missing"}])
            case["decisions"][0]["question"] = "Coba hotfix?"
            with self.assertRaisesRegex(ProductionError, "jawaban"):
                select_case(plan, identity(plan), root)
