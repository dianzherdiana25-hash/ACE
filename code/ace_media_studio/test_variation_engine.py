from collections import Counter
from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from .variation_engine import variants


class VariationTests(unittest.TestCase):
    def test_grid_varies_real_pixels_and_balances_and_preserves_brief(self):
        plan = {"schema": "ace.media.variation-plan.v1", "id": "local", "source_ref": "fixture:brief",
                "brief": "Cahaya geometris", "background": "#202035", "colors": ["#F06050", "#73A060"],
                "positions": ["left", "right"], "motifs": ["diamond", "disc"], "count": 8, "seed": 11}
        files, report = variants(plan, identity(plan))
        self.assertEqual((files, report), variants(plan, identity(plan)))
        self.assertEqual(report["brief_sha256"], sha256(plan["brief"].encode()).hexdigest())
        for factor in ("palette_color", "position", "motif"):
            self.assertEqual(sorted(Counter(item[factor] for item in report["variants"]).values()), [4, 4])
        self.assertEqual(len({sha256(raw).hexdigest() for raw in files.values()}), 8)
        plan["count"] = 9
        with self.assertRaisesRegex(ContractError, "Jumlah varian"):
            variants(plan, identity(plan))
