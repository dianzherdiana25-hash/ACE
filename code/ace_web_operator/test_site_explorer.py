"""Verifier navigasi dari tautan loopback dan anggaran kecukupan."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import unittest

from ace_web_operator import site_explorer
from ace_web_operator._contracts import ContractError,identity


PAGES={
    "/":b'<a href="/manual/b">B</a><a href="/manual/a">A</a><a href="/hidden">deny</a><a href="//else.invalid">foreign</a>',
    "/manual/a":b'<a href="/manual/deep">D</a><a href="/">home</a>',
    "/manual/b":b'<a href="/manual/a">dup</a>',
    "/manual/deep":b"Leaf",
}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        self.server.visited.append(self.path)
        page=PAGES.get(self.path,b"missing")
        self.send_response(200 if self.path in PAGES else 404)
        self.send_header("Content-Type","text/html")
        self.send_header("Content-Length",str(len(page)))
        self.end_headers()
        self.wfile.write(page)


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.server=self.enterContext(ThreadingHTTPServer(("127.0.0.1",0),Fixture))
        self.server.visited=[]
        runner=Thread(target=self.server.serve_forever,daemon=True)
        runner.start()
        self.addCleanup(runner.join,3)
        self.addCleanup(self.server.shutdown)
        self.raw={"schema":"ace.web.explore-plan.v1","source_ref":"fixture/crawl","origin":f"http://127.0.0.1:{self.server.server_port}",
                  "entry":"/","allow_prefixes":["/"],"deny_prefixes":["/hidden"],"max_pages":3,"max_depth":2,
                  "max_bytes":1200,"min_spacing_ms":80}

    def explore(self):
        return site_explorer.explore(self.raw,identity(self.raw),wait=lambda delay:self.assertEqual(delay,0.08))

    def test_real_crawl_is_breadth_first_and_reports_frontier(self):
        result=self.explore()
        self.assertEqual(self.server.visited,["/","/manual/a","/manual/b"])
        self.assertEqual(result["pages"][0]["rejected_links"],2)
        self.assertEqual(result["frontier"],[{"path":"/manual/deep","from":"/manual/a","reason":"page_budget"}])

    def test_depth_limit_and_blocked_entry_are_observable(self):
        self.raw["max_depth"]=0
        result=self.explore()
        self.assertEqual({row["reason"] for row in result["frontier"]},{"depth_limit"})
        self.raw["entry"]="/hidden"
        with self.assertRaisesRegex(ContractError,"rute"):
            self.explore()
