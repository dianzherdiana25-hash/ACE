from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .market_analyst import analyze_market
from .test_data_analyst import column, table


class MarketTests(unittest.TestCase):
    def test_observed_totals_are_distinct_from_market_and_hhi_requires_complete_coverage(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ref, spec = table(root, b"period,maker,value\n1,A,6\n1,B,4\n2,A,8\n3,A,8\n",
                [column("period", "category"), column("maker", "category"), column("value", "decimal")])
            plan = {"schema": "ace.institute.market-plan.v1", "data": ref, "format": spec,
                    "columns": {"period": "period", "competitor": "maker", "amount": "value"},
                    "unit": "unit terukur", "market_totals": [
                        {"period": "1", "total": "10", "source_ref": "fixture:p1"},
                        {"period": "2", "total": "20", "source_ref": "fixture:p2"}]}
            first, second, third = analyze_market(plan, identity(plan), root)["periods"]
            self.assertEqual(first["hhi"], "5200")
            self.assertEqual(second["coverage_bp"], 4000)
            self.assertIsNone(second["hhi"])
            self.assertIsNone(third["competitors"][0]["market_share_bp"])
            plan["market_totals"][1]["total"] = "7"
            with self.assertRaisesRegex(ResearchError, "melebihi"):
                analyze_market(plan, identity(plan), root)
