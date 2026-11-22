from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .test_data_analyst import column, table
from .trend_analyst import trends


class TrendsTests(unittest.TestCase):
    def test_day_slope_and_window_differentials_use_not_row_spacing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            pointer, spec = table(root, b"date,value\n2025-01-01,0\n2025-01-02,2\n2025-01-05,8\n2025-01-06,10\n",
                                 [column("date", "date"), column("value", "decimal")])
            plan = {"schema": "ace.institute.trend-plan.v1", "data": pointer, "format": spec, "date": "date",
                    "value": "value", "expected_gap_days": 1, "comparison_days": 2}
            result = trends(plan, identity(plan), root)
            self.assertEqual(result["slope_per_day"], "2")
            self.assertEqual(result["window_change"]["delta"], "8")
            self.assertEqual(result["calendar_gaps"][0]["source_lines"], [3, 4])
            self.assertEqual(result["calendar_gaps"][0]["days"], 3)
            plan["comparison_days"] = 6
            self.assertIsNone(trends(plan, identity(plan), root)["window_change"])
