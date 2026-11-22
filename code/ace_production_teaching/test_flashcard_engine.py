from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .flashcard_engine import make_cards
from .test_learner_model import profile
from .test_tabular_engine import save


class FlashcardsTests(unittest.TestCase):
    def test_only_observed_weakness_produces_source_bound_cards(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = save(root, "fact.md", b"Baseline dipakai untuk pembanding.\n")
            plan = {"schema": "ace.teaching.flashcard-plan.v1", "profile": profile(root),
                    "maximum": 10, "weakness_below_bp": 8000, "facts": [
                       {"id": f"{topic}_fact", "topic": topic, "prompt": "Untuk apa baseline?",
                        "answer": "untuk pembanding", "source": data | {"line": 1}} for topic in ("base", "target")]}
            result = make_cards(plan, identity(plan), root)
            self.assertEqual([row["id"] for row in result["cards"]], ["base_fact"])
            self.assertEqual(result["cards"][0]["based_on_attempt_lines"], [1, 2])
            self.assertEqual(result["held"][0]["reason"], "not_observed")
