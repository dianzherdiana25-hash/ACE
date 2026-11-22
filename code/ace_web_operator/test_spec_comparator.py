"""Verifier konversi Decimal, preferensi, missing dan unit tidak cocok."""
import unittest

from ace_web_operator import spec_comparator
from ace_web_operator._contracts import identity


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.data={"schema":"ace.web.spec-snapshot.v1","source_ref":"fixture/specs","records":[
                   {"id":key,"source_ref":"fixture/"+key,"artifact_sha256":"a"*64,
                    "fields":{"height":{"value":value,"unit":unit,"source_ref":"fixture/height"}} if value else {}}
                   for key,value,unit in (("one","2","cm"),("two","21","mm"),("three","4","kg"),("four",None,None))]}
        self.plan={"schema":"ace.web.spec-compare-plan.v1","source_ref":"fixture/rule",
                   "fields":[{"id":"height","type":"length_mm","prefer":"less","tolerance":"0.1",
                              "source_ref":"fixture/tolerance"}]}

    def compare(self):
        self.plan["snapshot_sha256"]=identity(self.data)
        return spec_comparator.compare(self.plan,identity(self.plan),self.data)["fields"][0]

    def test_compatible_units_rank_without_guessing_missing_fields(self):
        result=self.compare()
        self.assertEqual(result["leaders"],["one"])
        self.assertEqual(result["comparable_count"],2)
        self.assertEqual({row["id"]:row["finding"] for row in result["values"]},
                         {"one":None,"two":None,"three":"incompatible_unit","four":"missing"})

    def test_tolerance_yields_tie_at_boundary(self):
        self.plan["fields"][0]["tolerance"]="1.0"
        result=self.compare()
        self.assertEqual((result["status"],result["leaders"]),("within_tolerance",[]))
