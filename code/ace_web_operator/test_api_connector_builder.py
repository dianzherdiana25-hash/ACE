"""Verifier dokumentasi ke kontrak path serta larangan URL di dokumentasi."""
import unittest

from ace_web_operator import api_connector_builder
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator._http import Observation


def sample(port):
    need={"in":"path","required":True,"name":"key","schema":{"type":"integer"}}
    response={"type":"object","properties":{"label":{"type":"string"}},"required":["label"],"additionalProperties":False}
    document={"openapi":"3.1.0","servers":[{"url":"https://not-used.invalid"}],
              "paths":{"/things/{key}":{"get":{"parameters":[need],"responses":{
                  "200":{"content":{"application/json":{"schema":response}}}}}}}}
    plan={"schema":"ace.web.connector-plan.v1","id":"things","source_ref":"fixture/openapi",
          "document_sha256":identity(document),"origin":f"http://127.0.0.1:{port}","max_response":500,
          "operations":[{"id":"lookup","path":"/things/{key}","ref":"fixture/lookup"}]}
    return document,plan


class ConnectorTests(unittest.TestCase):
    def test_compiles_data_connector_using_only_explicit_loopback_origin(self):
        docs,plan=sample(9002)
        config=api_connector_builder.compile_connector(docs,plan,identity(plan))
        def server(base,path,cap):
            self.assertEqual((base,path,cap),("http://127.0.0.1:9002","/things/3",500))
            return Observation(200,"application/json",b'{"label":"Sampel"}',None)
        body,receipt=api_connector_builder.invoke(config,identity(config),"lookup",{"key":3},transport=server)
        self.assertEqual(body,{"label":"Sampel"})
        self.assertEqual(receipt["status"],"verified")
        self.assertEqual(receipt["source_ref"],"fixture/lookup")
        self.assertNotIn("not-used",str(config))

    def test_refuses_nonliteral_path_data_and_security_from_spec(self):
        docs,plan=sample(9002)
        config=api_connector_builder.compile_connector(docs,plan,identity(plan))
        with self.assertRaises(ContractError):
            api_connector_builder.invoke(config,identity(config),"lookup",{"key":"../api"},
                                         transport=lambda *args:self.fail("transport called"))
        docs["security"]=[{"token":[]}]
        plan["document_sha256"]=identity(docs)
        with self.assertRaisesRegex(ContractError,"autentikasi"):
            api_connector_builder.compile_connector(docs,plan,identity(plan))
