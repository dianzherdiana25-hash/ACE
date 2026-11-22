from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .model_builder import fit
from .test_data_analyst import column, table


class ModelTests(unittest.TestCase):
    def test_coefficients_and_holdout_baseline_use_only_training_rows(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref, spec = table(root, b"x,z,y\n0,0,3\n1,0,5\n0,1,2\n1,1,4\n3,2,7\n4,1,10\n",
                              [column(name, "integer") for name in "xzy"])
            plan = {"schema": "ace.institute.regression-plan.v1", "data": ref, "format": spec,
                    "features": ["x", "z"], "target": "y", "training_through_line": 5}
            result = fit(plan, identity(plan), root)
            self.assertEqual(result["coefficient"], {"intercept": "3", "x": "2", "z": "-1"})
            self.assertEqual(result["training_n"], 4)
            self.assertEqual([r["line"] for r in result["predictions"]], [6, 7])
            self.assertEqual(result["holdout_mae"], "0")
            self.assertEqual(result["baseline_mae"], "5")
            plan["training_through_line"] = 4
            with self.assertRaisesRegex(ResearchError, "koefisien"):
                fit(plan, identity(plan), root)
