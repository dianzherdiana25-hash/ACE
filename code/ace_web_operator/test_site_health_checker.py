"""Verifier slow, JSON type conflict, dan kegagalan transport terpisah."""
import unittest

from ace_web_operator import site_health_checker
from ace_web_operator._contracts import identity
from ace_web_operator._http import Observation


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.plan={"schema":"ace.web.health-plan.v1","source_ref":"fixture/check",
                   "sites":[{"id":"site","origin":"http://127.0.0.1:9010","source_ref":"fixture/origin"}],
                   "checks":[{"id":"health","site":"site","path":"/health","status":200,"media_type":"application/json",
                              "json_equals":{"key":"ready","value":True},"timeout_seconds":2,"latency_ms":50,
                              "source_ref":"fixture/health"}]}

    def result(self,response,elapsed):
        ticks=iter([0,elapsed])
        return site_health_checker.probe(self.plan,identity(self.plan),transport=lambda *args,**kwargs:response,
                                          clock=lambda:next(ticks))

    def test_latency_boundary_and_data_types(self):
        correct=Observation(200,"application/json",b'{"ready":true}',None)
        self.assertEqual(self.result(correct,50_000_000)["status"],"healthy")
        self.assertEqual(self.result(correct,50_000_001)["status"],"degraded")
        wrong=Observation(200,"application/json",b'{"ready":1}',None)
        self.assertEqual(self.result(wrong,1)["checks"][0]["reasons"],["body_assertion_failed"])

    def test_transport_failure_has_no_successful_http_or_body_proof(self):
        result=self.result(Observation(None,None,b"","transport_failed"),500)
        self.assertEqual(result["status"],"unhealthy")
        self.assertIsNone(result["checks"][0]["body_sha256"])
        self.assertIsNone(result["checks"][0]["http_status"])
