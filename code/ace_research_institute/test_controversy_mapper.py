from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .controversy_mapper import map_controversy
from .test_literature_reviewer import DIMS, hypotheses
from .test_source_collector import source


class ControversyTests(unittest.TestCase):
    def test_compatible_cross_group_edges_and_connected_component(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            refs = hypotheses(root)
            refs["sources"].append(source(root, "third", "cohort_c", "| third | group | cahaya | lab | 35 | pct | 25 | 31 | 37 |"))
            plan = {"schema": "ace.institute.controversy-plan.v1", "sources": refs, "minimum_sample": 5,
                    "scopes": [{"dimensions": DIMS, "unit": "pct", "material_difference": "8"}]}
            scope = map_controversy(plan, identity(plan), root)["scopes"][0]
            self.assertEqual([o["source_id"] for o in scope["measurements"]], ["left", "right", "third"])
            self.assertEqual([r["delta"] for r in scope["conflicts"]], ["0.15", "0.11"])
            self.assertEqual(scope["components"], [[0, 1, 2]])
