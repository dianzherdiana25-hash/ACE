from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, canonical, identity
from .explanation_adapter import adapt
from .test_tabular_engine import save


class ExplanationTests(unittest.TestCase):
    def test_factual_binding_preserved_and_new_numbers_do_not_slip_in(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            card = {"schema": "ace.teaching.explanation-card.v1", "topic": "rate",
                    "facts": [{"id": "speed", "render": "Laju ukur 8 meter per detik.", "source_ref": "fixture:measurement",
                               "essential": True}]}
            plan = {"schema": "ace.teaching.explanation-plan.v1", "source": save(root, "card.json", canonical(card)),
                    "level": "intro", "variants": {"intro": ["Bayangkan bergerak. {{speed}}"],
                    "intermediate": ["Lihat pengukuran kita. {{speed}}"], "technical": ["Pada kerangka alat. {{speed}}"]}}
            answer = adapt(plan, identity(plan), root)
            self.assertEqual(answer["blocks"], [{"text": "Bayangkan bergerak. Laju ukur 8 meter per detik.",
                                                 "sources": ["fixture:measurement"]}])
            plan["variants"]["technical"] = ["Hitung lagi {{speed}} menjadi 9."]
            with self.assertRaisesRegex(ProductionError, "Angka baru"):
                adapt(plan, identity(plan), root)
