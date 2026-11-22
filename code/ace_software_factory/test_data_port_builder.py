"""Verifier ekspor-impor CSV/JSON dengan sel berformula dan kolom nullable."""
import unittest

from ace_software_factory import data_port_builder as model
from ace_software_factory._contracts import ContractError, identity


class PortTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-data-port.v1","id":"records","source_ref":"fixture/schema",
                   "columns":[{"id":key,"type":kind,"nullable":nullable} for key,kind,nullable in
                              [("id","integer",False),("label","text",True),("visible","boolean",False)]],
                   "primary":["id"]}
        self.anchor=identity(self.plan)
        self.rows=[{"id":3,"label":"=lihat","visible":True},{"id":1,"label":None,"visible":False},
                   {"id":2,"label":"\\N","visible":True},{"id":4,"label":"Apa\r\nKabar","visible":False}]

    def test_types_order_and_formula_escape_round_trip(self):
        for format_name in ("csv","json"):
            with self.subTest(format=format_name):
                data,report=model.export(self.rows,self.plan,self.anchor,format_name)
                if format_name=="csv":
                    self.assertIn(b"'=lihat",data)
                    self.assertIn(b"'\\N",data)
                loaded,result=model.ingest(data,self.plan,self.anchor,format_name)
                self.assertEqual(loaded,sorted(self.rows,key=lambda row:row["id"]))
                self.assertEqual(result,report)

    def test_refuses_wrong_columns_and_csv_with_unescaped_formula(self):
        header=b"id,label,visible\r\n"
        with self.assertRaisesRegex(ContractError,"record 1"):
            model.ingest(header+b"3,=bad,true\r\n",self.plan,self.anchor,"csv")
        with self.assertRaisesRegex(ContractError,"Header"):
            model.ingest(b"id,visible,label\r\n",self.plan,self.anchor,"csv")

    def test_duplicate_id_rejected_regardless_of_other_columns(self):
        with self.assertRaisesRegex(ContractError,"ganda"):
            model.export(self.rows+[{**self.rows[0],"label":"different"}],self.plan,self.anchor,"json")
