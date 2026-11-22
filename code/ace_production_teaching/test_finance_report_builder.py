from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .finance_report_builder import build_finance_report
from .test_tabular_engine import save


class FinanceTests(unittest.TestCase):
    def test_period_and_category_totals_recompute_and_input_bytes_remain(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = (b"id,date,kind,category,amount,currency\nx,2025-05-01,income,books,10.005,USD\n"
                   b"y,2025-05-31,cost,printing,3.15,USD\nz,2025-06-01,cost,printing,90,USD\n"
                   b"a,2025-05-10,income,books,0.99,USD\n")
            plan = {"schema": "ace.production.finance-report-plan.v1", "table": save(root, "fixture.csv", raw),
                    "title": "Laporan", "from": "2025-05-01", "through": "2025-05-31",
                    "currency": "USD", "minor_digits": 2, "formats": ["docx"]}
            _, receipt = build_finance_report(plan, identity(plan), root)
            self.assertEqual(receipt["totals"], {"income": "11.00", "cost": "3.15", "net": "7.85"})
            self.assertEqual(receipt["ignored_lines_outside_period"], [4])
            self.assertEqual(receipt["categories"][1]["source_lines"], [2, 5])
            self.assertEqual((root / "fixture.csv").read_bytes(), raw)
