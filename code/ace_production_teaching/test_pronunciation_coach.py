import unittest

from ._contracts import identity
from .pronunciation_coach import coach


class PronunciationTests(unittest.TestCase):
    def test_indonesian_cluster_is_one_unit_with_position_and_practice(self):
        plan = {"schema": "ace.teaching.pronunciation-plan.v1", "language": "id",
                "target": {"transcript": "Angin", "source_ref": "fixture:heard"},
                "attempt": {"transcript": "Anin", "source_ref": "fixture:attempt"},
                "exercises": [{"unit": "ng", "prompt": "Latih bunyi pada akhir suku.", "source_ref": "fixture:practice"}]}
        report = coach(plan, identity(plan))
        self.assertEqual(report["basis"], "weighted_grapheme_alignment")
        feature = report["mismatches"][0]
        self.assertEqual((feature["target"], feature["observed"], feature["target_word"]), ("ng", "n", 1))
        self.assertEqual(feature["practice"]["source_ref"], "fixture:practice")
        self.assertLess(report["similarity_bp"], 10000)
