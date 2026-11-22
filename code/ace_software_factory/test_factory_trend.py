"""Verifier rate per permukaan, gap dan lintasan perubahan antar-run."""
import unittest

from ace_software_factory import factory_trend
from ace_software_factory._contracts import ContractError,identity


def evidence(key,at,rows):
    products=[]
    for name,surface,status in rows:
        products.append({"product_id":name,"surface":surface,"artifact_sha256":"b"*64,
                         "acceptance":f"fixture/{key}/{name}.json","status":status,
                         "counts":{"passed":int(status=="passed"),"failed":int(status=="failed"),"missing_rule":0,
                                   "missing_observation":int(status=="incomplete")}})
    total=sum(row["status"]=="passed" for row in products)
    bench={"schema":"ace.factory-bench-report.v1","plan_sha256":"a"*64,"source_ref":f"fixture/{key}",
           "product_count":len(products),"passed":total,"status":"passed" if total==len(products) else "failed",
           "products":products}
    return {"id":key,"ref":f"fixture/history/{key}","at":at,"bench_sha256":identity(bench),"bench":bench}


class TrendTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-trend-history.v1","source_ref":"fixture/history","runs":[
            evidence("later","2026-01-02T00:00:00Z",[("a","cli","failed"),("c","service","incomplete")]),
            evidence("early","2026-01-01T00:00:00Z",[("a","cli","passed"),("b","web","passed")])]}

    def check(self):
        return factory_trend.summarize(self.plan,identity(self.plan))

    def test_denominator_and_change_reason_are_derived_from_evidence(self):
        result=self.check()
        self.assertEqual([row["id"] for row in result["timeline"]],["early","later"])
        self.assertEqual(result["by_surface"]["cli"]["pass_rate_bp"],5000)
        self.assertEqual(result["by_surface"]["service"]["incomplete"],1)
        self.assertIsNone(result["by_surface"]["service"]["pass_rate_bp"])
        self.assertEqual({item["product_id"]:item["reason"] for item in result["changes"]},
                         {"a":"verdict_changed","b":"product_removed","c":"product_added"})

    def test_wrong_bench_anchor_rejected_and_empty_history_reported(self):
        self.plan["runs"][0]["bench_sha256"]="0"*64
        with self.assertRaisesRegex(ContractError,"anchor"):
            self.check()
        self.plan["runs"]=[]
        result=self.check()
        self.assertEqual(result["run_count"],0)
        self.assertIsNone(result["by_surface"]["web"]["pass_rate_bp"])
