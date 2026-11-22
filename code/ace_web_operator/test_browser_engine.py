"""Uji Chromium terhadap situs loopback dan batas kontrak browser."""
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import shutil
import subprocess
import unittest

from ace_web_operator import browser_engine
from ace_web_operator._contracts import ContractError, identity


HTML = b'''<!doctype html><html lang="id"><head><title>Unit lokal</title></head><body>
<label>Nama<input data-testid="name"></label>
<button data-testid="mark" onclick="document.querySelector('[data-testid=out]').textContent='Selesai'">Tandai</button>
<p data-testid="out">Awal</p><button data-testid="forbidden" onclick="fetch('/outside').catch(()=>{})">Cek pagar</button>
</body></html>'''


def browser_available():
    node = shutil.which("node")
    return bool(node and shutil.which("chromium") and (
        subprocess.run([node,"-e",'require.resolve("playwright")'], cwd=Path(__file__).parent,
                       capture_output=True, timeout=5).returncode == 0))


class LocalSite(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        self.server.visited.append(self.path)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/outside")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.send_header("Content-Length",str(len(HTML)))
        self.end_headers()
        self.wfile.write(HTML)


def fixture(test):
    http=test.enterContext(ThreadingHTTPServer(("127.0.0.1",0),LocalSite))
    http.visited=[]
    thread=Thread(target=http.serve_forever,daemon=True)
    thread.start()
    test.addCleanup(thread.join,3)
    test.addCleanup(http.shutdown)
    return http


def plan(port):
    return {"schema":"ace.web.browser-plan.v1","source_ref":"fixture/local-site","origin":f"http://127.0.0.1:{port}",
            "allow_paths":["/","/favicon.ico"],"request_limit":8,"timeout_ms":2000,
            "steps":[{"id":"get_home","op":"navigate","path":"/"},{"id":"page_title","op":"expect_title","expected":"Unit lokal"},
                     {"id":"set_name","op":"fill","test_id":"name","value":"fixture text"},
                     {"id":"mark","op":"click","test_id":"mark"},
                     {"id":"read","op":"expect_text","test_id":"out","expected":"Selesai"}]}


class BrowserTests(unittest.TestCase):
    def test_real_chromium_only_releases_typed_evidence_and_fixture_receipts(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        http=fixture(self)
        config=plan(http.server_port)
        result=browser_engine.run(config,identity(config))
        self.assertEqual(result["status"],"completed",result)
        self.assertEqual(result["steps"][-1]["evidence"]["text_sha256"],sha256(b"Selesai").hexdigest())
        self.assertNotIn("fixture text",str(result))
        self.assertIn("/",http.visited)

    def test_tampered_anchor_nonloopback_and_unregistered_navigation_are_refused(self):
        config=plan(9001)
        with self.assertRaisesRegex(ContractError,"anchor"):
            browser_engine.run(config,"a"*64)
        config["origin"]="http://localhost:9001"
        with self.assertRaisesRegex(ContractError,"loopback"):
            browser_engine.run(config,identity(config))
        config=plan(9001)
        config["steps"][0]["path"]="/witness"
        with self.assertRaisesRegex(ContractError,"terdaftar"):
            browser_engine.run(config,identity(config))

    def test_actual_request_outside_paths_does_not_reach_loopback_server(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        http=fixture(self)
        config=plan(http.server_port)
        config["steps"]=[config["steps"][0],{"id":"blocked_click","op":"click","test_id":"forbidden"},
                         {"id":"next","op":"expect_text","test_id":"out","expected":"Selesai"}]
        result=browser_engine.run(config,identity(config))
        self.assertEqual(result["status"],"failed",result)
        self.assertNotIn("/outside",http.visited)


    def test_redirect_never_skips_path_filter(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        http=fixture(self)
        config=plan(http.server_port)
        config["allow_paths"].append("/redirect")
        config["steps"]=[{"id":"redirect","op":"navigate","path":"/redirect"}]
        result=browser_engine.run(config,identity(config))
        self.assertEqual((result["status"],result["reason"]),("failed","request_rejected"))
        self.assertNotIn("/outside",http.visited)
