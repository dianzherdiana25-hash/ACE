from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, identity
from .test_tabular_engine import save
from .vocab_trainer import train


class VocabularyTests(unittest.TestCase):
    def test_single_context_gap_and_ambiguous_occurrences(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.vocab-plan.v1", "document": save(root, "context.txt",
                    b"Panel memantulkan cahaya ke meja.\nPanel panel.\n"),
                    "seed": 4, "cards": [{"id": "sample", "line": 1, "target": "panel",
                                         "distractors": ["kertas", "lampu"], "gloss_ref": "fixture:gloss"}]}
            report = train(plan, identity(plan), root)
            card = report["cards"][0]
            self.assertEqual(card["prompt"], "____ memantulkan cahaya ke meja.")
            self.assertEqual(card["options"][report["instructor_key"][0]["position"]], "panel")
            plan["cards"][0]["line"] = 2
            with self.assertRaisesRegex(ProductionError, "tunggal"):
                train(plan, identity(plan), root)
