from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .material_qa import assess_material
from .test_tabular_engine import save


class MaterialTests(unittest.TestCase):
    def test_material_gate_verifies_linked_goal_and_finds_answer_leak(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = save(root, "source.md", b"Ukuran perlu dikalibrasi.\n")
            plan = {"schema": "ace.teaching.material-plan.v1", "goals": ["calibration"], "reserved_answers": ["nilai tepat"],
                    "material": save(root, "lesson.md", b"# Lesson\nGunakan kalibrasi.\n"),
                    "cards": [{"goal": "calibration", "material_phrase": "Gunakan kalibrasi",
                               "proof": source, "proof_excerpt": "perlu dikalibrasi"}]}
            self.assertEqual(assess_material(plan, identity(plan), root)["status"], "pass")
            plan["material"] = save(root, "lesson.md", b"# Lesson\nGunakan kalibrasi.\nInilah nilai tepat.\n")
            report = assess_material(plan, identity(plan), root)
            self.assertEqual(report["answer_findings"], [{"line": 3, "reason": "reserved_answer_present"}])
            self.assertEqual(report["status"], "hold")
