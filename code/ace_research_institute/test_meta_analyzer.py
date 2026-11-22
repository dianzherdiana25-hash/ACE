from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .meta_analyzer import meta_analyze
from .test_publication_bias_detector import ledger


class MetaTests(unittest.TestCase):
    def test_fixed_and_random_show_named_effect_and_heterogeneity(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.institute.meta-plan.v1", "source": ledger(root, [-1, 1], ["0.5", "0.5"]),
                    "method": "fixed", "confidence": "95"}
            fixed = meta_analyze(plan, identity(plan), root)
            self.assertEqual((fixed["pooled_effect"], fixed["q"], fixed["i_squared_bp"]), ("0", "8", 8750))
            self.assertEqual(fixed["tau_squared_dl"], "1.75")
            plan["method"] = "random_dl"
            random = meta_analyze(plan, identity(plan), root)
            self.assertGreater(Decimal(random["standard_error"]), Decimal(fixed["standard_error"]))
            self.assertEqual([r["weight_bp"] for r in random["studies"]], [5000, 5000])
