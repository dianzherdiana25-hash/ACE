"""Verifier gap jadwal, transisi, dan hasil probe kesehatan terkontrol."""
import unittest

from ace_software_factory import uptime_builder
from ace_software_factory._contracts import ContractError,identity


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.factory-uptime-plan.v1","source_ref":"fixture/monitor",
                   "from":"2026-01-01T00:00:00Z","until":"2026-01-01T00:01:00Z","cadence_seconds":20,
                   "max_delay_seconds":3,"components":[{"id":"api","port":9012,"path":"/health",
                                                        "ok_status":200,"source_ref":"fixture/api"},
                                                      {"id":"worker","port":9013,"path":"/health",
                                                       "ok_status":200,"source_ref":"fixture/worker"}]}
        self.anchor=identity(self.plan)

    def sample(self,when):
        return uptime_builder.probe(self.plan,self.anchor,when,client=lambda port,*args:{
            "status":200 if port==9012 else None,"error":None if port==9012 else "transport"})

    def test_records_all_probe_results_and_unknown_slots(self):
        data=self.sample("2026-01-01T00:00:21Z")
        self.assertEqual([item["state"] for item in data["rows"]],["up","down"])
        summary=uptime_builder.evaluate(self.plan,self.anchor,data)
        api,worker=summary["components"]
        self.assertEqual((api["up"],api["down"],api["unknown"]),(1,0,2))
        self.assertEqual(api["uptime_observed"],{"numerator":1,"denominator":1})
        self.assertEqual(api["uptime_lower_bound"],{"numerator":1,"denominator":3})
        self.assertEqual([row["to"] for row in worker["transitions"]],["unknown","down","unknown"])
        self.assertEqual(worker["transitions"][1]["at"],"2026-01-01T00:00:20Z")

    def test_missing_all_observations_and_late_delay(self):
        early=self.sample("2026-01-01T00:00:00Z")
        early["rows"]=[]
        report=uptime_builder.evaluate(self.plan,self.anchor,early)
        self.assertIsNone(report["components"][0]["uptime_observed"])
        with self.assertRaisesRegex(ContractError,"slot"):
            self.sample("2026-01-01T00:00:24Z")
