"""Verifier audit dashboard yang menautkan SKU dan menahan mutasi."""
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest

from ace_web_operator import shop_operator,web_ops_bench
from ace_web_operator._contracts import ContractError,identity
from ace_web_operator.test_browser_engine import browser_available


class ShopTests(unittest.TestCase):
    def setup_plan(self,port):
        base=f"http://127.0.0.1:{port}"
        roster={"schema":"ace.web.shop-inventory.v1","source_ref":"fixture/stock","shop":"demo_shop","origin":base,
                "items":[{"sku":"crate","stock":4,"stock_test_id":"quantity","source_ref":"fixture/crate"}]}
        config={"schema":"ace.web.shop-inspection.v1","source_ref":"fixture/audit",
                "inventory_sha256":identity(roster),"approval_ref":"fixture/read","shop":"demo_shop","path":"/stock",
                "owner_test_id":"owner","owner_label":"Demo Shop",
                "browser":{"origin":base,"allow_paths":["/stock","/favicon.ico"],"timeout_ms":1500,"request_limit":10}}
        return config,roster

    def test_real_dashboard_proves_ownership_and_inventory_read(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        fixture=self.enterContext(ThreadingHTTPServer(("127.0.0.1",0),web_ops_bench.FixtureHandler))
        fixture.pages={"/stock":("text/html",b'<h1 data-testid="owner">Demo Shop</h1><p data-testid="quantity">4 unit</p>'),
                       "/favicon.ico":("text/plain",b"icon")}
        fixture.requests=[]
        thread=Thread(target=fixture.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,3)
        self.addCleanup(fixture.shutdown)
        cfg,roster=self.setup_plan(fixture.server_port)
        result=shop_operator.inspect(cfg,identity(cfg),roster)
        self.assertEqual(result["status"],"inventory_confirmed",result)
        self.assertEqual(result["items"][0]["source_ref"],"fixture/crate")
        self.assertTrue(all(method=="GET" for method,_ in fixture.requests))

    def test_shop_mismatch_and_mutating_route_are_rejected(self):
        cfg,roster=self.setup_plan(9009)
        cfg["shop"]="other"
        with self.assertRaisesRegex(ContractError,"toko"):
            shop_operator.compile_inspection(cfg,identity(cfg),roster)
        cfg["shop"]="demo_shop"
        cfg["browser"]["allow_paths"].append("/stock/publish")
        with self.assertRaisesRegex(ContractError,"mutasi"):
            shop_operator.compile_inspection(cfg,identity(cfg),roster)
