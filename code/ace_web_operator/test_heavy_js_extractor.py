"""Verifier DOM yang baru ada setelah JavaScript mengisi data."""
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest

from ace_web_operator import heavy_js_extractor,web_ops_bench
from ace_web_operator._contracts import identity
from ace_web_operator.test_browser_engine import browser_available


DYNAMIC=b'''<p data-testid="ready">Loading</p><main data-testid="container"></main>
<script>setTimeout(()=>{
const row=document.createElement('article');row.className='entry';
const field=document.createElement('span');field.dataset.field='key';field.textContent='Fakta render';
row.append(field);document.querySelector('main').append(row);document.querySelector('p').textContent='Siap (1).';
},170)</script>'''


class RenderTests(unittest.TestCase):
    def test_extracts_rendered_dom_with_ready_witness_and_hash(self):
        if not browser_available():
            self.skipTest("Chromium, Node, atau Playwright lokal tidak tersedia")
        server=self.enterContext(ThreadingHTTPServer(("127.0.0.1",0),web_ops_bench.FixtureHandler))
        server.pages={"/render":("text/html",DYNAMIC),"/favicon.ico":("text/plain",b"icon")}
        server.requests=[]
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,3)
        self.addCleanup(server.shutdown)
        plan={"schema":"ace.web.dynamic-extract-plan.v1","source_ref":"fixture/JS","path":"/render",
              "browser":{"origin":f"http://127.0.0.1:{server.server_port}","allow_paths":["/render","/favicon.ico"],
                         "timeout_ms":1500,"request_limit":4},
              "ready":{"test_id":"ready","text":"Siap (1)."},"container":"container","min_records":1,
              "layout":{"row_tag":"article","row_class":"entry","primary":"key","fields":[
                  {"name":"key","marker":"key","type":"text","from":"text","required":True,"source_ref":"fixture/field"}]}}
        files,report=heavy_js_extractor.extract(plan,identity(plan))
        self.assertEqual(report["status"],"extracted",report)
        self.assertEqual(report["extraction"]["rows"][0]["values"],{"key":"Fakta render"})
        self.assertIn(report["extraction"]["html_ref"],files)
