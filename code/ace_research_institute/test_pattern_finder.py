from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .pattern_finder import find_patterns
from .test_data_analyst import column, table


class PatternTests(unittest.TestCase):
    def test_outlier_between_ramps_and_zero_mad_are_present(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref, spec = table(root, b"group,day,value\na,1,1\na,2,2\na,3,3\na,4,30\na,5,5\na,6,4\n"
                                    b"b,1,2\nb,2,2\nb,2,2\n",
                              [column("group", "category"), column("day", "integer"), column("value", "integer")])
            plan = {"schema": "ace.institute.pattern-plan.v1", "data": ref, "format": spec,
                    "value": "value", "order": "day", "group": "group", "minimum_run": 3, "mad_multiplier": "4"}
            answer = find_patterns(plan, identity(plan), root)
            first, second = answer["groups"]
            self.assertEqual([r["line"] for r in first["anomalies"]], [5])
            self.assertEqual([(r["trend"], r["length"]) for r in first["runs"]], [("increase", 4), ("decrease", 3)])
            self.assertEqual(second["anomaly_status"], "mad_zero")
            self.assertEqual(second["duplicate_order_lines"], [10])
            self.assertEqual(second["runs"], [])
