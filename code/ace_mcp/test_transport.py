"""Loopback MCP HTTP bearer/origin/transport regression tests."""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from .bridge import ACEBridge, PROTOCOL
from .server import make_http_server, MAX_REQUEST_BYTES


class HTTPTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.token="test-mcp-token-only-local-0123456789abcdef"
        self.server=make_http_server("127.0.0.1",0,
                  ACEBridge(Path(temp.name)/"state"),
                  token=self.token,allowed_origins=("https://trusted.example",))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def exchange(self,method="POST",headers=None,body=None,path="/mcp"):
        payload=json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/list"}) if body is None else body
        connection=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        try:
            connection.request(method,path,body=payload if method=="POST" else None,
                               headers=headers if headers is not None else {})
            response=connection.getresponse()
            status=response.status
            data=response.read()
            return status, json.loads(data) if data else None
        finally:
            connection.close()

    def auth_headers(self):
        return {"Authorization":"Bearer "+self.token,
                "Content-Type":"application/json",
                "MCP-Protocol-Version":PROTOCOL}

    def test_missing_or_bad_bearer_rejected(self):
        self.assertEqual(401,self.exchange(headers={"Content-Type":"application/json"})[0])
        headers=self.auth_headers()
        headers["Authorization"]="Bearer wrong"
        self.assertEqual(401,self.exchange(headers=headers)[0])

    def test_origin_rejection_before_rpc(self):
        headers=self.auth_headers()
        headers["Origin"]="https://untrusted.example"
        self.assertEqual(403,self.exchange(headers=headers)[0])

    def test_valid_initialized_and_tool_list(self):
        headers=self.auth_headers()
        headers["Origin"]="https://trusted.example"
        status,obj=self.exchange(headers=headers)
        self.assertEqual(200,status)
        self.assertEqual(6,len(obj["result"]["tools"]))

    def test_malformed_content_type_protocol_and_length(self):
        headers=self.auth_headers()
        headers["Content-Type"]="text/plain"
        self.assertEqual(415,self.exchange(headers=headers)[0])
        headers=self.auth_headers()
        headers["MCP-Protocol-Version"]="invalid-version"
        self.assertEqual(400,self.exchange(headers=headers)[0])
        headers=self.auth_headers()
        headers["Content-Length"]=str(MAX_REQUEST_BYTES+1)
        self.assertEqual(413,self.exchange(headers=headers)[0])

    def test_readonly_write_call_fails(self):
        body=json.dumps({"jsonrpc":"2.0","id":8,"method":"tools/call",
                         "params":{"name":"ace_run_tasks","arguments":{"max_tasks":1}}})
        status,resp=self.exchange(headers=self.auth_headers(),body=body)
        self.assertEqual(200,status)
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("disabled",resp["result"]["content"][0]["text"])

    def test_get_mcp_does_not_stream_or_expose_data(self):
        status,_=self.exchange(method="GET",headers=self.auth_headers())
        self.assertEqual(405,status)
        status,_=self.exchange(method="GET",headers={})
        self.assertEqual(401,status)

    def test_no_public_binding_and_weak_token(self):
        with self.assertRaises(ValueError):
            make_http_server("0.0.0.0",0,ACEBridge("/tmp/test"),token=self.token)
        with self.assertRaises(ValueError):
            make_http_server("127.0.0.1",0,ACEBridge("/tmp/test"),token="short")

    def test_valid_notification_returns_202(self):
        body=json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})
        status,obj=self.exchange(headers=self.auth_headers(),body=body)
        self.assertEqual(202,status)
        self.assertIsNone(obj)


if __name__=="__main__":
    unittest.main()
