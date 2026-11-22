from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .publication_bias_detector import asymmetry
from .test_comparison_analyst import save


def ledger(root, estimates, errors):
    file = {"schema": "ace.institute.effect-series.v1", "effect_kind": "standardized",
            "studies": [{"id": f"s{i}", "independence_group": f"g{i}", "effect": estimate, "standard_error": se,
                         "sample_size": 20 + i, "source_ref": f"fixture:study{i}"}
                        for i, (estimate, se) in enumerate(zip(estimates, errors, strict=True))]}
    return save(root, "studies.json", canonical(file))


class AsymmetryTests(unittest.TestCase):
    def test_exact_permutations_and_indeterminate_constant_errors(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.institute.asymmetry-plan.v1", "source": ledger(root, [1, 2, 3, 4, 5], [1, 2, 3, 4, 5]),
                    "alpha": "0.02"}
            signal = asymmetry(plan, identity(plan), root)
            self.assertEqual((signal["p_exact"], signal["permutations"]), ([1, 60], 120))
            self.assertEqual(signal["status"], "asymmetry_signal")
            plan["source"] = ledger(root, [1, 2, 3, 4, 5], [2] * 5)
            self.assertIsNone(asymmetry(plan, identity(plan), root)["p_exact"])
