"""Verifier exchange offline untuk nilai benar dan schema mismatch."""
import unittest

from ace_web_operator import api_connector_builder,connector_sandbox
from ace_web_operator._contracts import identity
from ace_web_operator.test_api_connector_builder import sample


class SandboxTests(unittest.TestCase):
    def setUp(self):
        docs,plan=sample(9010)
        self.connector=api_connector_builder.compile_connector(docs,plan,identity(plan))
        self.suite={"schema":"ace.web.connector-sandbox.v1","source_ref":"fixture/contract",
                    "connector_sha256":identity(self.connector),"cases":[]}
        for key,body,passed in (("valid",{"label":"ok"},True),("bad",{"label":False},False)):
            self.suite["cases"].append({"id":key,"operation":"lookup","parameters":{"key":5},
                "exchange":{"path":"/things/5","status":200,"media_type":"application/json","body":body},
                "expected":{"status":"verified" if passed else "held","reason":None if passed else "schema_mismatch",
                            "body":body if passed else None},"source_ref":f"fixture/{key}"})

    def run_fixture(self):
        return connector_sandbox.run(self.connector,self.suite,identity(self.suite))

    def test_exact_assertions_verifiable_without_http_transport(self):
        result=self.run_fixture()
        self.assertEqual(result["status"],"verified")
        self.assertEqual([row["receipt"]["reason"] for row in result["cases"]],[None,"schema_mismatch"])
        self.assertTrue(all(row["matched"] for row in result["cases"]))

    def test_mismatched_route_reports_failing_case(self):
        self.suite["cases"][1]["exchange"]["path"]="/wrong"
        result=self.run_fixture()
        self.assertEqual(result["failed_cases"],["bad"])
        self.assertEqual(result["cases"][1]["receipt"]["reason"],"fixture_route_mismatch")
