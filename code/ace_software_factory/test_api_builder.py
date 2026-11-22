"""Verifier builder API dengan HTTP loopback dan SQLite fixture."""
from http.client import HTTPConnection
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from ace_software_factory import api_builder as model
from ace_software_factory.repo_scaffolder import materialize
from ace_software_factory.test_schema_designer import repository


def settings(source):
    return {"schema":"ace.factory-api-plan.v1","plan_ref":"fixture/API","model_sha256":model.identity(source),
            "resources":[{"route":"categories","table":"category","read":["id","name"],"write":["name"],
                          "methods":["GET","POST","PATCH","DELETE"],"source_ref":"fixture/categories"},
                         {"route":"items","table":"item","read":["id","category_id","visible"],"write":["category_id","visible"],
                          "methods":["GET","POST"],"source_ref":"fixture/items"}]}


class APITests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))
        self.source=repository()
        self.plan=settings(self.source)

    def actual(self):
        files,report=model.build(self.source,self.plan,model.identity(self.plan))
        artifact=self.root/"generated"
        materialize(artifact,files)
        specs=spec_from_file_location("fixture_backend",artifact/"backend.py")
        module=module_from_spec(specs)
        specs.loader.exec_module(module)
        endpoint=self.enterContext(module.server(self.root/"data.sqlite"))
        thread=Thread(target=endpoint.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)
        self.addCleanup(endpoint.shutdown)
        return endpoint.server_port,report

    def request(self,port,method,path,body=None,headers=None):
        request={} if headers is None else dict(headers)
        if body is not None:
            if not isinstance(body,bytes):
                body=json.dumps(body).encode()
            request["Content-Type"]="application/json"
        conn=HTTPConnection("127.0.0.1",port,timeout=3)
        try:
            conn.request(method,path,body,headers=request)
            response=conn.getresponse()
            return response.status,json.loads(response.read())
        finally:
            conn.close()

    def test_actual_crud_and_read_only_fields_produce_expected_json(self):
        port,evidence=self.actual()
        self.assertEqual(evidence["resources"]["items"]["methods"],["GET","POST"])
        status,value=self.request(port,"POST","/categories",{"name":"fixture's label"})
        self.assertEqual((status,value),(201,{"id":1,"name":"fixture's label"}))
        self.assertEqual(self.request(port,"GET","/categories?limit=1"),(200,{"limit":1,"offset":0,"items":[value]}))
        self.assertEqual(self.request(port,"PATCH","/categories/1",{"name":"new"}),(200,{"id":1,"name":"new"}))
        self.assertEqual(self.request(port,"POST","/items",{"category_id":1,"visible":False}),
                         (201,{"id":1,"category_id":1,"visible":False}))
        self.assertEqual(self.request(port,"DELETE","/categories/1"),(200,{"deleted":1}))
        self.assertEqual(self.request(port,"GET","/items/1"),(200,{"id":1,"category_id":None,"visible":False}))
        self.assertEqual(self.request(port,"GET","/categories/1")[0],404)

    def test_guard_semantics_are_observed_from_generated_server(self):
        port,_=self.actual()
        for method,path,payload,answer in (
            ("POST","/items",{"category_id":99},409),
            ("POST","/items",{"visible":1},400),
            ("POST","/items",{"id":1},400),
            ("POST","/items",b'{"visible":true,"visible":false}',400),
            ("GET","/items?limit=1&limit=2",None,400),
            ("DELETE","/items/1",None,405),
        ):
            with self.subTest(method=method,path=path,answer=answer):
                self.assertEqual(self.request(port,method,path,payload)[0],answer)
        self.assertEqual(self.request(port,"GET","/items",headers={"Host":"fixture.invalid"})[0],400)

    def test_build_rejects_invalid_method_and_exposing_undeclared_columns(self):
        self.plan["resources"][0]["methods"].append("TRACE")
        with self.assertRaises(model.ContractError):
            model.build(self.source,self.plan,model.identity(self.plan))
        self.plan=settings(self.source)
        self.plan["resources"][0]["write"].append("id")
        with self.assertRaises(model.ContractError):
            model.build(self.source,self.plan,model.identity(self.plan))
