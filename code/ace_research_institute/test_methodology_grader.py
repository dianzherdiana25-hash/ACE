from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .methodology_grader import assess_methods
from .test_comparison_analyst import save


class MethodsTests(unittest.TestCase):
    def test_rubric_withheld_if_unassessed_even_when_threshold_reached(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = save(root, "methods.md", b"Alokasi diacak.\nCara ukur disimpan.\n")
            plan = {"schema": "ace.institute.method-plan.v1", "design": "randomized",
                    "source": source, "minimum_bp": 2000, "criteria": [
                       {"id": "sequence", "status": "met", "line": 1, "excerpt": "diacak", "reason": "Alokasi disebut."},
                       {"id": "measurement", "status": "partial", "line": 2, "excerpt": "Cara ukur", "reason": "Kalibrasi absen."}]}
            report = assess_methods(plan, identity(plan), root)
            self.assertEqual((report["score_bp"], report["status"]), (3100, "hold"))
            self.assertEqual(report["criteria"][1]["status"], "unassessed")
            plan["criteria"][1]["line"] = 1
            with self.assertRaisesRegex(ResearchError, "Kutipan"):
                assess_methods(plan, identity(plan), root)
