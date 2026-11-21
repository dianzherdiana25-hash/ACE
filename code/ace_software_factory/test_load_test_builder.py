"""Verifier laju terkendali, timeout, dan respons HTTP produk lokal."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import unittest

from ace_software_factory import load_test_builder as model
from ace_software_factory._contracts import ContractError,identity


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path=="/alive" else 503)
        self.send_header("Content-Length","2")
        self.end_headers()
        self.wfile.write(b"{}")


class LoadTests(unittest.TestCase):
    def plan(self,port):
        return {"schema":"ace.factory-load-plan.v1","source_ref":"fixture/load","host":"127.0.0.1",
                "port":port,"rate":12,"workers":2,"timeout_seconds":3,"max_p95_ns":3_000_000_000,
                "cases":[{"id":"health","path":"/alive","count":3,"accept_status":200,"source_ref":"fixture/0"},
                         {"id":"missing","path":"/stopped","count":1,"accept_status":200,"source_ref":"fixture/1"}]}

    def test_real_http_and_status_errors_have_separate_receipts(self):
        fixture=self.enterContext(ThreadingHTTPServer(("127.0.0.1",0),Handler))
        runner=Thread(target=fixture.serve_forever,daemon=True)
        runner.start()
        self.addCleanup(runner.join,4)
        self.addCleanup(fixture.shutdown)
        plan=self.plan(fixture.server_port)
        report=model.run(plan,identity(plan))
        self.assertEqual((report["requests"],report["failed"],report["status"]),(4,1,"failed"))
        self.assertEqual([entry["status"] for entry in report["measurements"]],[200,200,200,503])
        self.assertGreater(report["statistics"]["min_ns"],0)

    def test_explicit_timeout_no_fabricated_latency_and_rate_budget(self):
        plan=self.plan(9001)
        now=[0.0]
        waiting=[]
        def tick(delta):
            waiting.append(delta)
            now[0]+=delta
        report=model.run(plan,identity(plan),clock=lambda:now[0],wait=tick,probe=lambda *args:{
            "status":None,"error":"timeout","received_bytes":None,"elapsed_ns":1})
        self.assertIsNone(report["statistics"])
        self.assertTrue(all(row["error"]=="timeout" for row in report["measurements"]))
        self.assertEqual(len(waiting),3)
        self.assertAlmostEqual(sum(waiting),3/12)

    def test_refuses_nonloopback_before_probe(self):
        plan=self.plan(9001)
        plan["host"]="fixture.invalid"
        with self.assertRaisesRegex(ContractError,"loopback"):
            model.run(plan,identity(plan),probe=lambda *args:self.fail("probe di luar konfigurasi"))
