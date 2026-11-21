"""Verifier upstream loopback, batas rute dan pelepasan header dari klien."""
from contextlib import closing
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from ace_software_factory import api_gateway_builder
from ace_software_factory._contracts import ContractError, canonical, decode, identity
from ace_software_factory.repo_scaffolder import materialize


class OldAPI(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path == "/old":
            data = canonical({"ref": "old", "authorization_visible": self.headers.get("Authorization") is not None})
            self.send_response(200)
            self.send_header("Content-Type","application/json")
        else:
            data = b""
            self.send_response(301)
            self.send_header("Location","/old")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class GatewayTests(unittest.TestCase):
    def listen(self, server):
        self.enterContext(server)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.shutdown)
        return server.server_port

    def setUp(self):
        old = self.listen(ThreadingHTTPServer(("127.0.0.1",0),OldAPI))
        self.plan = {"schema": "ace.factory-gateway-plan.v1", "id": "local_api", "source_ref": "fixture/contract",
                     "timeout_seconds": 3, "max_bytes": 512,
                     "routes": [{"client_path": "/v1/data", "method": "GET", "upstream_host": "127.0.0.1",
                                 "upstream_port": old, "upstream_path": "/old", "source_ref": "fixture/route"},
                                {"client_path": "/v1/moved", "method": "GET", "upstream_host": "127.0.0.1",
                                 "upstream_port": old, "upstream_path": "/redirect", "source_ref": "fixture/moved"}]}

    def generated_server(self):
        files, receipt = api_gateway_builder.build(self.plan, identity(self.plan))
        root = Path(self.enterContext(TemporaryDirectory()))/"gateway"
        materialize(root,files)
        spec = spec_from_file_location("fixture_gateway",root/receipt["runtime"]["path"])
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return self.listen(module.server())

    def request(self, port, path, headers=None):
        with closing(HTTPConnection("127.0.0.1",port,timeout=5)) as conn:
            conn.request("GET",path,headers=headers or {})
            response = conn.getresponse()
            return response.status, decode(response.read())

    def test_gateway_uses_remapped_route_and_never_forwards_auth_header(self):
        port = self.generated_server()
        self.assertEqual(self.request(port, "/v1/data", {"Authorization": "fixture"}),
                         (200,{"ref":"old","authorization_visible":False}))
        self.assertEqual(self.request(port, "/v1/data?dynamic=yes")[0], 404)
        self.assertEqual(self.request(port, "/v1/moved"), (502,{"error":"upstream_status"}))

    def test_refuses_non_loopback_and_unregistered_path_form(self):
        self.plan["routes"][0]["upstream_host"] = "::1"
        with self.assertRaisesRegex(ContractError,"loopback"):
            api_gateway_builder.build(self.plan,identity(self.plan))
