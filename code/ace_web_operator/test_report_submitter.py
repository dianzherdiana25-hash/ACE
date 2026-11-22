"""Verifier proyeksi metrik yang hanya mengisi form dan menolak data hilang."""
import unittest

from ace_web_operator import report_submitter
from ace_web_operator._contracts import identity


class ReportsTests(unittest.TestCase):
    def setUp(self):
        self.form={"schema":"ace.web.form-plan.v1","source_ref":"fixture/form","path":"/","fields":[
            {"id":"total","kind":"text","test_id":"total_box","required":True,"max_chars":10,"choices":[],
             "source_ref":"fixture/field"}],"browser":{"origin":"http://127.0.0.1:9010","allow_paths":["/"],
             "timeout_ms":250,"request_limit":2}}
        self.report={"schema":"ace.web.period-records.v1","source_ref":"fixture/records","rows":[
            {"id":key,"metric":"views","at":when,"count":count,"source_ref":"fixture/"+key,"evidence_sha256":"a"*64}
            for key,when,count in (("one","2026-01-01T00:05:00Z",3),("two","2026-01-01T00:06:00Z",4),
                                   ("excluded","2026-01-02T00:00:00Z",99))]}
        self.plan={"schema":"ace.web.period-report-plan.v1","source_ref":"fixture/report","form_sha256":identity(self.form),
                   "from":"2026-01-01T00:00:00Z","until":"2026-01-02T00:00:00Z",
                   "mapping":[{"field":"total","metric":"views","source_ref":"fixture/mapping"}]}

    def rehearse(self,browser):
        self.plan["report_sha256"]=identity(self.report)
        return report_submitter.rehearse(self.plan,identity(self.plan),self.report,self.form,browser=browser)

    def test_period_aggregate_computes_value_and_never_submits(self):
        def browser(config,anchor):
            self.assertEqual([item["op"] for item in config["steps"]],["navigate","fill"])
            self.assertEqual(config["steps"][-1]["value"],"7")
            return {"plan_sha256":anchor,"status":"completed","reason":None,
                    "steps":[{"id":item["id"],"status":"ok"} for item in config["steps"]]}
        receipt=self.rehearse(browser)
        self.assertEqual(receipt["status"],"filled_locally")
        self.assertEqual(len(receipt["fields"][0]["inputs"]),2)
        self.assertFalse(receipt["submitted"])

    def test_missing_metric_writes_no_form(self):
        self.report["rows"]=[]
        outcome=self.rehearse(lambda *args:self.fail("browser cannot run"))
        self.assertEqual(outcome["reason"],"missing_metric")
