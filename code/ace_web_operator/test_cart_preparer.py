"""Verifier batas keranjang dan simulasi DOM browser tanpa checkout."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import unittest

from ace_web_operator import cart_preparer
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available


PAGE=b'''<html><body><input type="number" data-testid="ring_units"><p data-testid="summary">0 item</p>
<button data-testid="add_ring" onclick="document.querySelector('[data-testid=summary]').textContent =
document.querySelector('[data-testid=ring_units]').value+' item'">Tambah</button></body></html>'''


class LocalPage(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        self.server.seen.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.send_header("Content-Length",str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)


class CartTests(unittest.TestCase):
    def config(self,port):
        catalog={"schema":"ace.web.fixture-catalog.v1","source_ref":"fixture/catalog","items":[
            {"id":"ring","stock":5,"unit_minor":4,"amount_test_id":"ring_units","add_test_id":"add_ring",
             "source_ref":"fixture/row"}]}
        raw={"schema":"ace.web.cart-plan.v1","source_ref":"fixture/prep","catalog_sha256":identity(catalog),
             "browser":{"origin":f"http://127.0.0.1:{port}","allow_paths":["/catalog","/favicon.ico"],
                        "timeout_ms":1500,"request_limit":5},
             "page":"/catalog","summary_test_id":"summary","max_minor_units":10,
             "cart":[{"item":"ring","quantity":2}]}
        return raw,catalog

    def test_cart_refuses_budget_and_checkout_route_before_activity(self):
        raw,catalog=self.config(9010)
        raw["max_minor_units"]=7
        with self.assertRaisesRegex(ContractError,"batas"):
            cart_preparer.prepare(raw,identity(raw),catalog,browser=lambda *args:self.fail("browser called"))
        raw["browser"]["allow_paths"].append("/checkout")
        with self.assertRaisesRegex(ContractError,"checkout"):
            cart_preparer.compile_cart(raw,identity(raw),catalog)

    def test_real_dom_records_only_local_cart_preparation(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        server=self.enterContext(ThreadingHTTPServer(("127.0.0.1",0),LocalPage))
        server.seen=[]
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,3)
        self.addCleanup(server.shutdown)
        raw,catalog=self.config(server.server_port)
        report=cart_preparer.prepare(raw,identity(raw),catalog)
        self.assertEqual(report["status"],"prepared_locally",report)
        self.assertFalse(report["checkout"])
        self.assertEqual(report["total_minor_fixture"],8)
        self.assertTrue(set(server.seen)<={"/catalog","/favicon.ico"})
