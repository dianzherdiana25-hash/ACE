from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from .render_recipe import freeze_recipe, replay


def geometry():
    return {"schema": "ace.media.image-plan.v1", "source_ref": "fixture:recipe", "id": "local",
            "format": "png", "instructions": "CANVAS 40 32 #121214\nRECT 10 12 15 12 #EE3070"}


class RecipeTests(unittest.TestCase):
    def test_freeze_and_replay_validate_bytes_input_and_implementation(self):
        plan = geometry()
        content, recipe = freeze_recipe("geometry_png", plan, identity(plan))
        data, report = replay(recipe, identity(recipe))
        self.assertEqual(data, content)
        self.assertTrue(report["byte_identical"])
        self.assertEqual(recipe["result"]["sha256"], sha256(data).hexdigest())
        with self.assertRaisesRegex(ContractError, "Build"):
            bad = recipe | {"implementation_sha256": "a" * 64}
            replay(bad, identity(bad))
        recipe["result"]["sha256"] = "b" * 64
        with self.assertRaisesRegex(ContractError, "byte-identik"):
            replay(recipe, identity(recipe))
