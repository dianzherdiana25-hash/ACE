"""Verifier alamat A1 hingga AA, data bertipe, dan rumus yang ditolak."""
import unittest

from ace_web_operator import web_sheet_filler
from ace_web_operator._contracts import ContractError,identity


class SheetTests(unittest.TestCase):
    def setUp(self):
        self.sheet={"schema":"ace.web.sheet-data.v1","source_ref":"fixture/sheet","rows":[["Satu",2],[True,-4]]}
        self.plan={"schema":"ace.web.sheet-plan.v1","source_ref":"fixture/grid","sheet_sha256":identity(self.sheet),
                   "browser":{"origin":"http://127.0.0.1:9010","allow_paths":["/grid"],"timeout_ms":500,"request_limit":3},
                   "path":"/grid","start":"Z9","selector_prefix":"cell"}

    def compile(self):
        self.plan["sheet_sha256"]=identity(self.sheet)
        return web_sheet_filler.compile_grid(self.plan,identity(self.plan),self.sheet)

    def test_addresses_numeric_and_boolean_values_into_document_order(self):
        program,cells,_=self.compile()
        self.assertEqual([row["cell"] for row in cells],["Z9","AA9","Z10","AA10"])
        fill=[(row["test_id"],row["value"]) for row in program["steps"] if row["op"]=="fill"]
        self.assertEqual(fill,[("cell_z9","Satu"),("cell_aa9","2"),("cell_z10","true"),("cell_aa10","-4")])

    def test_rejects_formula_and_jagged_rows_before_opening_browser(self):
        self.sheet["rows"][0][0]=" =SUM(1,2)"
        with self.assertRaisesRegex(ContractError,"Rumus"):
            self.compile()
        self.sheet["rows"][0][0]="Word"
        self.sheet["rows"][1].pop()
        with self.assertRaisesRegex(ContractError,"persegi"):
            self.compile()
