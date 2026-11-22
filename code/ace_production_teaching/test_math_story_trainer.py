import unittest

from ._contracts import identity
from .math_story_trainer import create_stories


class MathStoryTests(unittest.TestCase):
    def test_share_story_quantities_and_key_are_consistent_without_seed_drift(self):
        plan = {"schema": "ace.teaching.math-story-plan.v1", "seed": 61, "each": 5, "contexts": [
                {"id": "share", "kind": "share", "setting": "kelas", "unit": "buku",
                 "range": [2, 7], "source_ref": "fixture:division"}]}
        result = create_stories(plan, identity(plan))
        self.assertEqual(result, create_stories(plan, identity(plan)))
        for story, key in zip(result["items"], result["key"], strict=True):
            relation = key["relationship"]
            self.assertIn(f"{relation['a'] * relation['b']} buku", story["prompt"])
            self.assertEqual(key["value"], relation["a"])
            self.assertEqual(key["prompt_sha256"], identity(story))
